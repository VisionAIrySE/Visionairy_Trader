"""Compact exact-record reconciliation compatible with PostgreSQL jsonb output."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re
from pathlib import Path

from export_supabase import TYPES, KEYS, ORDER
from verify_import import read_batch


def pg_json(value):
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float, Decimal)):
        return format(Decimal(str(value)), 'f')
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return '[' + ', '.join(pg_json(v) for v in value) + ']'
    if isinstance(value, dict):
        keys = sorted(value, key=lambda k: (len(k.encode()), k.encode()))
        return '{' + ', '.join(pg_json(k) + ': ' + pg_json(value[k]) for k in keys) + '}'
    raise ValueError('Unsupported canonical value')


def typed_row(table, row):
    result = dict(row)
    for field in TYPES[table].split(','):
        key, kind = field.strip().split()
        value = result[key]
        if value is None:
            continue
        if kind == 'numeric':
            result[key] = Decimal(str(value))
        elif kind in ('integer', 'bigint'):
            result[key] = int(value)
        elif kind == 'timestamptz':
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                raise ValueError('Explicit timestamp offset required')
            dt = dt.astimezone(timezone.utc)
            stamp = dt.strftime('%Y-%m-%dT%H:%M:%S')
            if dt.microsecond:
                stamp += '.' + f'{dt.microsecond:06d}'.rstrip('0')
            result[key] = stamp + '+00:00'
    return result


def checksum_sql(table):
    if table not in TYPES:
        raise ValueError('Unknown table')
    fields = [v.strip().split()[0] for v in TYPES[table].split(',')]
    fields = [f for f in fields if (table, f) not in {('datasets', 'status'), ('runs', 'status')}]
    projection = ','.join("'" + f + "',d." + f for f in fields)
    order = ','.join('d.' + f for f in KEYS.get(table, ['id']))
    return (f"select '{table}' as table_name,count(*) as rows,"
            f"md5(coalesce(string_agg(md5(jsonb_build_object({projection})::text),'' order by {order}),'')) as checksum "
            f"from trader.{table} d")


def prepare_checksums(folder):
    folder = Path(folder)
    manifest = json.loads((folder / 'manifest.json').read_text())
    tables = {k: [] for k in ORDER}
    for batch in manifest['batches']:
        tables[batch['table']].extend(read_batch(folder / batch['file'], batch['table']))
    expected = {}
    for table, rows in tables.items():
        keys = KEYS.get(table, ['id'])
        ordered = sorted(rows, key=lambda r: tuple(r[k] for k in keys))
        hashes = []
        for row in ordered:
            record = typed_row(table, row)
            if table in ('datasets', 'runs'):
                record.pop('status')
            hashes.append(hashlib.md5(pg_json(record).encode()).hexdigest())
        expected[table] = dict(rows=len(rows), checksum=hashlib.md5(''.join(hashes).encode()).hexdigest())
    return expected


def finalization_sql(expected, finish_sql):
    """Recheck the complete import under locks before freezing any records."""
    if set(expected) != set(ORDER):
        raise ValueError('All imported tables must be verified')
    values = []
    for table in ORDER:
        entry = expected[table]
        if not isinstance(entry['rows'], int) or entry['rows'] < 0 or not re.fullmatch('[0-9a-f]{32}', entry['checksum']):
            raise ValueError('Invalid expected checksum')
        values.append(f"('{table}',{entry['rows']}::bigint,'{entry['checksum']}')")
    # Only accept the two narrowly generated state transitions from our exporter.
    pattern = (r"update trader\.(datasets|runs) set status='(frozen|complete)',"
               r"(frozen_at|completed_at)=now\(\) where id='[0-9a-f-]{36}' "
               r"and status='(building|writing)';")
    lines = finish_sql.strip().splitlines()
    if not lines or any(not re.fullmatch(pattern, line) for line in lines):
        raise ValueError('Unexpected finalization command')
    actual = '\nunion all\n'.join(checksum_sql(table) for table in ORDER)
    return ("begin; set local timezone='UTC';\nlock table " +
            ','.join('trader.' + table for table in ORDER) + " in share row exclusive mode;\n" +
            "do $finalize$ declare failures bigint; begin\n" +
            "with expected(table_name,rows,checksum) as (values " + ','.join(values) +
            "), actual as (" + actual + ") select count(*) into failures from expected e " +
            "full join actual a using(table_name) where e.rows is distinct from a.rows " +
            "or e.checksum is distinct from a.checksum;\n" +
            "if failures<>0 then raise exception 'Import changed or is incomplete: % mismatched tables',failures; end if;\n" +
            "if exists(select 1 from trader.sources s left join trader.source_observations p on p.source_id=s.id " +
            "group by s.id,s.row_count having count(p.sequence)<>s.row_count) then " +
            "raise exception 'Source row lineage is incomplete'; end if;\n" +
            "if exists(select 1 from trader.source_observations p join trader.sources s on s.id=p.source_id " +
            "join trader.observations o on o.id=p.observation_id where s.instrument_id<>o.instrument_id " +
            "or s.interval_label<>o.interval_label) then raise exception 'Source lineage mismatched'; end if;\n" +
            "if exists(select 1 from trader.observations o where not exists(select 1 from trader.source_observations p " +
            "where p.observation_id=o.id)) then raise exception 'Observation without provenance'; end if;\n" +
            'end $finalize$;\n' + finish_sql + '\ncommit;')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'expected_checksums.json').write_text(json.dumps(prepare_checksums(args.source), indent=2))
    (out / 'checksums.sql').write_text("begin; set local timezone='UTC';\n" +
        '\nunion all\n'.join(checksum_sql(t) for t in ORDER) + ';\ncommit;')
    print('Prepared exact typed-record checksums for 15 imported tables.')
