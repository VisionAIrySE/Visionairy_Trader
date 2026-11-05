"""Broad observed-market collection and versioned snapshot-change research.

Quote snapshots are not completed OHLCV bars or validated trade recommendations.
"""
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal as D
import base64
import hashlib
import json
import re
import time
import uuid
import zlib

from broker_readonly import TradierReader, ProviderReadError
from replay import DataError

VERSION='market-monitor-v1'


class ScanCancelled(DataError):pass


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),default=str,allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def pack(value):return base64.b64encode(zlib.compress(canonical(value).encode(),9)).decode()
def unpack(value):
    decoder=zlib.decompressobj()
    raw=decoder.decompress(base64.b64decode(value,validate=True),12000001)
    if len(raw)>12000000 or not decoder.eof:raise DataError('Invalid or oversized scanner state')
    return json.loads(raw)


def numeric(value,positive=False,allow_negative=False):
    if isinstance(value,bool) or value is None:raise DataError('Missing numeric quote evidence')
    try:result=D(str(value))
    except (ValueError,ArithmeticError):raise DataError('Invalid numeric quote') from None
    if not result.is_finite() or (result<0 and not allow_negative) or (positive and result<=0):raise DataError('Invalid numeric quote')
    return result


def normalize_quote(row,instrument,clock,received_at,maximum_age=60):
    symbol=instrument['symbol']
    if row.get('symbol')!=symbol:raise DataError('Unqualified symbol substitution')
    last=numeric(row.get('last'),True);volume=numeric(row.get('volume'))
    stamp=numeric(row.get('trade_date'),True)
    if stamp!=stamp.to_integral_value() or not 946684800000<=stamp<=4102444800000:
        raise DataError('Quote requires millisecond trade timestamp')
    age=D(received_at)-stamp/D(1000)
    if age < -5:raise DataError('Quote timestamp is in the future')
    trade_utc_date=datetime.fromtimestamp(float(stamp/D(1000)),timezone.utc).date().isoformat()
    # US regular trading never crosses UTC midnight. Outside that scope do not
    # manufacture an exchange-session label from a local machine time zone.
    session=clock.get('date') if trade_utc_date==clock.get('date') else None
    name=instrument.get('name','')
    if instrument.get('etf_flag'):
        kind='etf_subtype_pending'
    elif re.search(r'\b(preferred|warrants?|rights?|units?|notes?|debentures?)\b',name,re.I):
        kind='special_security_not_ordinary_qualified'
    elif re.search(r'\b(common stock|common shares|ordinary shares?|depositary shares|depository shares)\b',name,re.I) and row.get('type')=='stock':
        kind='directory_and_broker_common_share_indicated'
    else:kind='security_type_pending'
    result=dict(symbol=symbol,last=str(last),volume=str(volume),trade_at_ms=int(stamp),
        received_at=received_at,session=session,trade_utc_date=trade_utc_date,
        trade_age_seconds=str(age),security_status=kind,
        fresh_regular_session=bool(clock.get('state')=='open' and session==clock.get('date') and 0<=age<=maximum_age),
        recommendation_qualified=False)
    for field in ('bid','ask','bid_date','ask_date','prevclose','change_percentage','average_volume'):
        try:result[field]=str(numeric(row.get(field),allow_negative=field=='change_percentage'))
        except DataError:result[field]=None
    return result


def snapshot_changes(previous,current,minimum_rise='0.02',minimum_new_shares='1',maximum_interval=600):
    """An experimental coarse trigger, not time-of-day RVOL or a breakout bar."""
    if not current['fresh_regular_session']:return None
    if not previous or previous.get('session')!=current['session']:return None
    elapsed=current['received_at']-previous['received_at']
    if not 0<elapsed<=maximum_interval or previous['trade_at_ms']>current['trade_at_ms']:return None
    old_volume=numeric(previous['volume']);new_volume=numeric(current['volume'])
    if new_volume<old_volume:return None  # revision/reset cannot become activity
    rise=numeric(current['last'],True)/numeric(previous['last'],True)-1
    added=new_volume-old_volume
    if rise<D(minimum_rise) or added<D(minimum_new_shares):return None
    event=dict(symbol=current['symbol'],available_at=current['received_at'],
        detector='snapshot_price_volume_change',version=VERSION,
        experimental_policy=dict(minimum_rise=minimum_rise,minimum_new_shares=minimum_new_shares,
                                 maximum_interval_seconds=maximum_interval),
        price_rise=str(rise),new_shares=str(added),window_seconds=elapsed,
        before=previous,after=current,qualification='coarse_research_trigger_only',
        missing=['completed_bar_setup','time_of_day_volume_baseline','liquidity_and_tradability',
                 'entry_stop_target_and_capital_review'],recommendation_qualified=False,orders_submitted=0)
    event['id']=digest(event)
    return event


