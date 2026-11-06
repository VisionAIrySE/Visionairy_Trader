"""Private read-only research UI. No order endpoints or private data uploads."""
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
import secrets
from http.cookies import SimpleCookie
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
from scanner_service import ScannerService
from candidate_service import CandidateService
from session_candidate_service import SessionCandidateService
from paper_review_config import PaperReviewConfig
from historical_simulation_service import HistoricalSimulationService
from replay import DataError


def make_handler(report,username,password_hash,account_provider=configured_snapshot,report_factory=run_demo,history_provider=None,assessment_service=None,scanner_service=None,candidate_service=None,session_candidate_service=None,paper_review_config=None,historical_simulation_service=None):
    if not username or len(password_hash)!=64 or any(c not in '0123456789abcdef' for c in password_hash):
        raise ValueError('Private dashboard credentials must be configured')
    account_cache=AccountCache(account_provider)
    history_provider=history_provider or HistoryGateway().read
    assessment_service=assessment_service or AssessmentService()
    scanner_service=scanner_service or ScannerService()
    candidate_service=candidate_service or CandidateService()
    session_candidate_service=session_candidate_service or SessionCandidateService()
    paper_review_config=paper_review_config or PaperReviewConfig()
    historical_simulation_service=historical_simulation_service or HistoricalSimulationService()
    sessions={};session_lock=threading.Lock();login_attempts={}
    report_cache={'report':report};report_lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass  # Never log Authorization headers or research payloads.
        def send(self,status,body,kind='application/json',extra_headers=None):
            payload=body if isinstance(body,bytes) else json.dumps(body,default=str).encode()
            self.send_response(status);self.send_header('Content-Type',kind)
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Server-Timing','app;dur=%.2f' % ((time.monotonic()-getattr(self,'request_started',time.monotonic()))*1000))
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            for name,value in (extra_headers or {}).items():self.send_header(name,value)
            self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
        def authorized(self):
            try:
                cookies=SimpleCookie();cookies.load(self.headers.get('Cookie',''))
                token=cookies.get('__Host-trader_session')
                if token:
                    with session_lock:
                        if sessions.get(hashlib.sha256(token.value.encode()).hexdigest(),0)>time.time():return True
            except (ValueError,TypeError):pass
            try:
                header=self.headers.get('Authorization','')
                if not header.startswith('Basic '):return False
                raw=base64.b64decode(header[6:],validate=True).decode()
                user,password=raw.split(':',1)
                return hmac.compare_digest(user.encode(),username.encode()) and hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(),password_hash)
            except (ValueError,UnicodeError):return False
        def do_GET(self):
            self.request_started=time.monotonic()
            if self.path=='/health':return self.send(200,dict(status='ok',mode='research_only'))
            if self.path in ('/login','/login.js','/login.css'):
                name,kind={'/login':('login.html','text/html; charset=utf-8'),'/login.js':('login.js','text/javascript; charset=utf-8'),'/login.css':('style.css','text/css; charset=utf-8')}[self.path]
                return self.send(200,(ROOT/'app'/'static'/name).read_bytes(),kind)
            if not self.authorized():
                if self.path=='/':return self.send(303,b'',extra_headers={'Location':'/login'})
                return self.send(401,dict(error='Sign in to view this private dashboard'))
            if self.path=='/api/research':
                with report_lock:
                    if report_cache['report'] is None:report_cache['report']=report_factory()
                    data=report_cache['report']
                return self.send(200,data)
            if self.path=='/api/account':
                return self.send(200,account_cache.get())
            if self.path=='/api/paper-review':
                return self.send(200,paper_review_config.read())
            if self.path=='/api/assessment':
                return self.send(200,assessment_service.latest())
            route=urlsplit(self.path)
            if route.path=='/api/historical-simulation':
                try:
                    parameters=parse_qs(route.query,strict_parsing=True,max_num_fields=3)
                    if set(parameters)-{'page','scenario','view'} or any(len(v)!=1 for v in parameters.values()):raise ValueError()
                    page=int(parameters.get('page',['0'])[0]);scenario=parameters.get('scenario',[None])[0];view=parameters.get('view',['trades'])[0]
                    if not 0<=page<=10000 or view not in ('trades','reviews') or scenario not in (None,'3R_base','2R_comparison','3R_cost_stress'):raise ValueError()
                except (ValueError,TypeError):return self.send(400,dict(error='Known historical scenario and bounded page required'))
                return self.send(200,historical_simulation_service.latest(page,scenario,view))
            if route.path in ('/api/scanner','/api/candidates','/api/session-candidates'):
                try:
                    parameters=parse_qs(route.query,strict_parsing=True,max_num_fields=1)
                    if set(parameters)-{'page'} or any(len(v)!=1 for v in parameters.values()):raise ValueError()
                    page=int(parameters.get('page',['0'])[0])
                    if not 0<=page<=10000:raise ValueError()
                except (ValueError,TypeError):return self.send(400,dict(error='Bounded scanner page required'))
                return self.send(200,{'/api/scanner':scanner_service,'/api/candidates':candidate_service,'/api/session-candidates':session_candidate_service}[route.path].latest(page))
            if route.path in ('/api/history','/api/calendar','/api/lookup','/api/quotes','/api/clock'):
                if len(route.query)>10000:return self.send(400,dict(error='Research query too long'))
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
            if self.path=='/api/login':
                if self.headers.get('X-Trader-Login')!='1':return self.send(403,dict(error='Use the sign-in form'))
                with session_lock:
                    recent=[t for t in login_attempts.get(self.client_address[0],[]) if time.time()-t<60]
                    if len(recent)>=10:return self.send(429,dict(error='Too many attempts. Try again in one minute.'))
                    login_attempts[self.client_address[0]]=recent+[time.time()]
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=512:raise ValueError()
                    values=json.loads(self.rfile.read(size))
                    if set(values)!={'username','password'} or not all(isinstance(v,str) for v in values.values()):raise ValueError()
                except (ValueError,TypeError):return self.send(400,dict(error='Enter your username and password'))
                if not (hmac.compare_digest(values['username'].encode(),username.encode()) and hmac.compare_digest(hashlib.sha256(values['password'].encode()).hexdigest(),password_hash)):
                    return self.send(401,dict(error='Username or password was not recognized'))
                token=secrets.token_urlsafe(32);now=time.time()
                with session_lock:
                    expired=[key for key,until in sessions.items() if until<=now]
                    for key in expired:del sessions[key]
                    if len(sessions)>=1000:return self.send(503,dict(error='Sign-in capacity unavailable'))
                    sessions[hashlib.sha256(token.encode()).hexdigest()]=now+8*3600
                return self.send(200,dict(status='signed_in'),extra_headers={'Set-Cookie':'__Host-trader_session='+token+'; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=28800'})
            if self.path not in ('/api/assessment/start','/api/scanner/start','/api/scanner/stop','/api/session-candidates/start','/api/session-candidates/stop','/api/paper-review/config'):
                return self.send(405,dict(error='This dashboard has no trading endpoints'))
            if not self.authorized():return self.send(401,dict(error='Authentication required'))
            if self.path=='/api/paper-review/config':
                if self.headers.get('X-Paper-Review')!='1':return self.send(403,dict(error='Explicit paper comparison setting required'))
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=128:raise ValueError()
                    payload=json.loads(self.rfile.read(length))
                    return self.send(200,paper_review_config.save(payload))
                except (ValueError,TypeError,DataError):return self.send(400,dict(error='Explicit bounded comparison cash and target scenario required'))
                except Exception:return self.send(503,dict(error='Comparison setting could not be saved'))
            if self.path in ('/api/scanner/start','/api/scanner/stop','/api/session-candidates/start','/api/session-candidates/stop'):
                if self.headers.get('X-Research-Scan')!='1':return self.send(403,dict(error='Explicit research scan required'))
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=128:raise ValueError()
                    expected=('session_bar_probe' if self.path.startswith('/api/session-candidates') else 'coverage_probe') if self.path.endswith('/start') else 'stop_scan'
                    if json.loads(self.rfile.read(length))!={'kind':expected}:raise ValueError()
                except (ValueError,TypeError):return self.send(400,dict(error='Known bounded scan required'))
                service=session_candidate_service if self.path.startswith('/api/session-candidates') else scanner_service
                return self.send(202,(service.start() if service is session_candidate_service else service.start(True)) if self.path.endswith('/start') else service.stop())
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
