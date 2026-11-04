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
                                        'test',hashlib.sha256(b'test-password').hexdigest())
    def get(self,path,auth=None,method='GET'):
        class Transport:
            def __init__(self,request):self.request=io.BytesIO(request);self.response=io.BytesIO()
            def makefile(self,*args):return self.request
            def sendall(self,payload):self.response.write(payload)
        request=f'{method} {path} HTTP/1.0\r\nHost: localhost\r\n'
        if auth:request+=f'Authorization: {auth}\r\n'
        transport=Transport((request+'\r\n').encode())
        self.handler(transport,('127.0.0.1',12345),object())
        head,body=transport.response.getvalue().split(b'\r\n\r\n',1)
        lines=head.decode().split('\r\n')
        return int(lines[0].split()[1]),dict(line.split(': ',1) for line in lines[1:]),body
    def auth(self):return 'Basic '+base64.b64encode(b'test:test-password').decode()
    def test_all_dashboard_and_api_routes_are_private(self):
        for path in ('/','/app.js','/style.css','/api/research','/../README.md'):
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


if __name__=='__main__':unittest.main()
