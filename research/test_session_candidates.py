from datetime import datetime,timezone
from decimal import Decimal as D
import threading
import unittest
from market_monitor import pack,unpack,digest,ScanCancelled
from session_candidates import SessionCandidates,session_bars,quote_evidence
from broker_readonly import ProviderReadError
from replay import DataError

NOW=int(datetime(2026,11,5,22,tzinfo=timezone.utc).timestamp())
OPEN=int(datetime(2026,11,5,14,30,tzinfo=timezone.utc).timestamp())
def bars_payload():
    rows=[]
    for i in range(6):
        price=10 if i<3 else 10.1
        rows.append(dict(time=f'2026-11-05T09:{30+i*5:02}:00',timestamp=OPEN+i*300,
            open=price,high=price+.01,low=price-.01,close=price,volume=10 if i<3 else 100))
    return {'series':{'data':rows}}

class SessionTests(unittest.TestCase):
    def test_quote_receipt_time_cannot_replace_bid_ask_timestamps(self):
        row=dict(symbol='TEST',bid='10',ask='10.01',bid_date=NOW*1000,ask_date=NOW*1000,trade_date=NOW*1000)
        self.assertIsNotNone(quote_evidence(row,NOW))
        for update in ({'ask_date':(NOW-61)*1000},{'bid_date':None},{'bid_date':(NOW+1)*1000},{'bid':'11'}):
            self.assertIsNone(quote_evidence(dict(row,**update),NOW))

    def test_incomplete_bars_are_withheld_and_clock_mismatch_rejected(self):
        payload=bars_payload();bars,withheld=session_bars(payload,'2026-11-05',390,OPEN+300)
        self.assertEqual(len(bars),1);self.assertEqual(withheld,5)
        payload['series']['data'][0]['timestamp']+=60
        with self.assertRaises(DataError):session_bars(payload,'2026-11-05',390,NOW)

    def make(self,permission=False,cancel=None):
        saved=[];calls=[]
        universe=dict(symbols=['TEST'],available_at=NOW-10,sources=[dict(directory=k,
            provider_creation_label='File Creation Time: 1105202615:41') for k in ('nasdaq','other')])
        class Store:
            def call(self,op,p):
                if op=='paper_review_config_get':return {'status':'not_configured'}
                if op=='scan_universe_get':return {'packed_universe':pack(universe)}
                if op=='scan_state':return dict(cycle_id='fixture',summary={'market_clock':{'date':'2026-11-05'}},
                    packed_state=pack({'TEST':{'security_status':'directory_and_broker_common_share_indicated'}}))
                saved.append((op,p));return {'saved':True}
        class Reader:
            def get(self,path,params=None):
                calls.append(path)
                source={'payload_sha256':'a'*64}
                if path=='markets/clock':return {'clock':{'date':'2026-11-05','state':'postmarket'}},source
                if path=='markets/calendar':return {'calendar':{'days':{'day':{'date':'2026-11-05','status':'open',
                    'open':{'start':'09:30','end':'16:00'}}}}},source
                if permission:raise ProviderReadError('Denied','permissions',401)
                return bars_payload(),source
            def get_many_quotes(self,symbols):return {'quotes':None},{'payload_sha256':'b'*64}
        worker=SessionCandidates(Reader(),Store(),now=lambda:NOW,pause=lambda _:None,limit=1,cancel=cancel)
        return worker,saved,calls

    def test_current_session_capture_is_source_pinned_sparse_and_never_a_buy(self):
        worker,saved,calls=self.make();report=worker.run()
        self.assertEqual(report['coverage'][0]['bars'],6)
        self.assertEqual(report['coverage'][0]['missing_slots_to_observed_edge'],72)
        self.assertEqual(report['selection']['symbols'],['TEST'])
        self.assertEqual(report['orders_submitted'],0);self.assertFalse(report['recommendation_qualified'])
        self.assertEqual(unpack(saved[0][1]['packed_report']),report)
        self.assertEqual(saved[0][1]['sha256'],digest(report))
        self.assertEqual(len(report['events']),1)
        self.assertIn('regular_session_closed',report['review']['allocation']['reviews'][0]['reasons'])

    def test_permissions_stop_and_cancellation_never_save_a_complete_report(self):
        worker,saved,calls=self.make(permission=True)
        with self.assertRaises(ProviderReadError):worker.run()
        self.assertEqual(calls.count('markets/timesales'),1);self.assertEqual(saved,[])
        stop=threading.Event();stop.set();worker,saved,calls=self.make(cancel=stop)
        with self.assertRaises(ScanCancelled):worker.run()
        self.assertEqual(calls,[]);self.assertEqual(saved,[])

    def test_stop_during_final_quote_read_prevents_completed_save(self):
        stop=threading.Event();worker,saved,calls=self.make(cancel=stop)
        original=worker.reader.get_many_quotes
        def quotes(symbols):
            result=original(symbols);stop.set();return result
        worker.reader.get_many_quotes=quotes
        with self.assertRaises(ScanCancelled):worker.run()
        self.assertEqual(saved,[])

    def test_fresh_open_session_connects_owner_budget_targets_and_shared_risk(self):
        worker,saved,calls=self.make();now=OPEN+1800;worker.now=lambda:now
        config=dict(cash='1000.00',target_multiple='3',version='paper-review-v1',mode='comparison_only',
            updated_at=now-1,target_support='unvalidated_geometry_not_forecast',orders_submitted=0)
        config['sha256']=digest(config)
        original_store=worker.store.call
        def call(op,p):
            if op=='paper_review_config_get':return config
            result=original_store(op,p)
            if op=='scan_universe_get':
                universe=unpack(result['packed_universe']);universe['available_at']=now-10
                for source in universe['sources']:source['provider_creation_label']='File Creation Time: 1105202609:59'
                return {'packed_universe':pack(universe)}
            return result
        worker.store.call=call
        original_get=worker.reader.get
        def get(path,params=None):
            if path=='markets/clock':return {'clock':{'date':'2026-11-05','state':'open'}},{'payload_sha256':'a'*64,'retrieved_at':now}
            if path=='markets/timesales':
                payload=bars_payload()
                for i,row in enumerate(payload['series']['data']):
                    price=10 if i<5 else 11
                    row.update(open=price,high=price+.01,low=price-.01,close=price,volume=1000 if i<5 else 5000)
                return payload,{'payload_sha256':'a'*64,'retrieved_at':now}
            return original_get(path,params)
        worker.reader.get=get
        worker.reader.get_many_quotes=lambda symbols:({'quotes':{'quote':dict(symbol='TEST',bid='10.99',ask='11',
            bid_date=now*1000,ask_date=now*1000)}},{'payload_sha256':'b'*64,'retrieved_at':now})
        report=worker.run();rows=report['review']['allocation']['reviews']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['state'],'conditional_research_reservation')
        self.assertGreater(rows[0]['quantity'],0)
        self.assertLessEqual(D(rows[0]['planned_risk']),D(10))
        self.assertFalse(report['recommendation_qualified']);self.assertEqual(report['orders_submitted'],0)
        self.assertEqual(len(report['target_hypotheses'][rows[0]['event_id']]),2)
