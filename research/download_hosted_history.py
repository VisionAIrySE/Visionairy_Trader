"""Retrieve completed private receipts; verify their original decompressed hashes."""
import sys,json,urllib.request,base64,gzip,hashlib
from pathlib import Path
token=sys.stdin.read().strip()
directory=Path(__file__).resolve().parents[1]/'data/momentum_study/holdout_v1/hosted_pages'
directory.mkdir(exist_ok=True)
offset=0;count=0
while True:
    req=urllib.request.Request('https://kbzpmvfrwfsbdhwafbow.supabase.co/functions/v1/assessment-store',data=json.dumps({'operation':'history_capture_export','payload':{'offset':offset}}).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r:data=json.load(r)
    if 'error' in data:raise RuntimeError('Private export unavailable')
    if not data['pages']:break
    for page in data['pages']:
        packed=page['payload'];raw=gzip.decompress(base64.b64decode(packed['gzip_base64']))
        if hashlib.sha256(raw).hexdigest()!=packed['sha256']:raise ValueError('Receipt checksum mismatch')
        path=directory/(page['id']+'.json')
        if path.exists() and path.read_bytes()!=raw:raise ValueError('Conflicting receipt')
        path.write_bytes(raw);count+=1
    offset+=len(data['pages'])
    print(json.dumps({'verified_pages':count}),flush=True)
print(json.dumps({'complete':True,'pages':count}))
