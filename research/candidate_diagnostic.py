"""Exercise independent detection on a frozen captured cohort; no return claim."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
from collection_diagnostic import calendar_sessions,load_attempts,digest
from independent_setups import IndependentPolicy,scan_independent
from setup_detection import MarketBar,SetupPolicy,OpportunityPolicy,validate_bars
from acquisition_funnel import AllocationPolicy
from candidate_review import review_candidates


def run(folder,spec_path):
    folder=Path(folder);spec_path=Path(spec_path)
    spec=json.loads(spec_path.read_text());plan=json.loads((folder/'plan.json').read_text())
    if digest({k:v for k,v in plan.items() if k!='plan_sha256'})!=plan['plan_sha256']:raise ValueError('Collection plan changed')
    if spec['financial_outcomes_permitted'] is not False or spec['bar_minutes']!=5:raise ValueError('Detection-only five-minute specification required')
    policy=IndependentPolicy(spec['version'],spec['bar_minutes'],D(spec['minimum_breakout_volume_ratio']),SetupPolicy(**spec['setup']))
    captures,attempts=load_attempts(folder,plan['plan_sha256'])
    calendars=[json.loads(p.read_text()) for p in sorted(folder.glob('calendar_*.json'))]
    coverage=[];events=[];states=Counter()
    for request in plan['requests']:
        symbol=request['query']['symbol'];capture=captures.get(symbol)
        record={'symbol':symbol,'status':request['status']};coverage.append(record)
        if request['status']!='pending':continue
        if not capture:record['status']='not_captured';continue
        if capture['query']!=request['query']:raise ValueError('Capture differs from frozen query')
        record.update(status=capture['response']['status'],capture_sha256=digest(capture))
        if record['status']!='observed':continue
        try:
            query=request['query'];sessions=calendar_sessions(calendars,query['start'],query['end'])
            rows=capture['response']['payload']['series']['data']
            if isinstance(rows,dict):rows=[rows]
            bars=[]
            for row in rows:
                label=datetime.fromisoformat(row['time']);day=label.date().isoformat()
                if label.tzinfo is not None or day not in sessions:raise ValueError('Unqualified provider session')
                utc=datetime.utcfromtimestamp(row['timestamp'])
                if (utc-label).total_seconds() not in (14400,18000):raise ValueError('Provider clock mismatch')
                bars.append(MarketBar(int(row['timestamp']),day,label.hour*60+label.minute-570,
                    *(D(str(row[k])) for k in ('open','high','low','close','volume')),sessions[day]))
            if not bars:raise ValueError('No completed bars')
            validate_bars(bars,5)
            result=scan_independent(symbol,bars,policy,now=bars[-1].timestamp+300)
            events.extend(dict(e,capture_sha256=record['capture_sha256']) for e in result['events'])
            states.update(r['state'] for r in result['decisions'])
            record.update(bars=len(bars),detected_setups=len(result['events']))
        except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
            record.update(status='invalid_history',reason=type(exc).__name__)
    groups=defaultdict(list)
    for event in events:groups[event['available_at']].append(event)
    op=OpportunityPolicy('diagnostic_missing_execution_evidence',300,60,1950,D('.02'),D(2),D(0),D(0),D(0))
    allocation=AllocationPolicy('diagnostic_missing_execution_evidence',('momentum','liquidity'),60,D(2),D(0),D(0),D(0))
    reviews=[review_candidates(batch,{}, {},{}, {},None,op,allocation,stamp) for stamp,batch in sorted(groups.items())]
    code={p:hashlib.sha256(Path(__file__).with_name(p).read_bytes()).hexdigest() for p in
        ('candidate_diagnostic.py','independent_setups.py','candidate_review.py','setup_detection.py')}
    return dict(role='captured_cohort_detection_diagnostic_only',spec=spec,spec_sha256=digest(spec),
        plan_sha256=plan['plan_sha256'],code_sha256=code,captures_sha256=digest(captures),
        attempts_sha256=digest(attempts),calendars_sha256=digest(calendars),coverage=coverage,
        decision_states=dict(states),setup_counts=dict(Counter(e['setup'] for e in events)),
        events=events,reviews=reviews,orders_submitted=0,financial_outcomes=[],
        representative_strategy_study_ready=False,recommendation_qualified=False,
        limitations=['Previously captured cohort is not unseen validation','Sparse data are not imputed',
            'Historical membership and corporate actions are not qualified',
            'No executable quotes, target hypotheses or reconciled paper capital supplied',
            'No financial performance or operating recommendation established'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--spec',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    report=run(a.folder,a.spec);Path(a.output).write_text(json.dumps(report,default=str,indent=2))
    print(json.dumps({k:report[k] for k in ('setup_counts','decision_states','coverage','spec_sha256')},default=str))
