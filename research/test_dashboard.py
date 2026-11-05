"""Serialized HTTP handler checks without requiring local socket permissions."""
import base64
import hashlib
import io
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('trader_dashboard',Path(__file__).resolve().parents[1]/'app/server.py')
server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.handler=server.make_handler({'status':'synthetic','orders_submitted':0},
                                        'test',hashlib.sha256(b'test-password').hexdigest(),
                                        account_provider=lambda:server.configured_snapshot({}))
    def get(self,path,auth=None,method='GET',payload=b'',extra_headers=None):
        class Transport:
            def __init__(self,request):self.request=io.BytesIO(request);self.response=io.BytesIO()
            def makefile(self,*args):return self.request
            def sendall(self,payload):self.response.write(payload)
        request=f'{method} {path} HTTP/1.0\r\nHost: localhost\r\n'
        if auth:request+=f'Authorization: {auth}\r\n'
        for key,value in (extra_headers or {}).items():request+=f'{key}: {value}\r\n'
        if payload:request+=f'Content-Length: {len(payload)}\r\n'
        transport=Transport((request+'\r\n').encode()+payload)
        self.handler(transport,('127.0.0.1',12345),object())
        head,body=transport.response.getvalue().split(b'\r\n\r\n',1)
        lines=head.decode().split('\r\n')
        return int(lines[0].split()[1]),dict(line.split(': ',1) for line in lines[1:]),body
    def auth(self):return 'Basic '+base64.b64encode(b'test:test-password').decode()
    def test_all_dashboard_and_api_routes_are_private(self):
        for path in ('/app.js','/style.css','/api/research','/api/account','/api/assessment','/api/scanner','/api/candidates','/api/session-candidates','/api/paper-review','/api/quotes?symbols=TEST','/api/clock','/api/history?symbol=TEST','/api/calendar?month=10','/api/lookup?q=PSA','/../README.md'):
            self.assertEqual(self.get(path)[0],401)
    def test_invalid_credentials_and_malformed_base64_are_rejected(self):
        for value in ('Basic invalid','Basic '+base64.b64encode(b'test:wrong').decode(),'Bearer fake'):
            self.assertEqual(self.get('/api/research',value)[0],401)
    def test_authenticated_output_and_assets_have_security_headers(self):
        for path in ('/','/app.js','/style.css','/api/research'):
            status,headers,body=self.get(path,self.auth())
            self.assertEqual(status,200);self.assertTrue(body)
            self.assertEqual(headers['Cache-Control'],'no-store')
            self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
    def test_health_is_generic_and_unknown_paths_do_not_expose_files(self):
        self.assertEqual(self.get('/health')[0],200)
        self.assertEqual(self.get('/../README.md',self.auth())[0],404)
        self.assertEqual(self.get('/api/order',self.auth(),method='POST')[0],405)
    def test_server_refuses_empty_credentials(self):
        with self.assertRaises(ValueError):server.make_handler({},'','')

    def test_account_route_does_not_turn_missing_data_into_synthetic_balance(self):
        status,_,body=self.get('/api/account',self.auth())
        self.assertEqual(status,200)
        import json
        account=json.loads(body)
        self.assertIn(account['status'],('refreshing','not_connected'))
        self.assertIsNone(account['balances'])
        self.assertIsNone(account['measured_net_return'])

    def test_demo_does_not_run_until_requested_and_is_cached(self):
        original=self.handler;calls=[]
        self.handler=server.make_handler(None,'test',hashlib.sha256(b'test-password').hexdigest(),
            account_provider=lambda:server.configured_snapshot({}),
            report_factory=lambda:(calls.append(1) or {'status':'synthetic'}))
        try:
            self.assertEqual(calls,[])
            self.assertEqual(self.get('/health')[0],200);self.assertEqual(calls,[])
            self.assertEqual(self.get('/',self.auth())[0],200);self.assertEqual(calls,[])
            self.assertEqual(self.get('/api/research',self.auth())[0],200)
            self.assertEqual(self.get('/api/research',self.auth())[0],200)
            self.assertEqual(calls,[1])
        finally:self.handler=original

    def test_history_query_is_authenticated_and_repeated_parameters_rejected(self):
        original=self.handler;calls=[]
        self.handler=server.make_handler({},'test',hashlib.sha256(b'test-password').hexdigest(),
            history_provider=lambda kind,params:(calls.append((kind,params)) or (200,{'status':'observed'})))
        try:
            self.assertEqual(self.get('/api/history?symbol=TEST',self.auth())[0],200)
            self.assertEqual(calls,[('history',{'symbol':'TEST'})])
            self.assertEqual(self.get('/api/history?symbol=A&symbol=B',self.auth())[0],400)
            self.assertEqual(len(calls),1)
        finally:self.handler=original

    def test_assessment_start_requires_auth_explicit_header_and_known_bounded_payload(self):
        import json
        original=self.handler;calls=[]
        class Service:
            def start(self):calls.append('start');return {'status':'running','orders_submitted':0}
            def latest(self):return {'status':'not_started','orders_submitted':0}
        self.handler=server.make_handler({},'test',hashlib.sha256(b'test-password').hexdigest(),assessment_service=Service())
        body=json.dumps({'kind':'synthetic_ghost_review'}).encode()
        try:
            self.assertEqual(self.get('/api/assessment/start',method='POST',payload=body)[0],401)
            self.assertEqual(self.get('/api/assessment/start',self.auth(),'POST',body)[0],403)
            self.assertEqual(self.get('/api/assessment/start',self.auth(),'POST',b'{"kind":"real_order"}',{'X-Ghost-Review':'1'})[0],400)
            self.assertEqual(calls,[])
            status,_,result=self.get('/api/assessment/start',self.auth(),'POST',body,{'X-Ghost-Review':'1'})
            self.assertEqual(status,202);self.assertEqual(json.loads(result)['orders_submitted'],0)
            self.assertEqual(calls,['start'])
            self.assertEqual(self.get('/api/assessment',self.auth())[0],200)
        finally:self.handler=original


    def test_scanner_controls_are_private_bounded_and_do_not_block_status(self):
        class Scanner:
            def __init__(self):self.calls=[]
            def latest(self,page):self.calls.append(('latest',page));return {'summary':{'status':'running'}}
            def start(self,probe):self.calls.append(('start',probe));return {'status':'running'}
            def stop(self):self.calls.append(('stop',));return {'status':'stopping'}
        original=self.handler;scanner=Scanner()
        self.handler=server.make_handler({},'test',hashlib.sha256(b'test-password').hexdigest(),scanner_service=scanner)
        try:
            self.assertEqual(self.get('/api/scanner/start',method='POST')[0],401)
            self.assertEqual(self.get('/api/scanner/stop',self.auth(),method='POST')[0],403)
            self.assertEqual(self.get('/api/scanner?page=-1',self.auth())[0],400)
            self.assertEqual(self.get('/api/scanner?page=0&page=1',self.auth())[0],400)
            self.assertEqual(self.get('/api/scanner?page=1',self.auth())[0],200)
            for action,kind in [('start','coverage_probe'),('stop','stop_scan')]:
                body=('{"kind":"'+kind+'"}').encode()
                self.assertEqual(self.get('/api/scanner/'+action,self.auth(),method='POST',payload=body,
                    extra_headers={'X-Research-Scan':'1'})[0],202)
            self.assertEqual(scanner.calls,[('latest',1),('start',True),('stop',)])
        finally:self.handler=original

    def test_candidate_pages_are_private_and_bounded(self):
        class Candidate:
            def latest(self,page):return {'page':page,'status':'historical_detection_diagnostic'}
        original=self.handler
        self.handler=server.make_handler({},'test',hashlib.sha256(b'test-password').hexdigest(),candidate_service=Candidate())
        try:
            self.assertEqual(self.get('/api/candidates')[0],401)
            self.assertEqual(self.get('/api/candidates?page=1',self.auth())[0],200)
            self.assertEqual(self.get('/api/candidates?page=-1',self.auth())[0],400)
            self.assertEqual(self.get('/api/candidates?page=1&page=2',self.auth())[0],400)
        finally:self.handler=original

    def test_session_probe_start_requires_private_bounded_explicit_request(self):
        class Session:
            def latest(self,page):return {'page':page}
            def start(self):return {'status':'running'}
            def stop(self):return {'status':'stopping'}
        original=self.handler
        self.handler=server.make_handler({},'test',hashlib.sha256(b'test-password').hexdigest(),session_candidate_service=Session())
        try:
            self.assertEqual(self.get('/api/session-candidates/start',method='POST')[0],401)
            self.assertEqual(self.get('/api/session-candidates/start',self.auth(),method='POST')[0],403)
            self.assertEqual(self.get('/api/session-candidates/start',self.auth(),method='POST',
                payload=b'{"kind":"session_bar_probe"}',extra_headers={'X-Research-Scan':'1'})[0],202)
            self.assertEqual(self.get('/api/session-candidates?page=-1',self.auth())[0],400)
        finally:self.handler=original

    def test_paper_config_requires_owner_auth_and_explicit_validated_fields(self):
        from paper_review_config import PaperReviewConfig
        class Store:
            def call(self,op,p):return {'saved':True} if op=='paper_review_config_put' else {'status':'not_configured'}
        original=self.handler
        self.handler=server.make_handler({},'test',hashlib.sha256(b'test-password').hexdigest(),paper_review_config=PaperReviewConfig(Store()))
        try:
            self.assertEqual(self.get('/api/paper-review/config',method='POST')[0],401)
            self.assertEqual(self.get('/api/paper-review/config',self.auth(),method='POST')[0],403)
            self.assertEqual(self.get('/api/paper-review/config',self.auth(),method='POST',payload=b'{"cash":"0","target_multiple":"3"}',extra_headers={'X-Paper-Review':'1'})[0],400)
            self.assertEqual(self.get('/api/paper-review/config',self.auth(),method='POST',payload=b'{"cash":"1000","target_multiple":"3"}',extra_headers={'X-Paper-Review':'1'})[0],200)
            self.assertEqual(self.get('/api/paper-review',self.auth())[0],200)
        finally:self.handler=original

    def test_normal_login_page_and_private_session_cookie(self):
        import json
        status,headers,_=self.get('/')
        self.assertEqual(status,303);self.assertEqual(headers['Location'],'/login')
        self.assertEqual(self.get('/login')[0],200)
        status,headers,_=self.get('/api/login',method='POST',payload=json.dumps({'username':'test','password':'test-password'}).encode(),extra_headers={'X-Trader-Login':'1'})
        self.assertEqual(status,200)
        cookie=headers['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie);self.assertIn('SameSite=Strict',cookie)
        self.assertEqual(self.get('/api/research',extra_headers={'Cookie':cookie.split(';',1)[0]})[0],200)
        self.assertEqual(self.get('/api/login',method='POST',payload=b'{}')[0],403)
        self.assertEqual(self.get('/api/research',extra_headers={'Cookie':'__Host-trader_session=invalid'})[0],401)

if __name__=='__main__':unittest.main()
