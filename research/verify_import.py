"""Verify preserved imports field-for-field; never finalize an unchecked import.

Offline preparation only. Execute generated SQL through the authorized backend.
No credentials, network, or real orders.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from export_supabase import TYPES, KEYS, ORDER, canon


def read_batch(path, table):
    if table not in TYPES:
        raise ValueError('Unknown table')
    sql = Path(path).read_text(encoding='utf-8')
    match = re.search(r"jsonb_to_recordset\('((?:''|[^'])*)'::jsonb\)", sql)
    if not match or not sql.startswith('insert into trader.' + table + '('):
        raise ValueError('Not a generated import batch')
    rows = json.loads(match.group(1).replace("''", "'"))
    fields = [f.strip().split()[0] for f in TYPES[table].split(',')]
    if not rows or any(set(row) != set(fields) for row in rows):
        raise ValueError('Invalid rows')
    keys = KEYS.get(table, ['id'])
    if len({tuple(r[k] for k in keys) for r in rows}) != len(rows):
        raise ValueError('Duplicate batch identity')
    return rows


def verified_batch_sql(table, rows):
    if table not in TYPES or not rows:
        raise ValueError('Unknown table or empty batch')
    fields = [f.strip().split()[0] for f in TYPES[table].split(',')]
    if any(set(row) != set(fields) for row in rows):
        raise ValueError('Column mismatch')
    keys = KEYS.get(table, ['id'])
    join = ' and '.join('d.' + k + '=s.' + k for k in keys)
    # State is verified separately after finalization, not overwritten on retries.
    compared = [f for f in fields if (table, f) not in {('datasets', 'status'), ('runs', 'status')}]
    left = 'row(' + ','.join('d.' + f for f in compared) + ')'
    right = 'row(' + ','.join('s.' + f for f in compared) + ')'
    payload = canon(rows).replace("'", "''")
    tag = '$verify_import$'
    if tag in payload:
        raise ValueError('Reserved SQL delimiter in payload')
    return f"""do {tag}
declare payload jsonb := '{payload}'::jsonb; missing bigint; mismatched bigint;
begin
 insert into trader.{table}({','.join(fields)})
 select {','.join('s.'+f for f in fields)}
 from jsonb_to_recordset(payload) as s({TYPES[table]})
 where not exists(select 1 from trader.{table} d where {join})
 on conflict do nothing;
 select count(*) filter(where d.{keys[0]} is null),
        count(*) filter(where d.{keys[0]} is not null and {left} is distinct from {right})
 into missing,mismatched
 from jsonb_to_recordset(payload) as s({TYPES[table]})
 left join trader.{table} d on {join};
 if missing<>0 or mismatched<>0 then
  raise exception 'Import verification failed for {table}: missing %, mismatched %',missing,mismatched;
 end if;
end {tag};
select '{table}' as verified_table,{len(rows)} as verified_rows;"""


def packed_batch_sql(table, rows):
    """Dictionary-encode repeated column values; verify the decoded typed records."""
    # Reuse schema/field validation and the transactional comparison implementation.
    sql = verified_batch_sql(table, rows)
    packed, expressions = {}, []
    for field in rows[0]:
        values = [row[field] for row in rows]
        unique, positions, codes = [], {}, []
        for value in values:
            key = canon(value)
            if key not in positions:
                positions[key] = len(unique)
                unique.append(value)
            codes.append(positions[key])
        if len(unique) == 1:
            packed[field] = unique
            expression = f"packed->'{field}'->0"
        elif len(canon(dict(v=unique, i=codes))) < len(canon(values)):
            packed[field] = dict(v=unique, i=codes)
            expression = f"(packed->'{field}'->'v')->((packed->'{field}'->'i'->>ix)::integer)"
        else:
            packed[field] = values
            expression = f"packed->'{field}'->ix"
        expressions.append("'" + field + "'," + expression)
    payload = canon(packed).replace("'", "''")
    if '$verify_import$' in payload:
        raise ValueError('Reserved SQL delimiter')
    start = sql.index('declare payload jsonb :=')
    end = sql.index('\nbegin', start)
    sql = (sql[:start] + "declare packed jsonb := '" + payload +
           "'::jsonb; payload jsonb; missing bigint; mismatched bigint;" + sql[end:])
    unpack = ("\n select jsonb_agg(jsonb_build_object(" + ','.join(expressions) +
              f")) into payload from generate_series(0,{len(rows)-1}) as ix;")
    return sql.replace('\nbegin\n', '\nbegin' + unpack + '\n', 1)


def prepare(source, output):
    source, output = Path(source), Path(output)
    manifest = json.loads((source / 'manifest.json').read_text())
    output.mkdir(parents=True, exist_ok=True)
    totals = {table: 0 for table in ORDER}
    receipts = []
    for batch in manifest['batches']:
        name = batch['file']
        if Path(name).name != name or not re.fullmatch(r'\d{3}_[a-z_]+\.sql', name):
            raise ValueError('Unsafe batch path')
        rows = read_batch(source / name, batch['table'])
        if len(rows) != batch['rows']:
            raise ValueError('Batch count differs from manifest')
        sql = verified_batch_sql(batch['table'], rows)
        (output / name).write_text(sql, encoding='utf-8')
        totals[batch['table']] += len(rows)
        receipts.append(dict(file=name, table=batch['table'], rows=len(rows),
                             sha256=hashlib.sha256(sql.encode()).hexdigest()))
    if totals != manifest['expected_counts']:
        raise ValueError('Manifest totals differ')
    record = dict(expected_counts=totals, batches=receipts,
                  verification='typed field comparison including exact numeric and JSON values')
    (output / 'manifest.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output)['expected_counts']))
