import unittest
from durable_history_worker import query_for,retry_decision,fetch_page

class Response:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):return self.body

class Opener:
    def __init__(self,body):self.body=body
    def open(self,req,timeout):
        self.request=req;r=Response();r.body=self.body;return r

class WorkerTests(unittest.TestCase):
    def setUp(self):self.payload={'date':'2025-04-01','symbols':['AAPL']}
    def test_fixed_read_only_host(self):
        self.assertTrue(query_for(self.payload,{}).startswith('https://data.alpaca.markets/v2/stocks/bars?'))
    def test_reject_url_injection(self):
        with self.assertRaises(ValueError):query_for(dict(self.payload,symbols=['https://evil']),{})
    def test_bounded_dates(self):
        with self.assertRaises(ValueError):query_for(dict(self.payload,date='2026-01-01'),{})
    def test_retry_limit(self):self.assertEqual(retry_decision(429,8),('failed',0))
    def test_auth_failure_stops(self):self.assertEqual(retry_decision(401,1),('failed',0))
    def test_transient_backoff(self):self.assertEqual(retry_decision(503,3),('queued',60))
    def test_no_repeated_page(self):
        with self.assertRaises(ValueError):fetch_page(self.payload,{'next_page_token':'x'},{'ALPACA_API_KEY':'test','ALPACA_API_SECRET':'test'},Opener(b'{"bars":{},"next_page_token":"x"}'))
    def test_empty_success_retained(self):
        opener=Opener(b'{"bars":{},"next_page_token":null}')
        page,token=fetch_page(self.payload,{}, {'ALPACA_API_KEY':'test','ALPACA_API_SECRET':'test'},opener)
        self.assertEqual(page['bars'],0);self.assertIsNone(token);self.assertEqual(opener.request.get_method(),'GET')

if __name__=='__main__':unittest.main()
