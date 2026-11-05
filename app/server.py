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
from urllib.parse import urlsplit,parse_qs

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'research'))
from mechanics_demo import run_demo
from broker_readonly import configured_snapshot
from account_cache import AccountCache
from history_gateway import HistoryGateway
from assessment_service import AssessmentService


def make_handler(report,username,password_hash,account_provider=configured_snapshot,report_factory=run_demo,history_provider=None,assessment_service=None):
    if not username or len(password_hash)!=64 or any(c not in '0123456789abcdef' for c in password_hash):
        raise ValueError('Private dashboard credentials must be configured')
    account_cache=AccountCache(account_provider)
    history_provider=history_provider or HistoryGateway().read
    assessment_service=assessment_service or AssessmentService()
    report_cache={'report':report};report_lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass  # Never log Authorization headers or research payloads.
        def send(self,status,body,kind='application/json'):
            payload=body if isinstance(body,bytes) else json.dumps(body,default=str).encode()
            self.send_response(status);self.send_header('Content-Type',kind)
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Server-Timing','app;dur=%.2f' % ((time.monotonic()-getattr(self,'request_started',time.monotonic()))*1000))
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
            self.request_started=time.monotonic()
            if self.path=='/health':return self.send(200,dict(status='ok',mode='research_only'))
            if not self.authorized():
                self.send_response(401);self.send_header('WWW-Authenticate','Basic realm="VisionAIry Trader", charset="UTF-8"')
                self.send_header('Cache-Control','no-store');self.send_header('Content-Length','0');self.end_headers();return
            if self.path=='/api/research':
                with report_lock:
                    if report_cache['report'] is None:report_cache['report']=report_factory()
                    data=report_cache['report']
                return self.send(200,data)
            if self.path=='/api/account':
                return self.send(200,account_cache.get())
            if self.path=='/api/assessment':
                return self.send(200,assessment_service.latest())
            route=urlsplit(self.path)
            if route.path in ('/api/history','/api/calendar','/api/lookup','/api/quotes','/api/clock'):
                if len(route.query)>2000:return self.send(400,dict(error='Research query too long'))
                try:params=parse_qs(route.query,keep_blank_values=True,max_num_fields=8,strict_parsing=True)
                except ValueError:return self.send(400,dict(error='Invalid research query'))
                if any(len(v)!=1 for v in params.values()):return self.send(400,dict(error='Repeated query parameter'))
                status,data=history_provider(route.path.split('/')[-1],{k:v[0] for k,v in params.items()})
                return self.send(status,data)
            files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
            if self.path in files:
                name,kind=files[self.path];return self.send(200,(ROOT/'app'/'static'/name).read_bytes(),kind)
            return self.send(404,dict(error='Not found'))
        def do_POST(self):
            self.request_started=time.monotonic()
            if self.path!='/api/assessment/start':
                return self.send(405,dict(error='This dashboard has no trading endpoints'))
            if not self.authorized():return self.send(401,dict(error='Authentication required'))
            if self.headers.get('X-Ghost-Review')!='1':
                return self.send(403,dict(error='Explicit same-origin ghost review required'))
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=128:raise ValueError()
                payload=json.loads(self.rfile.read(length))
                if payload!={'kind':'synthetic_ghost_review'}:raise ValueError()
            except (ValueError,TypeError):return self.send(400,dict(error='Known bounded review required'))
            return self.send(202,assessment_service.start())
    return Handler


def main():
    # Bind immediately. The optional mechanics demo is computed only when requested.
    handler=make_handler(None,os.environ.get('DASHBOARD_USERNAME',''),os.environ.get('DASHBOARD_PASSWORD_SHA256',''))
    ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8080'))),handler).serve_forever()


if __name__=='__main__':main()
