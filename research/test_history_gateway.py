import json
import unittest
from history_gateway import HistoryGateway
from test_broker_readonly import Provider


class HistoryGatewayTests(unittest.TestCase):
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


if __name__=='__main__':unittest.main()

