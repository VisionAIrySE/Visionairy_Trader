"""Explicit private plan import; no dataset or secrets enter the repository."""
import argparse,hashlib,json,os
from pathlib import Path
from durable_history_worker import KIND,query_for

def enqueue(db,plan):
    jobs=plan['jobs']
    if not 1<=len(jobs)<=1000:raise ValueError('Unexpected job count')
    for job in jobs:query_for(job,{})
    fingerprint=hashlib.sha256(json.dumps(jobs,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    with db.transaction():
        for i,job in enumerate(jobs):
            db.execute("""insert into trader.jobs(kind,idempotency_key,payload,status)
                values(%s,%s,%s::jsonb,'queued') on conflict(idempotency_key) do nothing""",
                (KIND,f'{KIND}:{fingerprint}:{i}',json.dumps(job)))
    return {'plan_hash':fingerprint,'batches':len(jobs)}

if __name__=='__main__':
    import psycopg
    parser=argparse.ArgumentParser();parser.add_argument('plan');args=parser.parse_args()
    with psycopg.connect(os.environ['HISTORY_DATABASE_URL'],autocommit=True,connect_timeout=10) as db:
        print(json.dumps(enqueue(db,json.loads(Path(args.plan).read_text()))))
