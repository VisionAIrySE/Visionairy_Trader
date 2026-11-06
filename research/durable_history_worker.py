"""Dedicated Render worker. GET-only Alpaca history; Postgres owns checkpoints."""
import base64
import gzip
import hashlib
import json
import os
import re
import time
import uuid
import urllib.request
import urllib.error
from datetime import date

KIND='alpaca_holdout_capture_v1'
PAGE_KIND='alpaca_holdout_page_v1'
MAX_FAILURES=8

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def query_for(payload,checkpoint):
    from urllib.parse import urlencode
    symbols=payload['symbols'];day=payload['date']
    if not isinstance(symbols,list) or not 1<=len(symbols)<=20 or any(not re.fullmatch(r'[A-Z0-9.\-]{1,24}',s) for s in symbols):raise ValueError('invalid_symbols')
    if not isinstance(day,str) or not date(2025,4,1)<=date.fromisoformat(day)<=date(2025,6,30):raise ValueError('invalid_date')
    params=dict(symbols=','.join(symbols),timeframe='1Min',start=day+'T13:30:00Z',end=day+'T19:59:59Z',feed='sip',adjustment='raw',asof='-',limit='10000',sort='asc')
    token=checkpoint.get('next_page_token')
    if token:
        if not isinstance(token,str) or len(token)>4096:raise ValueError('invalid_page_token')
        params['page_token']=token
    return 'https://data.alpaca.markets/v2/stocks/bars?'+urlencode(params)

def retry_decision(status,failures):
    transient=status is None or status in (408,429) or 500<=status<=599
    return ('queued',min(900,15*2**(failures-1))) if transient and failures<MAX_FAILURES else ('failed',0)

def fetch_page(payload,checkpoint,env,opener=None):
    url=query_for(payload,checkpoint)
    req=urllib.request.Request(url,headers={'APCA-API-KEY-ID':env['ALPACA_API_KEY'],'APCA-API-SECRET-KEY':env['ALPACA_API_SECRET']},method='GET')
    opener=opener or urllib.request.build_opener(NoRedirect())
    with opener.open(req,timeout=25) as response:
        raw=response.read(12000001)
    if len(raw)>12000000:raise ValueError('oversized_response')
    data=json.loads(raw)
    if not isinstance(data,dict) or not isinstance(data.get('bars'),dict) or 'next_page_token' not in data:raise ValueError('invalid_response')
    token=data['next_page_token']
    if token is not None and (not isinstance(token,str) or not token or token==checkpoint.get('next_page_token')):raise ValueError('invalid_pagination')
    if set(data['bars'])-set(payload['symbols']) or any(not isinstance(v,list) for v in data['bars'].values()):raise ValueError('unexpected_symbols')
    receipt={'query':url,'received_at':time.time(),'payload':data}
    packed=json.dumps(receipt,separators=(',',':')).encode()
    return {'sha256':hashlib.sha256(packed).hexdigest(),'gzip_base64':base64.b64encode(gzip.compress(packed)).decode(),'bars':sum(len(v) for v in data['bars'].values())},token

class Queue:
    def __init__(self,connection):self.db=connection
    def claim(self):
        token=str(uuid.uuid4())
        with self.db.transaction():
            row=self.db.execute("""select id,payload,checkpoint from trader.jobs
              where kind=%s and ((status='queued' and available_at<=now())
                or (status='running' and lease_until<now()))
              order by available_at,id for update skip locked limit 1""",(KIND,)).fetchone()
            if not row:return None
            job=dict(id=row[0],payload=row[1],checkpoint=row[2]);job['checkpoint']['lease_token']=token
            self.db.execute("""update trader.jobs set status='running',lease_until=now()+interval '120 seconds',
                attempts=attempts+1,checkpoint=%s::jsonb where id=%s""",(json.dumps(job['checkpoint']),job['id']))
            return job
    def finish(self,job,page,next_token):
        cp=dict(job['checkpoint']);index=cp.get('pages',0)
        with self.db.transaction():
            current=self.db.execute("select checkpoint->>'lease_token' from trader.jobs where id=%s and status='running' and lease_until>now() for update",(job['id'],)).fetchone()
            if not current or current[0]!=cp['lease_token']:return False
            self.db.execute("""insert into trader.jobs(kind,idempotency_key,payload,status)
              values(%s,%s,%s::jsonb,'complete')""",(PAGE_KIND,str(job['id'])+':'+str(index),json.dumps(page)))
            cp.update(pages=index+1,bars=cp.get('bars',0)+page['bars'],next_page_token=next_token,failures=0,last_success=time.time(),last_error=None)
            cp.pop('lease_token',None)
            self.db.execute("""update trader.jobs set status=%s,checkpoint=%s::jsonb,lease_until=null,available_at=now() where id=%s""",('queued' if next_token else 'complete',json.dumps(cp),job['id']))
        return True
    def fail(self,job,http_status=None,reason='transport'):
        cp=dict(job['checkpoint']);failures=cp.get('failures',0)+1
        status,delay=retry_decision(http_status,failures)
        token=cp.pop('lease_token');cp.update(failures=failures,last_error=reason,last_failure=time.time())
        with self.db.transaction():
            self.db.execute("""update trader.jobs set status=%s,checkpoint=%s::jsonb,
              lease_until=null,available_at=now()+(%s * interval '1 second')
              where id=%s and status='running' and checkpoint->>'lease_token'=%s""",(status,json.dumps(cp),delay,job['id'],token))

def tick(queue,env):
    job=queue.claim()
    if not job:return False
    try:page,token=fetch_page(job['payload'],job['checkpoint'],env)
    except urllib.error.HTTPError as e:queue.fail(job,e.code,'provider_http_'+str(e.code));return True
    except (ValueError,KeyError,TypeError):queue.fail(job,400,'invalid_configuration_or_response');return True
    except (OSError,TimeoutError):queue.fail(job,None,'transport');return True
    # A database failure does not advance the checkpoint; the lease expires for recovery.
    queue.finish(job,page,token)
    return True

class HostedQueue:
    def __init__(self):
        from model_assessment import HostedAssessmentStore
        self.store=HostedAssessmentStore()
    def claim(self):return self.store.call('history_capture_claim',{}).get('job')
    def finish(self,job,page,next_token):
        return self.store.call('history_capture_finish',dict(id=job['id'],lease_token=job['checkpoint']['lease_token'],page=page,next_page_token=next_token)).get('saved',False)
    def fail(self,job,http_status=None,reason='transport'):
        return self.store.call('history_capture_fail',dict(id=job['id'],lease_token=job['checkpoint']['lease_token'],http_status=http_status,reason=reason))

def main():
    if not all(os.environ.get(k) for k in ('ASSESSMENT_STORE_URL','ASSESSMENT_STORE_TOKEN','ALPACA_API_KEY','ALPACA_API_SECRET')):
        raise SystemExit('Required worker secrets are not configured')
    queue=HostedQueue()
    while True:
        try:time.sleep(1 if tick(queue,os.environ) else 15)
        except Exception:
            print('History worker reconnecting; committed progress retained',flush=True)
            time.sleep(30)

if __name__=='__main__':main()
