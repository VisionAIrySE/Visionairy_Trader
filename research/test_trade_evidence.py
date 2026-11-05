from dataclasses import replace
from decimal import Decimal as D
import unittest
from test_purpose_pipeline import fixture,policies
from independent_setups import IndependentPolicy,scan_independent
from trade_evidence import target_hypotheses,paper_liquidity
from paper_review_config import PaperReviewConfig,comparison_account,validate_config
from replay import DataError

class TradeEvidenceTests(unittest.TestCase):
    def test_targets_use_original_setup_geometry_without_later_highs(self):
        bars=fixture()[0][-180:]
        result=scan_independent('TEST',bars,IndependentPolicy('fixture',1,D(3),policies()[1]),now=bars[-1].timestamp+60)
        event=result['events'][0];now=event['available_at']
        targets=target_hypotheses(event,bars,now,'a'*64,1)
        self.assertEqual([t['risk_multiple'] for t in targets],['2','3'])
        changed=[replace(b,high=D('99999')) if b.timestamp>=now else b for b in bars]
        self.assertEqual(target_hypotheses(event,changed,now,'a'*64,1),targets)
        for t in targets:
            self.assertIsNone(t['win_probability']);self.assertIsNone(t['expected_return'])
            self.assertEqual(t['evidence'],'unvalidated_geometry_not_price_forecast')
            self.assertEqual(D(t['price']),D(event['entry_reference'])+D(t['risk_multiple'])*(D(event['entry_reference'])-D(event['proposed_stop'])))
        with self.assertRaises(DataError):target_hypotheses(event,bars,now-1,'a'*64,1)

    def test_liquidity_cap_is_bounded_bar_participation_not_quote_size_units(self):
        bars=fixture()[0][-180:][-3:]
        # Use a supported contiguous five-minute fixture derived from clock-valid bars.
        bars=[replace(b,minute=i*5,timestamp=bars[0].timestamp+i*300,volume=D(1000)) for i,b in enumerate(bars)]
        now=bars[-1].timestamp+300
        row=dict(symbol='TEST',bid='10',ask='10.01',bid_date=now*1000,ask_date=now*1000,asksize=999999)
        result=paper_liquidity(row,bars,now,'a'*64,'b'*64)
        self.assertEqual(result['maximum_quantity'],10)
        self.assertFalse(result['displayed_size_units_qualified']);self.assertFalse(result['fill_guaranteed'])
        row['asksize']=1
        self.assertEqual(paper_liquidity(row,bars,now,'a'*64,'b'*64)['maximum_quantity'],10)
        self.assertEqual(paper_liquidity(row,bars,now+61,'a'*64,'b'*64)['status'],'unknown')
        with self.assertRaises(DataError):paper_liquidity(row,bars,now,'a'*64,'b'*64,participation='.02')

    def test_paper_cash_is_explicit_validated_and_not_an_active_ledger(self):
        saved=[]
        class Store:
            def call(self,op,p):saved.append((op,p));return {'saved':True}
        config=PaperReviewConfig(Store(),now=lambda:1793918217).save({'cash':'1234.50','target_multiple':'3'})
        snapshot=comparison_account(config,1793918218)
        self.assertEqual(snapshot['mode'],'counterfactual');self.assertEqual(snapshot['settled_cash'],'1234.50')
        self.assertEqual(snapshot['total_open_risk'],'0');self.assertEqual(snapshot['open_symbols'],[])
        self.assertIn('comparison_scenario',snapshot['capital_basis'])
        self.assertIsNone(comparison_account({'status':'not_configured'},1793918218))
        with self.assertRaises(DataError):comparison_account(dict(config,cash='9999'),1793918218)
        for cash in ('0','-1','NaN','1.001','1000001',True,1000):
            with self.assertRaises(DataError):validate_config({'cash':cash,'target_multiple':'3'})
        with self.assertRaises(DataError):validate_config({'cash':'1000','target_multiple':'3','live':True})
