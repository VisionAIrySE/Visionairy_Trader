from copy import deepcopy
from dataclasses import replace
from decimal import Decimal as D
import unittest
from test_purpose_pipeline import fixture,policies
from test_acquisition_funnel import candidate,account,policy as allocation_policy
from independent_setups import IndependentPolicy,scan_independent
from candidate_review import review_candidates
from setup_detection import OpportunityPolicy
from replay import DataError

class CandidateReviewTests(unittest.TestCase):
    def scan(self,bars,now):
        p=IndependentPolicy('synthetic_independent',1,D(3),policies()[1])
        return scan_independent('ALREADY_ACTIVE',bars,p,now=now)

    def test_breakout_and_resumed_pullback_need_no_quiet_baseline(self):
        bars=fixture()[0][-180:];now=bars[-1].timestamp+60
        result=self.scan(bars,now)
        self.assertEqual([e['setup'] for e in result['events']],['initial_breakout','pullback_continuation'])
        self.assertTrue(all(e['cohort']=='independent_momentum' for e in result['events']))
        self.assertEqual(len(result['decisions']),len(bars))
        self.assertFalse(result['recommendation_qualified'])

    def test_future_bars_and_gaps_cannot_fabricate_detection(self):
        bars=fixture()[0][-180:];cutoff=bars[10].timestamp+60
        first=self.scan(bars,cutoff)
        changed=list(bars);changed[11]=replace(changed[11],close=D('99999'))
        self.assertEqual(self.scan(changed,cutoff),first)
        gap=bars[:9]+bars[10:]
        event_times={e['available_at'] for e in self.scan(gap,cutoff)['events']}
        self.assertNotIn(cutoff,event_times)
        quiet=[replace(b,volume=D(10)) for b in bars]
        self.assertEqual(self.scan(quiet,bars[-1].timestamp+60)['events'],[])

    def review(self,rows,acc,targets=None):
        quotes={r['event']['event_id']:dict(symbol=r['event']['symbol'],bid='10',ask='10',observed_at=1000) for r in rows}
        targets=targets if targets is not None else {r['event']['event_id']:dict(r['assessment']['target_provenance'],symbol=r['event']['symbol']) for r in rows}
        return review_candidates([r['event'] for r in rows],quotes,targets,
            {r['event']['event_id']:r['evidence_groups'] for r in rows},
            {r['event']['event_id']:dict(maximum_quantity=1000,available_at=1000) for r in rows},acc,
            OpportunityPolicy('synthetic_review',300,60,120,D('.02'),D(2),D(0),D(0),D(0)),allocation_policy(),1000)

    def test_exact_setup_assessment_ranking_and_cash_are_connected(self):
        result=self.review([candidate('a','ONE',target='13'),candidate('b','TWO',target='15')],account(settled_cash='100'))
        selected=[r for r in result['allocation']['reviews'] if r['quantity']]
        self.assertEqual([r['symbol'] for r in selected],['TWO'])
        self.assertEqual(result['allocation']['remaining_settled_cash'],'0')
        self.assertEqual(result['orders_submitted'],0)
        self.assertFalse(result['recommendation_qualified'])

    def test_missing_target_and_capital_stay_visible_without_an_invented_rank(self):
        result=self.review([candidate()],None,targets={})
        row=result['allocation']['reviews'][0]
        self.assertIsNone(row['rank']);self.assertEqual(row['quantity'],0)
        self.assertIn('reconciled_paper_capital_required',row['reasons'])
        self.assertIn('fresh_quotes_and_point_in_time_target_required',row['reasons'])
        for acc in (account(mode='live'),account(observed_at=1)):
            with self.assertRaises(DataError):self.review([candidate()],acc)
