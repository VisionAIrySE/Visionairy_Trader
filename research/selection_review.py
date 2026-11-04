"""Audit preserved inputs against explicit experimental cohort definitions.

This diagnostic cannot promote the old convenience roster into a strategy study.
No network, orders, claims of historical market-wide coverage or invented fills.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import sqlite3

from discovery_selection import Observation, SelectionPolicy, scan_symbol, study_gate


def load_frozen_baselines(database):
    db = sqlite3.connect('file:' + Path(database).resolve().as_posix() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    run = db.execute("select * from runs where state='complete' order by created_at limit 1").fetchone()
    if run is None:
        raise ValueError('No preserved completed run')
    ids = json.loads(run['dataset_sources_json'])
    marks = ','.join('?' for _ in ids)
    rows = db.execute('select o.*,p.source_time_text from observations o '
        'join source_observations p on p.observation_id=o.id '
        f"where o.interval='5min' and p.source_id in ({marks}) "
        'order by o.symbol,o.timestamp_ms', ids).fetchall()
    series = {}
    seen = set()
    for row in rows:
        identity = (row['symbol'],row['timestamp_ms'])
        if identity in seen:
            raise ValueError('Conflicting/repeated baseline source membership')
        seen.add(identity)
        label = datetime.fromisoformat(row['source_time_text'])
        stamp = int(row['timestamp_ms'])//1000
        utc = datetime.fromtimestamp(stamp, timezone.utc).replace(tzinfo=None)
        if (utc-label).total_seconds() not in (14400,18000):
            raise ValueError('Provider time/epoch mapping disagrees')
        minute = label.hour*60+label.minute-570
        series.setdefault(row['symbol'],[]).append(Observation(stamp,label.date().isoformat(),minute,
                                                              D(row['close']),D(row['volume'])))
    db.close()
    return series, run['id']


def audit(database, start, end):
    series, run_id = load_frozen_baselines(database)
    experiments = []
    # Untuned diagnostic grid. Not adopted recommendation or live-risk parameters.
    for quiet_limit in (50000,100000,500000):
        policy = SelectionPolicy('intent_correction_diagnostic_v1',5,1,10,D(quiet_limit),
                                 D('.02'),D(3),D(10000),30)
        decisions = [r for symbol, bars in series.items() for r in scan_symbol(symbol,bars,policy)
                     if start <= r['available_at'] < end]
        universe = dict(symbols=sorted(series),selection_basis='convenience',source_sha256='legacy',
                        available_at=start)
        gate = study_gate(universe,series,start,end,decisions,5)
        by_symbol = {}
        for symbol in series:
            rows = [r for r in decisions if r['symbol']==symbol]
            baselines = [D(r['baseline_daily_shares']) for r in rows if 'baseline_daily_shares' in r]
            by_symbol[symbol] = dict(decision_windows=len(rows),
                daily_share_baseline_min=str(min(baselines)) if baselines else None,
                daily_share_baseline_max=str(max(baselines)) if baselines else None,
                states=dict(Counter(r['state'] for r in rows)),
                cohorts=dict(Counter(r['cohort'] for r in rows)))
        experiments.append(dict(policy={k:str(v) for k,v in policy.__dict__.items()},
                                study_gate=gate,symbols=by_symbol))
    return dict(role='intent_fit_diagnostic_not_strategy_performance',
                source_run=run_id,source_sha256=hashlib.sha256(Path(database).read_bytes()).hexdigest(),
                legacy_target_cohort_claim='withdrawn',experiments=experiments)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--database',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    start=int(datetime(2026,10,21,tzinfo=timezone.utc).timestamp())
    end=int(datetime(2026,11,4,tzinfo=timezone.utc).timestamp())
    result=audit(args.database,start,end)
    Path(args.output).write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