class MarketMonitor:
    def __init__(self,reader,store,now=time.time,pause=time.sleep,batch_size=500,cancel_event=None):
        if not 1<=batch_size<=500:raise ValueError('Bounded batch size required')
        self.reader,self.store,self.now,self.pause,self.batch_size=reader,store,now,pause,batch_size
        self.cancel_event=cancel_event

    def run(self,universe,coverage_probe=False):
        symbols=universe['symbols'];instruments={r['symbol']:r for r in universe['instruments']}
        if len(set(symbols))!=len(symbols) or set(symbols)!=set(instruments):
            raise DataError('Distinct universe with instrument evidence required')
        clock_payload,clock_source=self.reader.get('markets/clock')
        clock=clock_payload.get('clock')
        if not isinstance(clock,dict) or not isinstance(clock.get('date'),str):raise DataError('Verified market clock required')
        cycle_id=str(uuid.uuid4())
        prior=self.store.call('scan_state',{})
        previous=unpack(prior['packed_state']) if prior.get('packed_state') else {}
        summary=dict(id=cycle_id,version=VERSION,status='running',stage='collecting_quotes',
            started_at=int(self.now()),market_clock=clock,market_clock_source=clock_source,
            universe_sha256=universe['source_sha256'],universe_available_at=universe['available_at'],
            universe_count=len(symbols),requested_count=0,observed_count=0,missing_count=0,invalid_count=0,
            unsupported_count=0,completed_batches=0,coverage_probe=coverage_probe,
            regular_session=clock.get('state')=='open',candidate_count=0,
            comparison_status='baseline_available' if previous else 'baseline_initializing',
            recommendations_generated=0,orders_submitted=0,
            detection_scope='coarse_quote_snapshot_changes_not_all_strategy_families')
        created=self.store.call('scan_begin',{'id':cycle_id,'summary':summary})
        if not created.get('created'):return created
        observations={};events=[];issues=[];sources=[]
        if clock.get('state')!='open' and not coverage_probe:
            summary.update(status='waiting_for_regular_session',stage='market_closed',finished_at=int(self.now()))
            self.store.call('scan_finish',{'id':cycle_id,'summary':summary,'packed_events':pack([])})
            return summary
        available=universe.get('available_at')
        if (not isinstance(available,(int,float)) or isinstance(available,bool)
                or not 0<=self.now()-available<=86400
                or datetime.fromtimestamp(available,timezone.utc).date().isoformat()!=clock.get('date')):
            summary.update(status='failed',stage='universe_refresh_required',finished_at=int(self.now()),
                regular_entry_review_available=False)
            self.store.call('scan_finish',{'id':cycle_id,'summary':summary,'packed_events':pack([])})
            return summary
        supported=[]
        for symbol in symbols:
            if re.fullmatch(r'[A-Z0-9./^-]+',symbol):supported.append(symbol)
            else:issues.append({'symbol':symbol,'reason':'provider_symbol_mapping_not_qualified'})
        summary['unsupported_count']=len(issues)
        summary['total_batches']=(len(supported)+self.batch_size-1)//self.batch_size
        try:
            for start in range(0,len(supported),self.batch_size):
                if self.cancel_event is not None and self.cancel_event.is_set():raise ScanCancelled('Requested scan stop')
                batch=supported[start:start+self.batch_size]
                response=None
                for attempt in range(2):
                    try:
                        response,source=self.reader.get_many_quotes(','.join(batch))
                        break
                    except ProviderReadError as exc:
                        if exc.category=='permissions':raise
                        if exc.category!='rate_limit' and (exc.http_status or 0)<500:raise
                        if attempt:raise
                        self.pause(2)
                received=int(self.now());sources.append(source)
                if 'quotes' not in response:raise DataError('Missing quote collection')
                container=response.get('quotes')
                rows=container.get('quote',[]) if isinstance(container,dict) else container or []
                if rows is None:rows=[]
                if isinstance(rows,dict):rows=[rows]
                if not isinstance(rows,list):raise DataError('Invalid quote collection')
                by_symbol={}
                for row in rows:
                    if not isinstance(row,dict) or row.get('symbol') not in batch:continue
                    if row['symbol'] in by_symbol:raise DataError('Conflicting duplicate quote')
                    by_symbol[row['symbol']]=row
                for symbol in batch:
                    if symbol not in by_symbol:
                        summary['missing_count']+=1;issues.append({'symbol':symbol,'reason':'no_quote_returned'});continue
                    try:
                        quote=normalize_quote(by_symbol[symbol],instruments[symbol],clock,received)
                        quote['source_packet_sha256']=source.get('payload_sha256')
                        observations[symbol]=quote
                        event=snapshot_changes(previous.get(symbol),quote)
                        if event:events.append(event)
                    except DataError as exc:
                        summary['invalid_count']+=1;issues.append({'symbol':symbol,'reason':str(exc)})
                summary.update(requested_count=summary['requested_count']+len(batch),
                    observed_count=len(observations),candidate_count=len(events),
                    completed_batches=summary['completed_batches']+1)
                self.store.call('scan_progress',{'id':cycle_id,'summary':summary})
                self.pause(.8)  # measured batches and provider quotas still need qualification
            final_clock,final_source=self.reader.get('markets/clock')
            summary['ending_market_clock']=final_clock.get('clock')
            summary['ending_market_clock_source']=final_source
            summary.update(status='complete',stage='complete',finished_at=int(self.now()),
                fresh_regular_count=sum(r['fresh_regular_session'] for r in observations.values()),
                security_status_counts=dict(Counter(r['security_status'] for r in observations.values())),
                coverage_fraction=str(D(len(observations))/D(len(symbols))) if symbols else None,
                full_strategy_coverage_qualified=False)
            if final_clock.get('clock',{}).get('state')!='open':
                summary['regular_entry_review_available']=False
            else:summary['regular_entry_review_available']=clock.get('state')=='open'
            self.store.call('scan_finish',{'id':cycle_id,'summary':summary,'packed_events':pack(events),
                'packed_issues':pack(issues),'sources':sources,'packed_state':pack(observations)})
            return summary
        except Exception as exc:
            summary.update(status='cancelled' if isinstance(exc,ScanCancelled) else 'failed',
                           stage='user_stopped' if isinstance(exc,ScanCancelled) else 'feed_unavailable',finished_at=int(self.now()),
                           regular_entry_review_available=False)
            self.store.call('scan_finish',{'id':cycle_id,'summary':summary,'packed_events':pack(events),
                'packed_issues':pack(issues),'sources':sources,'packed_state':None})
            raise
