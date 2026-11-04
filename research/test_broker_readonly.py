"""Contract and safety behavior with fabricated API responses, not a connection claim."""
import io
import json
import unittest
import urllib.error

from broker_readonly import TradierReader,configured_snapshot
from replay import DataError


class Response(io.BytesIO):
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


class Provider:
    def __init__(self,changes=None):
        self.calls=[]
        self.data={'user/profile':{'profile':{'account':{'account_number':'TEST123'}}},
            'accounts/TEST123/balances':{'balances':{'total_equity':1000.25,'total_cash':900,'cash':{'cash_available':800,'unsettled_funds':100}}},
            'accounts/TEST123/positions':{'positions':{'position':{'symbol':'TEST','quantity':5,'cost_basis':100}}},
            'markets/quotes':{'quotes':{'quote':{'symbol':'TEST','last':20.05,'bid':20.04,'ask':20.06,
                'trade_date':1800000000000,'bid_date':1800000000000,'ask_date':1800000000000}}}}
        self.data.update(changes or {})
    def open(self,request,timeout):
        self.calls.append(request)
        path=request.full_url.split('/v1/')[1].split('?')[0]
        value=self.data[path]
        if isinstance(value,Exception):raise value
        return Response(json.dumps(value).encode())


class BrokerReadTests(unittest.TestCase):
    def reader(self,provider=None,mode='production'):
        return TradierReader('test-server-only',mode,provider or Provider(),lambda:1800000000)
    def test_exact_numbers_have_provenance_but_no_invented_roi(self):
        p=Provider();result=self.reader(p).snapshot()
        self.assertEqual(result['balances']['total_equity'],'1000.25')
        self.assertEqual(result['balances']['total_cash'],'900')
        self.assertEqual(result['balances']['cash_available'],'800')
        self.assertIsNone(result['measured_net_return']);self.assertIsNone(result['planned_risk'])
        self.assertTrue(result['quotes'][0]['fresh_for_entry'])
        self.assertTrue(all(x.get_method()=='GET' for x in p.calls))
        self.assertEqual(result['account_label'],'Account ending T123')
        self.assertTrue(all('TEST123' not in str(s) for s in result['sources'].values()))
    def test_unconfigured_access_makes_no_request_and_no_fabricated_zero(self):
        p=Provider();result=configured_snapshot({},p)
        self.assertEqual(result['status'],'not_connected');self.assertEqual(p.calls,[])
        self.assertIsNone(result['balances']);self.assertIsNone(result['positions'])
    def test_cash_and_margin_are_not_silently_equivalent(self):
        p=Provider({'accounts/TEST123/balances':{'balances':{'total_equity':1000,'total_cash':500,'margin':{'stock_buying_power':2000}}}})
        result=self.reader(p).snapshot()
        self.assertIsNone(result['balances']['cash_available'])
        self.assertEqual(result['balances']['total_cash'],'500')
    def test_missing_balances_are_not_zero(self):
        p=Provider({'accounts/TEST123/balances':{'balances':{'total_equity':0}}})
        result=self.reader(p).snapshot()
        self.assertEqual(result['balances']['total_equity'],'0')
        self.assertIsNone(result['balances']['total_cash']);self.assertEqual(result['status'],'partial')
    def test_confirmed_empty_positions_differ_from_missing_evidence(self):
        for payload,expected in (({'positions':None},[]),({},None)):
            result=self.reader(Provider({'accounts/TEST123/positions':payload})).snapshot()
            self.assertEqual(result['positions'],expected)
    def test_multiple_accounts_are_not_selected_arbitrarily(self):
        p=Provider({'user/profile':{'profile':{'account':[{'account_number':'ONE'},{'account_number':'TWO'}]}}})
        result=self.reader(p).snapshot();self.assertEqual(result['status'],'unavailable')
        self.assertEqual(len(p.calls),1)
    def test_failed_quotes_do_not_erase_observed_balances(self):
        p=Provider({'markets/quotes':{'errors':{'error':'Rejected'}}})
        result=self.reader(p).snapshot();self.assertEqual(result['balances']['total_equity'],'1000.25')
        self.assertEqual(result['quotes'],[]);self.assertIn('quotes',result['errors'])
    def test_sandbox_is_not_presented_as_real_account_or_fresh_entry_data(self):
        p=Provider();result=self.reader(p,'sandbox').snapshot()
        self.assertEqual(result['evidence_mode'],'broker_paper_account')
        self.assertFalse(result['quotes'][0]['fresh_for_entry'])
        self.assertTrue(all(r.full_url.startswith('https://sandbox.tradier.com/') for r in p.calls))
    def test_future_quote_is_rejected_and_stale_quote_is_flagged(self):
        for stamp,expected_count in ((1800000002000,0),(1799999000000,1)):
            p=Provider({'markets/quotes':{'quotes':{'quote':{'symbol':'TEST','bid':20,'ask':21,'bid_date':stamp,'ask_date':stamp}}}})
            result=self.reader(p).snapshot();self.assertEqual(len(result['quotes']),expected_count)
            if expected_count:self.assertFalse(result['quotes'][0]['fresh_for_entry'])
    def test_order_funding_and_redirect_paths_are_not_permitted(self):
        p=Provider();reader=self.reader(p)
        for path in ('accounts/TEST123/orders','accounts/TEST123/funding','https://example.com','../user/profile'):
            with self.assertRaises(DataError):reader.get(path)
        self.assertEqual(p.calls,[])
    def test_provider_failures_do_not_echo_credentials_or_arbitrary_body(self):
        err=urllib.error.HTTPError('url',401,'test-server-only',{},Response(b'test-server-only'))
        result=self.reader(Provider({'user/profile':err})).snapshot()
        self.assertNotIn('test-server-only',json.dumps(result))
        self.assertEqual(result['status'],'unavailable')


if __name__=='__main__':unittest.main()
