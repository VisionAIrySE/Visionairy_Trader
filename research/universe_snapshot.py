"""Preserve broad exchange directories without a price/volume/ticker shortlist.

Current directories support prospective membership only. They do not establish
past membership, stock-vs-warrant type, broker symbols, tradability or market data.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path


def parse_directory(text, kind):
    if kind not in ('nasdaq', 'other'):
        raise ValueError('Unknown directory')
    lines = text.splitlines()
    if not lines or not lines[-1].startswith('File Creation Time: '):
        raise ValueError('Incomplete directory/footer missing')
    reader = csv.DictReader(io.StringIO('\n'.join(lines[:-1])), delimiter='|')
    key = 'Symbol' if kind == 'nasdaq' else 'NASDAQ Symbol'
    if not {key,'Security Name','Test Issue','ETF'}.issubset(set(reader.fieldnames or [])):
        raise ValueError('Unexpected exchange-directory schema')
    records = []
    for row in reader:
        if row['Test Issue'] not in ('Y','N') or row['ETF'] not in ('Y','N'):
            raise ValueError('Unknown listing flags')
        if row['Test Issue']=='Y':
            continue
        symbol = row[key].strip()
        if not symbol or not row['Security Name']:
            raise ValueError('Missing listing identity')
        records.append(dict(symbol=symbol,name=row['Security Name'],directory=kind,
                            etf_flag=row['ETF']=='Y',
                            instrument_type='etf' if row['ETF']=='Y' else 'unqualified',
                            broker_symbol_qualified=False))
    return records, lines[-1].split('|',1)[0]


def snapshot(nasdaq_path, other_path, available_at):
    records = {}
    sources = []
    for path,kind in ((Path(nasdaq_path),'nasdaq'),(Path(other_path),'other')):
        raw=path.read_bytes()
        rows,footer=parse_directory(raw.decode('utf-8-sig'),kind)
        sources.append(dict(directory=kind,sha256=hashlib.sha256(raw).hexdigest(),
                            provider_creation_label=footer,listing_rows=len(rows)))
        for row in rows:
            if row['symbol'] in records and records[row['symbol']] != row:
                raise ValueError('Conflicting listing identity; qualify symbol mapping')
            records[row['symbol']]=row
    identity=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
    return dict(selection_basis='broad_listing_snapshot',available_at=available_at,
                source_sha256=identity,sources=sources,symbols=sorted(records),
                instruments=[records[k] for k in sorted(records)],
                instrument_types={k:r['instrument_type'] for k,r in records.items()},
                session_windows=[],scope='exchange_listings_pending_security_type_and_calendar_qualification',
                historical_membership_qualified=False,market_data_coverage=False,
                selection_filters=['exchange_directory','exclude_test_issues'],
                no_price_volume_or_account_filter=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--nasdaq',required=True)
    parser.add_argument('--other',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    # The snapshot becomes available when captured, never at a backdated test start.
    available=int(max(Path(args.nasdaq).stat().st_mtime,Path(args.other).stat().st_mtime))
    result=snapshot(args.nasdaq,args.other,available)
    Path(args.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(listings=len(result['symbols']),sources=result['sources'],
                          available_at_utc=datetime.fromtimestamp(available,timezone.utc).isoformat(),
                          historical_membership_qualified=False,market_data_coverage=False)))
