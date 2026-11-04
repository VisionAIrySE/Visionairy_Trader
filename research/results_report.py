"""Describe preserved counterfactual results without pooling scenario rows as trades."""
import argparse
from collections import Counter
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path

def summarize(rows):
    modeled=[r for r in rows if r['status']=='modeled']
    values=[D(str(r['net_pnl'])) for r in modeled]
    return dict(scenario_rows=len(rows),modeled=len(modeled),
        event_ids=len({r['event_id'] for r in rows}),
        days=len({r['session'] for r in modeled}),
        symbols=sorted({r['symbol'] for r in modeled}),
        mean_net_dollars=str(sum(values)/len(values)) if values else None,
        positive_fraction=str(D(sum(v>0 for v in values))/len(values)) if values else None,
        statuses=dict(Counter(r['status'] for r in rows)))

def comparison(rows,**conditions):
    return summarize([r for r in rows if all(str(r[k])==str(v) for k,v in conditions.items())])

def build(rows):
    # A fixed reference case, not a best-performing case selected after results.
    ref=dict(delay_seconds=60,hold_minutes=15,budget=500,assumed_spread='0.002',assumed_fee='0')
    detectors=sorted({r['detector'] for r in rows} | {'B01_raw_2pct','B01_aligned_1pct',
        'B01_aligned_2pct','B02_aligned_1pct_rvol3','B02_aligned_2pct_rvol3'})
    detector_cases=[dict(detector=k,**comparison(rows,**ref,detector=k)) for k in detectors]
    raw=[r for r in rows if r['detector']=='B01_raw_2pct']
    sweeps={}
    for field,values in [('delay_seconds',[0,60,120]),('hold_minutes',[5,15,60]),
                         ('budget',[25,50,100,250,500]),('assumed_spread',['0.002','0.01','0.03']),
                         ('assumed_fee',['0','0.35'])]:
        sweeps[field]=[dict(value=v,**comparison(raw,**{**ref,field:v})) for v in values]
    return dict(stage='infrastructure_control_not_target_cohort_evidence',
        intent_fit=False,target_cohort_evidence=False,reference_case=ref,
        total=summarize(rows),detectors=detector_cases,sensitivity=sweeps,
        independent_sample_count=None,portfolio_return=None,
        limitations=['Withdrawn as evidence for the intended quiet-to-active strategy: no intent-linked universe or quiet-stock selection was implemented.',
        'AAPL/AMD/AMZN convenience sample; not a market-wide universe.',
        'Scenario rows reuse overlapping events and are not independent trades.',
        'Budget is per standalone hypothetical order, not portfolio capital.',
        'Whole shares; no fractional-share execution modeled.',
        'Bar-open executions and spread/volume assumptions; no historical quotes or fills.',
        'No stops, targets, additions, settlement or sell-decision delays simulated.',
        'No held-out comparison or evidence of a profitable strategy.'])

def money(value):
    return '—' if value is None else f'${D(value):.4f}'

def table(cases,label):
    lines=[f'| {label} | Modeled / cases | Mean net per modeled case | Positive | Days |',
           '|---|---:|---:|---:|---:|']
    for r in cases:
        positive='—' if r['positive_fraction'] is None else f"{D(r['positive_fraction'])*100:.1f}%"
        lines.append(f"| {r.get('detector',r.get('value'))} | {r['modeled']} / {r['scenario_rows']} | {money(r['mean_net_dollars'])} | {positive} | {r['days']} |")
    return '\n'.join(lines)

def markdown(report,digest):
    lines=['# VisionAIry Trader — historical pilot results','',
        '**Infrastructure-control sample only. Withdrawn as evidence for the intended quiet-to-active strategy.**','',
        f"Source outcomes SHA-256: `{digest}`",'',
        f"{report['total']['scenario_rows']:,} counterfactual rows; {report['total']['modeled']:,} modeled. These are not independent trades.",
        '', 'Reference: $500 per standalone order, 60-second entry delay, 15-minute hold, 0.2% full spread, $0 fee per side.',
        'The $500 case is a diagnostic affordability comparison and exceeds the planned $200 starting account. It is not a funding recommendation.',
        '',table(report['detectors'],'Detector'),'']
    for field,cases in report['sensitivity'].items():
        lines += [f'## Sensitivity: {field}','',
            'Raw 2% five-minute trigger; change one assumption from the reference case.',
            'Comparisons may have different affordable event sets; inspect modeled counts.',
            '',table(cases,field),'']
    lines+=['## Interpretation','',
        'Do not rank strategies from these overlapping, tiny samples. Larger spreads and fees can erase short moves; affordability filters which cases can be modeled.',
        'Zero modeled cases is missing execution evidence, not a zero return. A budget sweet spot or account growth cannot be inferred from this test.',
        '', '## Limits','']+['- '+v for v in report['limitations']]
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser();p.add_argument('--outcomes',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();raw=Path(args.outcomes).read_bytes();report=build(json.loads(raw))
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (out/'VisionAIry_Trader_Test_Results.md').write_text(markdown(report,hashlib.sha256(raw).hexdigest()),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
