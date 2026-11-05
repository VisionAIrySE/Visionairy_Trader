from copy import deepcopy
from decimal import Decimal
import unittest
from market_monitor import normalize_quote,snapshot_changes,pack,unpack,MarketMonitor
from replay import DataError


NOW=1793890000
CLOCK={'state':'open','date':'2026-11-05'}
INSTRUMENT={'symbol':'TEST','name':'Fixture Common Stock','etf_flag':False}


def row(**updates):
    r={'symbol':'TEST','last':'10','volume':'100','trade_date':NOW*1000,
       'type':'stock','bid':'9.99','ask':'10.01','change_percentage':'-1.2'}
    r.update(updates);return r


class MonitorTests(unittest.TestCase):
    def test_freshness_session_type_and_exact_numbers_remain_separate(self):
        q=normalize_quote(row(),INSTRUMENT,CLOCK,NOW)
        self.assertTrue(q['fresh_regular_session']);self.assertEqual(q['change_percentage'],'-1.2')
        self.assertFalse(q['recommendation_qualified'])
        q=normalize_quote(row(),dict(INSTRUMENT,name='Fixture Preferred Stock'),CLOCK,NOW)
        self.assertEqual(q['security_status'],'special_security_not_ordinary_qualified')
        self.assertFalse(normalize_quote(row(),INSTRUMENT,dict(CLOCK,state='postmarket'),NOW)['fresh_regular_session'])
        self.assertFalse(normalize_quote(row(),INSTRUMENT,CLOCK,NOW+61)['fresh_regular_session'])
        for invalid in (row(symbol='OTHER'),row(trade_date=NOW),row(last='NaN'),row(trade_date=(NOW+100)*1000)):
            with self.assertRaises(DataError):normalize_quote(invalid,INSTRUMENT,CLOCK,NOW)

    def test_snapshot_trigger_needs_prior_real_activity_and_never_becomes_a_buy(self):
        a=normalize_quote(row(),INSTRUMENT,CLOCK,NOW)
        b=normalize_quote(row(last='10.30',volume='101',trade_date=(NOW+60)*1000),INSTRUMENT,CLOCK,NOW+60)
        event=snapshot_changes(a,b)
        self.assertEqual(Decimal(event['price_rise']),Decimal('.03'))
        self.assertFalse(event['recommendation_qualified']);self.assertEqual(event['orders_submitted'],0)
        self.assertIsNone(snapshot_changes(None,b))
        for updates in ({'volume':'99'},{'received_at':NOW},{'session':'2026-11-06'},{'fresh_regular_session':False}):
            self.assertIsNone(snapshot_changes(a,dict(b,**updates)))
        self.assertEqual(unpack(pack({'TEST':b})),{'TEST':b})

    def test_broad_collection_retains_missing_unsupported_and_postmarket_scope(self):
        class Reader:
            def get(self,*args):return {'clock':dict(CLOCK,state='postmarket')},{'provider':'fixture'}
            def get_many_quotes(self,symbols):return {'quotes':{'quote':row()}},{'payload_sha256':'a'*64}
        class Store:
            def __init__(self):self.operations=[]
            def call(self,op,p):
                self.operations.append((op,deepcopy(p)))
                return {'created':True} if op=='scan_begin' else {}
        store=Store();universe={'symbols':['TEST','OTHER','PREF$A'],
            'instruments':[INSTRUMENT,dict(INSTRUMENT,symbol='OTHER'),dict(INSTRUMENT,symbol='PREF$A')],
            'source_sha256':'a'*64,'available_at':NOW-10}
        report=MarketMonitor(Reader(),store,now=lambda:NOW,pause=lambda _:None).run(universe,True)
        self.assertEqual(report['universe_count'],3);self.assertEqual(report['observed_count'],1)
        self.assertEqual(report['missing_count'],1);self.assertEqual(report['unsupported_count'],1)
        self.assertEqual(report['candidate_count'],0);self.assertFalse(report['regular_entry_review_available'])
        self.assertEqual(len(unpack(store.operations[-1][1]['packed_issues'])),2)
        self.assertEqual(len(unpack(store.operations[-1][1]['packed_state'])),1)

    def test_closed_market_without_probe_does_not_request_quotes(self):
        class Reader:
            def get(self,*args):return {'clock':dict(CLOCK,state='closed')},{}
            def get_many_quotes(self,*args):raise AssertionError('Closed-market scanning should wait')
        class Store:
            def call(self,op,p):return {'created':True} if op=='scan_begin' else {}
        u={'symbols':['TEST'],'instruments':[INSTRUMENT],'source_sha256':'a'*64,'available_at':NOW-1}
        r=MarketMonitor(Reader(),Store(),now=lambda:NOW,pause=lambda _:None).run(u)
        self.assertEqual(r['status'],'waiting_for_regular_session')

    def test_cancelled_cycle_preserves_partial_evidence_without_replacing_baseline(self):
        import threading
        from market_monitor import ScanCancelled
        cancel=threading.Event()
        class Reader:
            def get(self,*args):return {'clock':CLOCK},{}
            def get_many_quotes(self,*args):return {'quotes':{'quote':row()}},{'payload_sha256':'b'*64}
        class Store:
            def __init__(self):self.saved=[]
            def call(self,op,p):
                self.saved.append((op,deepcopy(p)))
                if op=='scan_progress':cancel.set()
                return {'created':True} if op=='scan_begin' else {}
        u={'symbols':['TEST','OTHER'],'instruments':[INSTRUMENT,dict(INSTRUMENT,symbol='OTHER')],
            'source_sha256':'a'*64,'available_at':NOW-1}
        store=Store()
        with self.assertRaises(ScanCancelled):MarketMonitor(Reader(),store,now=lambda:NOW,pause=lambda _:None,
            batch_size=1,cancel_event=cancel).run(u,True)
        terminal=store.saved[-1][1]
        self.assertEqual(terminal['summary']['status'],'cancelled')
        self.assertEqual(terminal['summary']['observed_count'],1)
        self.assertIsNone(terminal['packed_state'])
        self.assertEqual(terminal['summary']['orders_submitted'],0)
