"""Read-only captured-evidence inventory. No signals, fills or return estimates."""
import argparse
from collections import defaultdict
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3


HYPOTHESES=[
 ('quiet_to_active','Prior quiet + upward price + unusual activity','diagnostic_only',
  'Prior-session bars and activity statistics','Representative dated quiet/control cohort; qualified calendar and baseline coverage'),
 ('breakout','Initial upward breakout','diagnostic_only',
  'OHLC bars and implemented structural setup component','Qualified cohort, predeclared target/entry policy and historical execution assumptions'),
 ('pullback','Controlled pullback with resumed buying','diagnostic_only',
  'OHLC/volume and implemented resumption component','Suitable independent positive/failed setups and complete follow-through'),
 ('relative_volume','Time-of-day relative volume','diagnostic_only',
  'Observed session coverage is measured below','Qualified session slots and sufficient prior complete sessions for every evaluation event'),
 ('technical_variants','Compression, ADX, Bollinger, RSI/MACD and moving-average variants','data_partial_implementation_pending',
  'OHLC/volume can support declared bar-derived calculations','Implement/freeze each accepted experiment; avoid treating correlated indicators as independent evidence'),
 ('opening_previous_high','Opening-range / previous-day-high breaks','data_partial_implementation_pending',
  'Multi-session OHLC bars for limited symbols','Qualified regular-session calendar and separate frozen trigger definitions'),
 ('vwap','VWAP reclaim / retest','approximation_only_until_qualified',
  'Bar price/volume; captured VWAP field coverage is reported separately','Qualify provider VWAP convention; bar approximations are not exact observed session VWAP'),
 ('market_sector','Strength versus market and sector','partial_market_control_only',
  'SPY minute history permits limited aligned market-control diagnostics','Sector histories and point-in-time memberships; representative comparison cohort'),
 ('breadth','Market breadth / sector participation','missing_required_evidence',
  'A limited captured roster does not establish market breadth','Broad contemporaneous symbol coverage and dated sector/universe membership'),
 ('catalyst','Catalyst-only and combined catalyst/technical signals','missing_required_evidence',
  'No timestamped catalyst archive in captured market store','Dated original news/catalysts and actual availability times, including missing/negative cases'),
 ('news_novelty','New versus recycled news and price response','missing_required_evidence',
  'No historical story/version archive','Timestamped original stories, duplicates, revisions and point-in-time response rules'),
 ('peer_lead_lag','Economically related-stock lead/lag','missing_required_evidence',
  'Incidental overlap of five histories','Predeclared economic relationships and sufficiently complete aligned peer histories'),
 ('reclaim','Failed breakdown / reclaim','data_partial_implementation_pending',
  'Limited OHLC histories','Separate frozen detection rules and qualified cohort; do not relabel breakout tests'),
 ('persistence_exhaustion','Momentum persistence / continuation versus exhaustion','diagnostic_only',
  'Limited price/activity paths and setup extension measures','Predeclared outcome labels and suitable independent failures/continuations'),
 ('management','1-2-day to approximately week-long holding and protection','conditional_scenarios_only',
  'Multi-session bars; initial/partial/trailing/gap replay components','Sufficient future sessions per event, explicit calendar/horizon, realistic costs; additions/giveback incomplete'),
 ('execution','Spread, liquidity, slippage and approval delay','conditional_scenarios_only',
  'Bars plus a short SPY trade-print probe; no captured executable bid/ask history','Observed quote/depth/fill/delay evidence or explicitly modeled stress assumptions; trade prints do not prove fills'),
 ('capital_allocation','Compare opportunities, shared capital and retaining cash','conditional_scenarios_only',
  'Acquisition comparison and joint paper-account components','Point-in-time target hypotheses, historical input adapter, suitable competing cohort; correlation/additions incomplete'),
 ('learning','AI/news incremental value and learning/adoption','missing_required_evidence',
  'Versioned trials, decision records and learning guards exist','Frozen prediction/feature records, matched ablations and later unseen evaluation; no automatic adoption'),
]


def audit(database):
    path=Path(database).resolve()
    # Opening an existing file read-only cannot create a replacement database.
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        sources=[dict(r) for r in db.execute('select id,symbol,interval,sha256,row_count from sources order by id')]
        rows=[dict(r) for r in db.execute('select symbol,interval,timestamp_ms,open,high,low,close,volume,vwap from observations order by symbol,interval,timestamp_ms')]
    groups=defaultdict(list)
    for r in rows:groups[(r['symbol'],r['interval'])].append(r)
    coverage=[]
    for (symbol,interval),observations in sorted(groups.items()):
        sessions=defaultdict(list)
        for r in observations:sessions[datetime.fromtimestamp(r['timestamp_ms']/1000,timezone.utc).date().isoformat()].append(r)
        step={'1min':60000,'5min':300000,'15min':900000}.get(interval)
        gaps=[]
        if step:
            for session,items in sessions.items():
                for a,b in zip(items,items[1:]):
                    missing=(b['timestamp_ms']-a['timestamp_ms'])//step-1
                    if missing>0:gaps.append(dict(session=session,after=a['timestamp_ms'],before=b['timestamp_ms'],missing_grid_slots=missing))
        coverage.append(dict(symbol=symbol,interval=interval,observations=len(observations),
            first_utc=datetime.fromtimestamp(observations[0]['timestamp_ms']/1000,timezone.utc).isoformat(),
            last_utc=datetime.fromtimestamp(observations[-1]['timestamp_ms']/1000,timezone.utc).isoformat(),
            observed_session_dates=len(sessions),session_counts={d:len(v) for d,v in sorted(sessions.items())},
            missing_ohlc_rows=sum(any(r[k] is None for k in ('open','high','low','close')) for r in observations),
            supplied_vwap_rows=sum(r['vwap'] is not None for r in observations),
            internal_grid_missing_slots=sum(g['missing_grid_slots'] for g in gaps),gaps=gaps,
            calendar_qualified=False,session_note='UTC date grouping, not independent exchange-calendar validation'))
    source_digest=hashlib.sha256(json.dumps(sources,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    matrix=[dict(id=i,hypothesis=h,status=s,available=a,missing=m,
                 strategy_validation_ready=False) for i,h,s,a,m in HYPOTHESES]
    for item in matrix:
        if item['id']=='relative_volume':
            item['available']='; '.join(f"{c['symbol']} {c['interval']}: {c['observed_session_dates']} observed dates" for c in coverage if c['interval']!='tick')
        if item['id']=='vwap':
            item['available']=str(sum(c['supplied_vwap_rows'] for c in coverage))+' captured VWAP values; provider convention not qualified'
    return dict(role='captured_evidence_readiness_not_strategy_results',sources=len(sources),
        source_manifest_sha256=source_digest,observations=len(rows),symbols=sorted({r['symbol'] for r in rows}),
        coverage=coverage,hypotheses=matrix,representative_strategy_study_ready=False,
        original_convenience_pilot_role='infrastructure_control_only_target_claim_withdrawn',
        current_listing_directory_is_historical_membership=False,
        qualified_historical_bid_ask_available=False,profitable_strategy_demonstrated=False,
        next_step='Freeze supported diagnostic definitions and close cohort/calendar/history/point-in-time evidence gaps',
        limitations=['No historical membership or corporate-action qualification inferred from price rows',
            'Internal grid gaps exclude absent session edges and entirely missing sessions',
            'Longer holding outcomes near archive end remain censored',
            'Existing inspected archive cannot be relabeled unseen validation'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();result=audit(args.database)
    Path(args.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('role','sources','observations','symbols','representative_strategy_study_ready')},indent=2))
