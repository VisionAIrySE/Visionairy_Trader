"""Frozen-rule panel replay. Activity-only diagnostics are not quote-qualified trades."""
import json
from collections import defaultdict,Counter
from urllib.parse import urlsplit,parse_qs
from momentum_cohort import ROOT,read,write,qualify
from momentum_discovery_replay import replay,describe,POLICIES,SCENARIOS

def main():
    directory=ROOT/'data/momentum_study/holdout_v1'
    files=list((directory/'hosted_pages').glob('*.json'))
    if len(files)!=147:raise ValueError('Expected all147 verified hosted receipts')
    grouped=defaultdict(list);bars=0
    for file in files:
        r=read(file);params=parse_qs(urlsplit(r['query']).query);day=params['start'][0][:10]
        for symbol,rows in r['payload']['bars'].items():grouped[symbol,day].extend(rows);bars+=len(rows)
    if bars!=503478:raise ValueError('Hosted bar count mismatch')
    actions=set()
    for records in read(ROOT/'data/momentum_study/corporate_actions_probe.json')['payload']['corporate_actions'].values():
        for a in records:
            for symbol in [a.get('symbol'),a.get('old_symbol'),a.get('new_symbol')]:
                if symbol:actions.add((symbol,a.get('ex_date',a.get('process_date'))))
    activity={(r['symbol'],r['date']):r for r in read(directory/'panel_audit_records.json') if r['status']=='signal'}
    records=[]
    for signal in read(directory/'panel_signals.json'):
        key=(signal['symbol'],signal['date']);r=qualify(*key,grouped[key],actions)
        if r['status'] in ('case','control','middle') and (r['signal_at']!=signal['signal_at'] or r['signal_price']!=signal['signal_price']):r={'symbol':key[0],'date':key[1],'status':'opening_capture_disagreement'}
        r['activity_pass']=activity[key]['passes_100_dollar_activity'];records.append(r)
    write(directory/'full_qualification.json',records)
    results=[]
    for r in records:
        if r['status'] not in ('case','control','middle'):continue
        for scenario,delay,slip in SCENARIOS:
            for policy in POLICIES:
                result=replay(r,policy,delay,slip)
                results.append(dict(symbol=r['symbol'],date=r['date'],activity_pass=r['activity_pass'],complete_minutes=r['complete_minutes'],scenario=scenario,policy=policy,**result))
    write(directory/'holdout_replay_results.json',results)
    aggregates=[]
    for subset in ['all_qualified','activity_100','activity_100_complete_minutes']:
        for scenario,_,_ in SCENARIOS:
            for policy in POLICIES:
                rows=[r for r in results if r['scenario']==scenario and r['policy']==policy and (subset=='all_qualified' or r['activity_pass']) and (subset!='activity_100_complete_minutes' or r['complete_minutes'])]
                modeled=[r for r in rows if r['status']=='modeled']
                aggregates.append(dict(subset=subset,scenario=scenario,policy=policy,attempts=len(rows),exclusions=dict(Counter(r['status'] for r in rows if r['status']!='modeled')),**describe([r['return'] for r in modeled])))
    report={'signals':len(records),'bars':bars,'qualification':dict(Counter(r['status'] for r in records)),
        'activity_passing_qualified':sum(r['activity_pass'] for r in records if r['status'] in ('case','control','middle')),
        'complete_minutes_qualified':sum(r.get('complete_minutes',False) for r in records),
        'aggregates':aggregates,'limitations':['Quote/spread gate not yet applied; these are activity-only diagnostics.','Missing opening/closing bars excluded and counted, which may bias results.','Sparse intraday paths can hide stop touches; complete-minute sensitivity reported.','Historical security identity, type and action coverage remain incomplete.','No fees beyond assumed slippage; no depth or actual-fill evidence.','Independent returns are not a shared-cash account result.','Intraday terminal valuation, not an adopted forced-close policy.','Panel selected from current inventory with earlier data; not full-market evidence.']}
    write(directory/'holdout_report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='aggregates'}))
    print(json.dumps([r for r in aggregates if r['subset']=='activity_100']))
if __name__=='__main__':main()
