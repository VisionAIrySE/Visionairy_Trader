"""Source-pinned historical trades with a joint cash ledger; no live order transport."""
import argparse
from collections import Counter,defaultdict
from dataclasses import asdict
from datetime import datetime,timezone
from decimal import Decimal as D
import json
from pathlib import Path
from collection_diagnostic import calendar_sessions,load_attempts,digest
from setup_detection import MarketBar,SetupPolicy,OpportunityPolicy,validate_bars,assess_remaining_opportunity
from independent_setups import IndependentPolicy,scan_independent
from trade_evidence import target_hypotheses
from managed_replay import ReplayPolicy,replay_case
from management_replay import ManagementPolicy
from portfolio_replay import replay_portfolio


def load_histories(folder):
    folder=Path(folder);plan=json.loads((folder/'plan.json').read_text())
    if digest({k:v for k,v in plan.items() if k!='plan_sha256'})!=plan['plan_sha256']:raise ValueError('Frozen collection plan changed')
    captures,attempts=load_attempts(folder,plan['plan_sha256'])
    calendars=[json.loads(p.read_text()) for p in sorted(folder.glob('calendar_*.json'))]
    histories={};coverage=[];opens={};all_sessions={}
    for request in plan['requests']:
        symbol=request['query']['symbol'];capture=captures.get(symbol)
        row=dict(symbol=symbol,status=request['status']);coverage.append(row)
        if request['status']!='pending':continue
        if not capture:row['status']='not_collected';continue
        row.update(status=capture['response']['status'],source_sha256=digest(capture))
        if row['status']!='observed':continue
        if capture['query']!=request['query']:raise ValueError('Captured query revision differs')
        sessions=calendar_sessions(calendars,request['query']['start'],request['query']['end']);all_sessions.update(sessions)
        raw=capture['response']['payload']['series']['data'];raw=raw if isinstance(raw,list) else [raw]
        bars=[];seen=defaultdict(set)
        for value in raw:
            label=datetime.fromisoformat(value['time']);day=label.date().isoformat();stamp=value['timestamp']
            utc=datetime.fromtimestamp(stamp,timezone.utc).replace(tzinfo=None)
            if label.tzinfo is not None or day not in sessions or (utc-label).total_seconds() not in (14400,18000):raise ValueError('Captured clock/calendar mismatch')
            minute=label.hour*60+label.minute-570
            bar=MarketBar(stamp,day,minute,*(D(str(value[k])) for k in ('open','high','low','close','volume')),sessions[day])
            opening=stamp-minute*60
            if opens.setdefault(day,opening)!=opening:raise ValueError('Conflicting session UTC open')
            bars.append(bar);seen[day].add(minute)
        validate_bars(bars,5)
        missing=sum(len(set(range(0,length,5))-seen[day]) for day,length in sessions.items())
        row.update(bars=len(bars),missing_slots=missing,complete_for_portfolio=missing==0)
        histories[symbol]=bars
    if set(all_sessions)-set(opens):raise ValueError('Missing source-supported global session clock')
    windows=[dict(open=opens[day],close=opens[day]+length*60) for day,length in sorted(all_sessions.items())]
    manifest=dict(plan_sha256=plan['plan_sha256'],captures_sha256=digest(captures),attempts_sha256=digest(attempts),
        calendars_sha256=digest(calendars),coverage=coverage,calendar=windows)
    return histories,coverage,windows,manifest


def summarize(rows):
    closed=[r for r in rows if r.get('status')=='modeled' and r.get('net_pnl') is not None]
    values=[D(r['net_pnl']) for r in closed]
    return dict(cases=len(rows),closed_trades=len(closed),wins=sum(v>0 for v in values),losses=sum(v<0 for v in values),
        flat=sum(v==0 for v in values),closed_trade_net_pnl=str(sum(values,D(0))),
        statuses=dict(Counter(r['status'] for r in rows)),
        unresolved_entered=sum(bool(r.get('quantity')) and r['status']!='modeled' for r in rows))


