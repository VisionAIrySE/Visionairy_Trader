"""Bounded current-session feed qualification. No forecasts, capital invention or orders."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from decimal import Decimal as D
import json
from pathlib import Path
import re
import time
from market_monitor import unpack,digest,pack,ScanCancelled
from universe_refresh import current_universe
from setup_detection import MarketBar,SetupPolicy,OpportunityPolicy,validate_bars
from independent_setups import IndependentPolicy,scan_independent
from candidate_review import review_candidates
from acquisition_funnel import AllocationPolicy
from replay import DataError
from broker_readonly import ProviderReadError


def quote_evidence(row,now):
    try:
        stamps=[row[k] for k in ('bid_date','ask_date')]
        if any(type(s) is not int or not 0<=now-s/1000<=60 for s in stamps):return None
        bid,ask=D(str(row['bid'])),D(str(row['ask']))
        if not bid.is_finite() or not ask.is_finite() or not 0<bid<=ask:return None
        return dict(symbol=row['symbol'],bid=str(bid),ask=str(ask),observed_at=min(stamps)//1000)
    except (KeyError,TypeError,ValueError,ArithmeticError):return None


def session_bars(payload,day,length,now):
    series=payload.get('series');rows=series.get('data',[]) if isinstance(series,dict) else []
    if rows is None:rows=[]
    if isinstance(rows,dict):rows=[rows]
    if not isinstance(rows,list):raise DataError('Invalid bar collection')
    bars=[];withheld=0
    for row in rows:
        stamp=row.get('timestamp')
        if type(stamp) is not int:raise DataError('Bar epoch seconds required')
        if stamp+300>now:withheld+=1;continue
        label=datetime.fromisoformat(row['time'])
        utc=datetime.fromtimestamp(stamp,timezone.utc).replace(tzinfo=None)
        if (label.tzinfo is not None or label.date().isoformat()!=day or label.second
                or label.microsecond or (utc-label).total_seconds() not in (14400,18000)):
            raise DataError('Bar calendar or provider clock mismatch')
        bars.append(MarketBar(stamp,day,label.hour*60+label.minute-570,
            *(D(str(row[k])) for k in ('open','high','low','close','volume')),length))
    validate_bars(bars,5)
    return bars,withheld


class SessionCandidates:
    def __init__(self,reader,store,now=time.time,pause=time.sleep,limit=20,progress=None,cancel=None):
        if type(limit) is not int or not 1<=limit<=20:raise DataError('At most twenty probe symbols')
        self.reader=reader;self.store=store;self.now=now;self.pause=pause;self.limit=limit
        self.progress=progress or (lambda value:None);self.cancel=cancel
    def stopped(self):
        if self.cancel is not None and self.cancel.is_set():raise ScanCancelled('Current-session probe stopped')
    def run(self):
        self.stopped();started=int(self.now())
        clock,clock_source=self.reader.get('markets/clock');clock=clock['clock'];day=clock['date']
        universe=unpack(self.store.call('scan_universe_get',{})['packed_universe'])
        if not current_universe(universe,day,self.now()):raise DataError('Run broad coverage to refresh the current listing universe')
        baseline=self.store.call('scan_state',{})
        if baseline.get('summary',{}).get('market_clock',{}).get('date')!=day:
            raise DataError('Current-session broad quote baseline required')
        observed=unpack(baseline['packed_state'])
        universe_symbols=set(universe['symbols'])
        eligible=[s for s,q in observed.items() if q.get('security_status')=='directory_and_broker_common_share_indicated'
                  and re.fullmatch(r'[A-Z0-9./^-]+',s) and s in universe_symbols]
        symbols=sorted(eligible,key=lambda s:digest([day,s]))[:self.limit]
        if not symbols:raise DataError('No indicated common-share coverage available')
        # Freeze price-blind probe membership before any bar/outcome inspection.
        selection=dict(basis='session_hash_sample_of_indicated_common_shares',symbols=symbols,
            eligible_count=len(eligible),available_at=int(self.now()),broad_cycle_id=baseline['cycle_id'])
        calendar,calendar_source=self.reader.get('markets/calendar',{'month':day[5:7],'year':day[:4]})
        days=calendar['calendar']['days']['day'];days=days if isinstance(days,list) else [days]
        matching=[r for r in days if r['date']==day]
        if len(matching)!=1 or matching[0]['status']!='open':raise DataError('Observed open session calendar required')
        window=matching[0]['open']
        if window['start']!='09:30':raise DataError('Unsupported regular-session open')
        close=datetime.fromisoformat(day+'T'+window['end']);opening=datetime.fromisoformat(day+'T09:30')
        length=int((close-opening).total_seconds()/60)
        if not 0<length<=390 or length%5:raise DataError('Qualified five-minute session length required')
        spec=json.loads(Path(__file__).with_name('independent_experiment.json').read_text())
        policy=IndependentPolicy(spec['version'],5,D(spec['minimum_breakout_volume_ratio']),SetupPolicy(**spec['setup']))
        histories=[];events=[];coverage=[]
        for i,symbol in enumerate(symbols):
            self.stopped()
            query=dict(symbol=symbol,interval='5min',start=day+' 09:30',end=day+' '+window['end'],session_filter='open')
            item=dict(symbol=symbol,status='unavailable');coverage.append(item)
            try:
                payload,source=self.reader.get('markets/timesales',query)
                histories.append(dict(symbol=symbol,query=query,source=source,payload=payload))
                item['source_sha256']=source['payload_sha256']
                bars,withheld=session_bars(payload,day,length,int(self.now()))
                result=scan_independent(symbol,bars,policy,now=int(self.now()))
                # Explicit sparse coverage: no manufactured zero-volume bars.
                expected=length//5 if clock['state']!='open' else min(length//5,max((b.minute//5+1 for b in bars),default=0))
                item.update(status='observed' if bars else 'no_bars',bars=len(bars),withheld_incomplete_bars=withheld,
                    expected_slots_to_observed_edge=expected,missing_slots_to_observed_edge=max(0,expected-len(bars)),
                    source_sha256=source['payload_sha256'],setups=len(result['events']))
                item['completed_bar_edge_fresh']=bool(bars and 0<=int(self.now())-(bars[-1].timestamp+300)<=300)
                events.extend(dict(e,capture_sha256=source['payload_sha256']) for e in result['events'])
            except ProviderReadError as exc:
                if exc.category=='permissions':raise
                item.update(status='unavailable',reason=exc.category)
            except Exception as exc:
                item.update(status='unavailable',reason=type(exc).__name__)
            self.progress(dict(status='running',stage='collecting_session_bars',completed=i+1,total=len(symbols),progress_at=int(self.now())))
            self.pause(2)  # at most 30 bar requests/minute, below the existing quote sweep cadence
        self.stopped()
        quote_payload,quote_source=self.reader.get_many_quotes(','.join(symbols))
        self.stopped()
        rows=quote_payload.get('quotes',{});rows=rows.get('quote',[]) if isinstance(rows,dict) else []
        if isinstance(rows,dict):rows=[rows]
        rows=rows or []
        if len({r['symbol'] for r in rows})!=len(rows):raise DataError('Duplicate quote evidence')
        quotes_by_symbol={r['symbol']:quote_evidence(r,int(self.now())) for r in rows}
        ending_clock,ending_source=self.reader.get('markets/clock')
        starting_clock=clock;clock=ending_clock['clock']
        self.stopped()
        assessed=int(self.now());quotes={e['event_id']:quotes_by_symbol[e['symbol']] for e in events if quotes_by_symbol.get(e['symbol'])}
        op=OpportunityPolicy('session_evidence_review_v1',300,60,1950,D('.02'),D(2),D(0),D(0),D(0))
        allocation=AllocationPolicy('session_evidence_review_v1',('momentum','liquidity'),60,D(2),D(0),D(0),D(0))
        review=review_candidates(events,quotes,{}, {},{},None,op,allocation,assessed)
        if clock['state']!='open':
            for row in review['allocation']['reviews']:row['reasons'].append('regular_session_closed')
        report=dict(version='session-candidates-v1',status='complete',started_at=started,finished_at=assessed,
            market_clock=clock,clock_source=ending_source,starting_clock=starting_clock,starting_clock_source=clock_source,calendar_source=calendar_source,selection=selection,
            coverage=coverage,histories=histories,events=events,review=review,quote_source=quote_source,
            quote_payload=quote_payload,spec_sha256=digest(spec),setup_counts=dict(Counter(e['setup'] for e in events)),
            scope='twenty_symbol_current_session_feed_probe_not_full_market_strategy_scan',
            recommendation_qualified=False,orders_submitted=0,
            limitations=['Probe membership is not full-universe strategy coverage','Instrument and corporate-action qualification incomplete',
                'No validated target or paper-capital reconciliation supplied','Not a profitability or executable recommendation test'])
        packed=pack(report)
        if len(packed)>500000:raise DataError('Session report exceeds bounded storage')
        self.store.call('session_candidate_put',dict(version='session-candidates-v1',sha256=digest(report),packed_report=packed,
            recommendation_qualified=False,orders_submitted=0))
        return report
