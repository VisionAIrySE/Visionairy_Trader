"""Freeze a bounded coverage probe before retrieving its price histories.

Directory sampling is independent of returns. Current membership never qualifies
past membership; security types and symbol mappings remain evidence requirements.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from broker_readonly import validate_history_params


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def plan(snapshot,start,end,controls=(),sample_size=16,seed='directory_coverage_probe_v1'):
    symbols=snapshot['symbols']
    if (not seed or type(sample_size) is not int or not 1<=sample_size<=32
            or not symbols or len(set(symbols))!=len(symbols)
            or not snapshot.get('source_sha256') or type(snapshot.get('available_at')) is not int):
        raise ValueError('Explicit bounded sample and dated directory identity required')
    ordered=sorted(symbols,key=lambda s:(hashlib.sha256((seed+'/'+snapshot['source_sha256']+'/'+s).encode()).hexdigest(),s))
    picked=ordered[:sample_size]
    requests=[]
    for symbol in sorted(set(controls)|set(picked)):
        query=dict(symbol=symbol,interval='5min',start=start,end=end)
        status='pending' if re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,14}',symbol) else 'blocked_symbol_mapping'
        if status=='pending':validate_history_params('markets/timesales',dict(query,session_filter='open'))
        requests.append(dict(query=query,status=status,
            roles=([ 'preserved_archive_control'] if symbol in controls else [])+
                  (['directory_hash_sample'] if symbol in picked else []),
            instrument_type=snapshot.get('instrument_types',{}).get(symbol,'unqualified')))
    result=dict(version='bounded_history_coverage_probe_v1',seed=seed,
        directory_source_sha256=snapshot['source_sha256'],directory_snapshot_sha256=fingerprint(snapshot),
        directory_available_at=snapshot['available_at'],directory_listings=len(symbols),
        sample_size=len(picked),selected_symbols=picked,requests=requests,
        replacement_on_failure=False,price_or_outcome_filters=[],
        historical_membership_qualified=False,representative_strategy_study_ready=False,
        role='data_availability_and_prospective_baseline_probe_not_retrospective_strategy_study')
    result['plan_sha256']=fingerprint(result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--start',required=True);parser.add_argument('--end',required=True)
    parser.add_argument('--controls',nargs='*',default=[])
    args=parser.parse_args()
    result=plan(json.loads(Path(args.snapshot).read_text(encoding='utf-8')),args.start,args.end,args.controls)
    output=Path(args.output)
    if output.exists() and json.loads(output.read_text(encoding='utf-8'))!=result:
        raise ValueError('Existing frozen plan differs; preserve it and use a new experiment path')
    if not output.exists():output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('plan_sha256','sample_size','directory_listings','role')}))
