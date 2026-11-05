import json
import unittest
import urllib.error
from history_gateway import HistoryGateway
from test_broker_readonly import Provider


class HistoryGatewayTests(unittest.TestCase):
    def test_market_quotes_and_clock_are_bounded_production_reads(self):
        provider=Provider({'markets/quotes':{'quotes':{'quote':{'symbol':'TEST','last':'10','trade_date':1793890000000}}},
                           'markets/clock':{'clock':{'state':'open'}}})
        for kind,params in [('quotes',{'symbols':'TEST,OTHER'}),('clock',{})]:
            gateway=HistoryGateway({'TRADIER_PRODUCTION_TOKEN':'private-test-key'},provider)
            code,result=gateway.read(kind,params)
            self.assertEqual(code,200)
            self.assertEqual(result['source']['environment'],'production')
            self.assertNotIn('private-test-key',json.dumps(result))
        self.assertTrue(all(r.get_method()=='GET' for r in provider.calls))
        gateway=HistoryGateway({'TRADIER_PRODUCTION_TOKEN':'private-test-key'},provider)
        for kind,params in [('quotes',{'symbols':'A','url':'https://evil.example'}),
                            ('quotes',{'symbols':','.join(['A']*51)}),('quotes',{'symbols':'../secret?token=x'}),
                            ('clock',{'state':'closed'})]:
            self.assertEqual(gateway.read(kind,params)[0],400)

    def setUp(self):
        self.params=dict(symbol='TEST',interval='5min',start='2026-10-01 09:30',end='2026-11-03 16:00')
        self.row=dict(time='2026-10-01T09:30:00',timestamp=1790861400,
                      open=10,high=11,low=9,close=10,volume=100)
    def gateway(self,payload):
        self.provider=Provider({'markets/timesales':payload,'markets/calendar':{'calendar':{'month':10}}})
        return HistoryGateway({'TRADIER_PRODUCTION_TOKEN':'test-server-only'},self.provider)
    def test_observed_payload_preserved_with_source_hash_and_no_qualification(self):
        payload={'series':{'data':[self.row]}}
        code,result=self.gateway(payload).read('history',self.params)
        self.assertEqual(200,code);self.assertEqual(1,result['bars'])
        self.assertEqual(payload,result['payload']);self.assertEqual(64,len(result['source']['payload_sha256']))
        self.assertFalse(result['representative_strategy_study_ready'])
        self.assertNotIn('test-server-only',json.dumps(result))
        self.assertTrue(all(r.get_method()=='GET' for r in self.provider.calls))
    def test_empty_history_remains_explicit(self):
        code,result=self.gateway({'series':None}).read('history',self.params)
        self.assertEqual(200,code);self.assertEqual('no_bars_returned',result['status'])
    def test_bad_clock_and_future_range_rejected(self):
        row=dict(self.row,timestamp=self.row['timestamp']+7200)
        self.assertEqual(502,self.gateway({'series':{'data':[row]}}).read('history',self.params)[0])
        row=dict(self.row,time='2026-12-01T09:30:00')
        self.assertEqual(502,self.gateway({'series':{'data':[row]}}).read('history',self.params)[0])
    def test_bounded_query_no_arbitrary_routes_or_ranges(self):
        gateway=self.gateway({})
        for changes in ({'symbol':'https://example.com'},{'interval':'tick'},{'end':'2027-01-01 16:00'},{'url':'https://example.com'}):
            self.assertEqual(400,gateway.read('history',dict(self.params,**changes))[0])
        self.assertEqual(400,gateway.read('orders',{})[0]);self.assertEqual([],self.provider.calls)
    def test_pacing_and_missing_credential_are_explicit(self):
        gateway=self.gateway({'series':None})
        self.assertEqual(200,gateway.read('history',self.params)[0])
        self.assertEqual(429,gateway.read('history',self.params)[0])
        self.assertEqual(503,HistoryGateway({}).read('history',self.params)[0])
    def test_calendar_pinned_and_concurrent_request_does_not_wait(self):
        gateway=self.gateway({})
        code,result=gateway.read('calendar',dict(year='2026',month='10'))
        self.assertEqual(200,code);self.assertEqual('calendar',result['source']['endpoint'])
        gateway.lock.acquire()
        try:self.assertEqual(429,gateway.read('history',self.params)[0])
        finally:gateway.lock.release()

    def test_lookup_preserves_identity_evidence_without_approving_mapping(self):
        gateway=self.gateway({})
        payload={'securities':{'security':[{'symbol':'PSA/PK','description':'Fixture only'}]}}
        self.provider.data['markets/lookup']=payload
        code,result=gateway.read('lookup',{'q':'Public Storage'})
        self.assertEqual(200,code);self.assertEqual(payload,result['payload'])
        self.assertFalse(result['mapping_confirmed'])
        self.assertTrue(self.provider.calls[-1].full_url.endswith('markets/lookup?q=Public+Storage'))
        self.assertEqual(400,self.gateway({}).read('lookup',{'q':'https://evil.example'})[0])

    def test_provider_preferred_symbol_is_encoded_and_injection_rejected(self):
        gateway=self.gateway({'series':{'data':[self.row]}})
        code,result=gateway.read('history',dict(self.params,symbol="PSA'K"))
        self.assertEqual(200,code)
        self.assertIn('symbol=PSA%27K',self.provider.calls[-1].full_url)
        self.assertEqual("PSA'K",result['source']['request']['symbol'])
        for symbol in ("PSA';DROP",'../PSA','PSA?url=bad'):
            self.assertEqual(400,self.gateway({}).read('history',dict(self.params,symbol=symbol))[0])

    def test_upstream_status_controls_retry_without_leaking_body(self):
        from test_broker_readonly import Response
        for status,retry in ((400,False),(404,False),(401,False),(403,False),(429,True),(503,True)):
            error=urllib.error.HTTPError('url',status,'private-secret',{},Response(b'private-secret'))
            code,result=self.gateway(error).read('history',self.params)
            self.assertEqual(502,code);self.assertEqual(status,result['provider_http_status'])
            self.assertEqual(retry,result['retryable']);self.assertNotIn('private-secret',json.dumps(result))


if __name__=='__main__':unittest.main()

