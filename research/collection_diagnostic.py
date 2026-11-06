"""Calendar-aware diagnostic of a frozen, independently price-blind coverage probe."""
import argparse
from collections import Counter,defaultdict
from dataclasses import asdict
from datetime import date,datetime,timedelta
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path

from discovery_selection import Observation,SelectionPolicy,scan_symbol
from setup_detection import MarketBar,validate_bars


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()


def calendar_sessions(captures,start,end):
    days={}
    for capture in captures:
        if capture.get('status')!='observed':raise ValueError('Observed calendar capture required')
        rows=capture['payload']['calendar']['days']['day']
        for row in rows if isinstance(rows,list) else [rows]:
            key=row['date'];date.fromisoformat(key)
            if key in days and days[key]!=row:raise ValueError('Conflicting calendar revisions')
            days[key]=row
    cursor=date.fromisoformat(start[:10]);last=date.fromisoformat(end[:10]);sessions={}
    while cursor<=last:
        key=cursor.isoformat()
        if key not in days:raise ValueError('Missing calendar date; cannot infer a closed session')
        row=days[key]
        if row['status']=='open':
            window=row['open']
            opening=datetime.fromisoformat(key+'T'+window['start'])
            closing=datetime.fromisoformat(key+'T'+window['end'])
            if window['start']!='09:30' or not 0<(closing-opening).total_seconds()<=390*60:
                raise ValueError('Unsupported regular-session calendar window')
            sessions[key]=int((closing-opening).total_seconds()/60)
        elif row['status']!='closed':raise ValueError('Unknown market calendar state')
        cursor+=timedelta(days=1)
    return sessions


def load_attempts(folder,plan_sha256):
    folder=Path(folder)
    captures={};attempts=[]
    for path in folder.glob('*.json'):
        if len(path.stem)!=64 and '.attempt-' not in path.stem:continue
        capture=json.loads(path.read_text(encoding='utf-8'))
        if capture.get('plan_sha256')!=plan_sha256:raise ValueError('Capture belongs to another collection plan')
        symbol=capture['query']['symbol']
        attempts.append(capture)
        prior=captures.get(symbol)
        if prior is not None and prior['query']!=capture['query']:
            raise ValueError('Multiple query revisions require explicit reconciliation')
        if prior is None or (prior['response']['status']!='observed' and
                (capture['response']['status']=='observed' or capture['retrieved_at']>prior['retrieved_at'])):
            captures[symbol]=capture
        elif capture['response']['status']=='observed' and prior['response']['status']=='observed':
            if digest(capture['response'])!=digest(prior['response']):
                raise ValueError('Conflicting successful revisions require explicit reconciliation')
    return captures,attempts


def run(folder,start,end):
    if type(start) is not int or type(end) is not int or start>=end:
        raise ValueError('Explicit ordered UTC evaluation bounds required')
    folder=Path(folder);plan=json.loads((folder/'plan.json').read_text(encoding='utf-8'))
    if digest({k:v for k,v in plan.items() if k!='plan_sha256'})!=plan.get('plan_sha256'):
        raise ValueError('Frozen collection plan content hash differs')
    calendars=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('calendar_*.json'))]
    captures,attempts=load_attempts(folder,plan['plan_sha256'])
    manifest=dict(version='calendar_aware_collection_diagnostic_v1',plan=plan,
        calendars_sha256=digest(calendars),captures_sha256=digest(captures),
        attempts_sha256=digest(sorted(attempts,key=lambda a:(a['query']['symbol'],a['retrieved_at']))),
        evaluation_start=start,evaluation_end=end,
        code_sha256={p:hashlib.sha256(Path(__file__).with_name(p).read_bytes()).hexdigest()
                    for p in ('collection_diagnostic.py','discovery_selection.py','setup_detection.py')})
    histories={};coverage={}
    for request in plan['requests']:
        symbol=request['query']['symbol'];capture=captures.get(symbol)
        item=dict(roles=request['roles'],instrument_type=request['instrument_type'])
        coverage[symbol]=item
        if request['status']!='pending':item['status']=request['status'];continue
        if capture is None:item['status']='not_collected';continue
        if capture['query']!=request['query']:raise ValueError('Captured query differs from frozen plan')
        response=capture['response']
        item.update(status=response['status'],http_status=capture['http_status'])
        if response['status']!='observed':continue
        query=request['query'];sessions=calendar_sessions(calendars,query['start'],query['end'])
        rows=response['payload']['series']['data']
        if isinstance(rows,dict):rows=[rows]
        bars=[];observed=defaultdict(set)
        for row in rows:
            label=datetime.fromisoformat(row['time']);session=label.date().isoformat()
            if session not in sessions:raise ValueError('Price bar outside declared open calendar')
            minute=label.hour*60+label.minute-570
            if label.second or label.microsecond:raise ValueError('Non-minute provider label')
            bar=MarketBar(int(row['timestamp']),session,minute,
                          *(D(str(row[k])) for k in ('open','high','low','close','volume')),sessions[session])
            bars.append(bar);observed[session].add(minute)
        validate_bars(bars,5)
        missing={s:len(set(range(0,n,5))-observed[s]) for s,n in sessions.items()}
        item.update(bars=len(bars),calendar_open_sessions=len(sessions),
            complete_sessions=sum(v==0 for v in missing.values()),
            missing_calendar_slots=sum(missing.values()),missing_slots_by_session=missing)
        histories[symbol]=(bars,sessions)
    experiments=[]
    for cutoff in (50000,100000,500000):
        policy=SelectionPolicy('captured_archive_control_v1',5,1,10,D(cutoff),D('.02'),D(3),D(10000),30)
        decisions=[]
        for symbol,(bars,sessions) in sorted(histories.items()):
            observations=[Observation(b.timestamp,b.session,b.minute,b.close,b.volume,b.session_minutes) for b in bars]
            decisions.extend(dict(r,diagnostic_only=True) for r in scan_symbol(symbol,observations,policy,
                              expected_sessions=sorted(sessions)) if start<=r['available_at']<end)
        summary={s:dict(states=dict(Counter(r['state'] for r in decisions if r['symbol']==s)),
                        cohorts=dict(Counter(r['cohort'] for r in decisions if r['symbol']==s))) for s in histories}
        experiments.append(dict(policy=asdict(policy),policy_sha256=policy.fingerprint(),symbols=summary,
            decisions=decisions,decision_ledger_sha256=digest(decisions)))
    return dict(role='calendar_aware_coverage_diagnostic_not_strategy_validation',manifest=manifest,
        manifest_sha256=digest(manifest),coverage=coverage,experiments=experiments,
        representative_strategy_study_ready=False,financial_outcomes=[],portfolio_return=None,
        limitations=['Directory captured after historical diagnostic start; cannot establish past membership',
            'Non-ETF directory instrument types and symbol mappings remain unqualified',
            'Provider calendar captured now is not point-in-time calendar revision evidence',
            'Missing sessions/slots remain missing, never zero-volume observations',
            'Corporate actions, executable quotes and target hypotheses remain unqualified',
            'Cutoffs remain alternative diagnostics; no profitability or operational recommendations inferred'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',required=True)
    p.add_argument('--start',required=True,type=int);p.add_argument('--end',required=True,type=int)
    p.add_argument('--output',required=True);args=p.parse_args()
    report=run(args.folder,args.start,args.end)
    Path(args.output).write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print(json.dumps(dict(manifest_sha256=report['manifest_sha256'],coverage=report['coverage']),indent=2))
