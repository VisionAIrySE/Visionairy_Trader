"""Private read-only research UI. No order endpoints or private data uploads."""
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'research'))
from mechanics_demo import run_demo
from broker_readonly import configured_snapshot


def make_handler(report,username,password_hash,account_provider=configured_snapshot):
    if not username or len(password_hash)!=64 or any(c not in '0123456789abcdef' for c in password_hash):
        raise ValueError('Private dashboard credentials must be configured')
    account_cache={};account_lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass  # Never log Authorization headers or research payloads.
        def send(self,status,body,kind='application/json'):
            payload=body if isinstance(body,bytes) else json.dumps(body,default=str).encode()
            self.send_response(status);self.send_header('Content-Type',kind)
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
        def authorized(self):
            try:
                header=self.headers.get('Authorization','')
                if not header.startswith('Basic '):return False
                raw=base64.b64decode(header[6:],validate=True).decode()
                user,password=raw.split(':',1)
                return hmac.compare_digest(user,username) and hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(),password_hash)
            except (ValueError,UnicodeError):return False
        def do_GET(self):
            if self.path=='/health':return self.send(200,dict(status='ok',mode='research_only'))
            if not self.authorized():
                self.send_response(401);self.send_header('WWW-Authenticate','Basic realm="VisionAIry Trader", charset="UTF-8"')
                self.send_header('Cache-Control','no-store');self.send_header('Content-Length','0');self.end_headers();return
            if self.path=='/api/research':return self.send(200,report)
            if self.path=='/api/account':
                with account_lock:
                    now=time.monotonic()
                    if not account_cache or now-account_cache['retrieved']>=15:
                        account_cache.update(data=account_provider(),retrieved=time.monotonic())
                    data=dict(account_cache['data'],cache_age_seconds=round(time.monotonic()-account_cache['retrieved'],2))
                return self.send(200,data)
            files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
            if self.path in files:
                name,kind=files[self.path];return self.send(200,(ROOT/'app'/'static'/name).read_bytes(),kind)
            return self.send(404,dict(error='Not found'))
        def do_POST(self):return self.send(405,dict(error='This research dashboard has no action or trading endpoints'))
    return Handler


def main():
    # Only a mechanics demonstration is generated. No database or market credentials are needed.
    report=run_demo()
    handler=make_handler(report,os.environ.get('DASHBOARD_USERNAME',''),os.environ.get('DASHBOARD_PASSWORD_SHA256',''))
    ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8080'))),handler).serve_forever()


if __name__=='__main__':main()