def run(folder,spec_path):
    spec=json.loads(Path(spec_path).read_text());history,coverage,calendar,manifest=load_histories(folder)
    frozen=json.loads(Path(__file__).with_name('independent_experiment.json').read_text())
    policy=IndependentPolicy(frozen['version'],5,D(frozen['minimum_breakout_volume_ratio']),SetupPolicy(**frozen['setup']))
    events=[];decisions=Counter();source_by_symbol={r['symbol']:r['source_sha256'] for r in coverage if r['status']=='observed'}
    for symbol,bars in sorted(history.items()):
        result=scan_independent(symbol,bars,policy,now=bars[-1].timestamp+300)
        events.extend(dict(e,capture_sha256=source_by_symbol[symbol]) for e in result['events'])
        decisions.update(r['state'] for r in result['decisions'])
    complete={r['symbol'] for r in coverage if r.get('complete_for_portfolio')}
    expected=[t for w in calendar for t in range(w['open'],w['close'],300)]
    horizon_bars=spec['holding_trading_minutes']//5+1
    eligibility={e['event_id']:(e['symbol'] in complete and sum(t>=e['available_at']+spec['entry_delay_seconds'] for t in expected)>=horizon_bars) for e in events}
    scenarios=[]
    for scenario in spec['scenarios']:
        slip=D(scenario['slippage']);spread=D(spec['assumed_full_spread'])
        op=OpportunityPolicy(spec['version']+'/'+scenario['name'],300,60,1950,D('.02'),D(spec['minimum_net_reward_to_risk']),slip,slip,D(0))
        replay=ReplayPolicy(spec['version']+'/'+scenario['name'],5,spec['entry_delay_seconds'],spec['holding_trading_minutes'],spec['maximum_calendar_days'],
            spec['allow_overnight'],spread,slip,slip,D(spec['fee_per_side']),D(spec['prior_volume_participation']),D(spec['minimum_net_reward_to_risk']),D(spec['maximum_entry_change']))
        assessments=[];independent=[]
        for event in events:
            target=next(t for t in target_hypotheses(event,history[event['symbol']],event['available_at'],source_by_symbol[event['symbol']]) if t['risk_multiple']==scenario['target_multiple'])
            close=D(event['entry_reference']);quote=dict(symbol=event['symbol'],bid=str(close*(1-spread/2)),ask=str(close*(1+spread/2)),observed_at=event['available_at'],
                evidence='modeled_historical_quote_not_observed',source_sha256=source_by_symbol[event['symbol']])
            assessment=assess_remaining_opportunity(event,quote,target,event['available_at'],op)
            assessment['quote_model']=quote;assessments.append(assessment)
            outcome=replay_case(event,assessment,history[event['symbol']],calendar,replay,D(spec['initial_cash']),D(spec['initial_cash']))
            independent.append(dict(outcome,symbol=event['symbol'],setup_at=event['available_at'],portfolio_eligible=eligibility[event['event_id']]))
        eligible=[e for e in events if eligibility[e['event_id']]];ids={e['event_id'] for e in eligible}
        portfolio=replay_portfolio(eligible,[a for a in assessments if a['event_id'] in ids],
            {s:history[s] for s in complete},calendar,digest(manifest),D(spec['initial_cash']),D(spec['initial_cash']),op,replay,
            spec['settlement_sessions'],ManagementPolicy('fixed_original_protection_v1'))
        by_id={e['event_id']:e for e in events}
        for row in portfolio['outcomes']:
            row.update(symbol=by_id[row['event_id']]['symbol'],setup_at=by_id[row['event_id']]['available_at'])
        scenarios.append(dict(name=scenario['name'],assumptions=scenario,independent_cases=independent,
            independent_summary=summarize(independent),portfolio=portfolio,portfolio_summary=summarize(portfolio['outcomes']),
            portfolio_eligible_patterns=len(eligible),portfolio_excluded_patterns=len(events)-len(eligible)))
    return dict(version='historical-trade-test-v1',spec=spec,spec_sha256=digest(spec),source_manifest=manifest,
        detection_spec_sha256=digest(frozen),setup_counts=dict(Counter(e['setup'] for e in events)),decision_states=dict(decisions),
        portfolio_eligibility=eligibility,scenarios=scenarios,primary_scenario=spec['primary'],orders_submitted=0,
        code_sha256={p:digest(Path(__file__).with_name(p).read_text()) for p in
            ('historical_trade_test.py','managed_replay.py','management_replay.py','portfolio_replay.py','portfolio_ledger.py','trade_evidence.py','independent_setups.py')},
        evidence='conditional_historical_bar_simulation_not_observed_execution',
        limitations=['Captured cohort is not representative or unseen validation','Current directories do not establish historical membership',
            'Historical bid/ask, slippage, fills and settlement lag are modeled','Corporate actions/instrument qualifications remain incomplete',
            'Sparse histories retained as censored cases; joint portfolio requires complete histories and entry horizon',
            'Alternative scenarios are separate portfolios, not independent additional trades','No strategy adoption or profitable-strategy conclusion'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--spec',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    report=run(a.folder,a.spec);Path(a.output).write_text(json.dumps(report,default=str,indent=2))
    print(json.dumps(dict(setups=report['setup_counts'],scenarios=[dict(name=s['name'],summary=s['portfolio_summary'],status=s['portfolio']['status'],
        final_equity=s['portfolio']['ledger']['marked_equity'],return_fraction=s['portfolio']['net_account_return'],independent=s['independent_summary']) for s in report['scenarios']]),default=str))
