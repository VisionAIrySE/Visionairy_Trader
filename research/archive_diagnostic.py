"""Source-pinned, control-only historical diagnostic; never simulated returns.

Observed provider session labels use an explicit 390-minute diagnostic assumption.
They are not an independently qualified exchange calendar or dated universe.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import sqlite3

from discovery_selection import Observation, SelectionPolicy, scan_symbol, study_gate
from setup_detection import MarketBar, validate_bars


VERSION = 'captured_archive_control_v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     default=str).encode()).hexdigest()


def load_archive(database):
    """Read one consistent snapshot; duplicate imports never multiply observations."""
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        sources = [dict(r) for r in db.execute(
            'select id,symbol,interval,sha256,row_count from sources order by id')]
        rows = [dict(r) for r in db.execute(
            'select p.source_id,p.source_sequence,p.source_time_text,o.* '
            'from source_observations p join observations o on o.id=p.observation_id '
            "join sources s on s.id=p.source_id where s.interval in ('1min','5min') "
            'order by s.id,p.source_sequence')]
    if not rows:
        raise ValueError('No source-linked supported bar evidence')
    source_map = {s['id']: s for s in sources}
    counts = Counter(r['source_id'] for r in rows)
    for source in sources:
        if source['interval'] in ('1min', '5min'):
            if counts[source['id']] != source['row_count']:
                raise ValueError('Source membership count differs from preserved manifest')
    unique = {}
    memberships = defaultdict(list)
    for row in rows:
        source = source_map[row['source_id']]
        if (row['symbol'], row['interval']) != (source['symbol'], source['interval']):
            raise ValueError('Source/observation instrument or interval differs')
        identity = (row['symbol'], row['interval'], row['timestamp_ms'])
        payload = {k: row[k] for k in ('symbol','interval','timestamp_ms','source_time_text',
                                     'open','high','low','close','volume')}
        if identity in unique and payload != unique[identity]:
            raise ValueError('Conflicting observations or provider session labels')
        unique[identity] = payload
        memberships[identity].append(row['source_id'])
    groups = defaultdict(list)
    pinned_rows = []
    for identity, row in sorted(unique.items()):
        label = datetime.fromisoformat(row['source_time_text'])
        if label.tzinfo is not None:
            raise ValueError('Expected preserved naive provider-local session label')
        if row['timestamp_ms'] % 1000:
            raise ValueError('Expected whole-second bar start')
        stamp = row['timestamp_ms']//1000
        utc = datetime.fromtimestamp(stamp, timezone.utc).replace(tzinfo=None)
        if (utc-label).total_seconds() not in (14400, 18000):
            raise ValueError('Provider time and UTC epoch disagree')
        if label.second or label.microsecond:
            raise ValueError('Provider label is not a minute boundary')
        minute = label.hour*60+label.minute-570
        bar = MarketBar(stamp,label.date().isoformat(),minute,
                        *(D(str(row[k])) for k in ('open','high','low','close','volume')),390)
        groups[(row['symbol'],row['interval'])].append(bar)
        pinned_rows.append(dict(**row, source_ids=sorted(memberships[identity])))
    for (_, interval), bars in groups.items():
        validate_bars(bars, int(interval[0]))
    return sources, groups, pinned_rows, len(rows)-len(unique)


def run(database, start, end):
    if type(start) is not int or type(end) is not int or start >= end:
        raise ValueError('Explicit ordered UTC evaluation bounds required')
    sources, groups, rows, duplicates = load_archive(database)
    code = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('archive_diagnostic.py','discovery_selection.py','setup_detection.py')}
    manifest = dict(version=VERSION, sources=sources, normalized_rows_sha256=digest(rows),
                    code_sha256=code, evaluation_start=start, evaluation_end=end,
                    session_assumption_minutes=390, calendar_qualified=False,
                    universe_basis='captured_convenience_control_only',
                    quiet_daily_share_cutoffs=[50000,100000,500000],
                    decision_window_minutes=5, prior_sessions=10,
                    minimum_price_rise='0.02',minimum_relative_volume='3',
                    minimum_window_dollars='10000',cooldown_minutes=30)
    manifest_hash = digest(manifest)
    experiments = []
    for interval in sorted({i for _,i in groups}):
        step = int(interval[0])
        series = {s: [Observation(b.timestamp,b.session,b.minute,b.close,b.volume,b.session_minutes)
                      for b in bars] for (s,i), bars in groups.items() if i == interval}
        for cutoff in manifest['quiet_daily_share_cutoffs']:
            policy = SelectionPolicy(VERSION,step,5//step,10,D(cutoff),D('.02'),D(3),D(10000),30)
            decisions = [dict(r,diagnostic_only=True,manifest_sha256=manifest_hash)
                         for symbol,bars in sorted(series.items()) for r in scan_symbol(symbol,bars,policy)
                         if start <= r['available_at'] < end]
            universe = dict(symbols=sorted(series), selection_basis='convenience',
                            source_sha256=manifest_hash,available_at=end)
            gate = study_gate(universe,series,start,end,decisions,step)
            summaries = {}
            for symbol in series:
                selected = [r for r in decisions if r['symbol'] == symbol]
                summaries[symbol] = dict(windows=len(selected),
                    states=dict(Counter(r['state'] for r in selected)),
                    cohorts=dict(Counter(r['cohort'] for r in selected)),
                    reasons=dict(Counter(reason for r in selected for reason in r['reasons'])))
            experiments.append(dict(interval=interval,policy=asdict(policy),
                policy_sha256=policy.fingerprint(),study_gate=gate,symbols=summaries,
                decisions=decisions,decision_ledger_sha256=digest(decisions)))
    return dict(role='captured_price_control_diagnostic_not_strategy_evaluation',
        manifest=manifest,manifest_sha256=manifest_hash,experiments=experiments,
        unique_bar_observations=len(rows),duplicate_import_memberships_removed=duplicates,
        representative_strategy_study_ready=False,portfolio_return=None,
        profitable_strategy_demonstrated=False,orders_submitted=0,
        acquisition_status='blocked_missing_qualified_cohort_calendar_quotes_and_targets',
        financial_outcomes=[],limitations=[
            'All observed decisions retained, including missing baselines and failed activations',
            'Timeframes and cutoffs are alternative diagnostics, not independent trades',
            '390-minute provider-label assumption is not exchange-calendar qualification',
            'No corporate-action qualification or historical universe membership inferred',
            'No observed historical bid/ask or point-in-time target hypotheses supplied',
            'No future highs used as targets; no fills, profitability or cash advantage inferred',
            'Other accepted momentum/catalyst hypotheses remain pending separate experiments'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True)
    parser.add_argument('--start',type=int,required=True,help='Inclusive UTC available-at epoch seconds')
    parser.add_argument('--end',type=int,required=True,help='Exclusive UTC available-at epoch seconds')
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    result = run(args.database,args.start,args.end)
    output = Path(args.output).resolve()
    if output == Path(args.database).resolve():
        raise ValueError('Output must not replace the preserved archive')
    output.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('manifest','experiments')},indent=2))
