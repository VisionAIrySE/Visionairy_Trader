"""Acceptance tests for capital decisions; all market examples are synthetic."""
from copy import deepcopy
from decimal import Decimal as D
import unittest

from acquisition_funnel import AllocationPolicy, plan_acquisitions
from purpose_runner import run_bundle
from replay import DataError
from setup_detection import fingerprint


def policy(**overrides):
    values=dict(version='synthetic_test', required_evidence_groups=('momentum','liquidity'),
        maximum_evidence_age_seconds=60, minimum_net_reward_to_risk='2',
        fee_per_side='0', exit_slippage='0', exit_full_spread='0')
    values.update(overrides)
    return AllocationPolicy(**values)


def account(**overrides):
    values=dict(mode='counterfactual', equity='1000', settled_cash='1000',
        total_open_risk='0', observed_at=1000, trade_risk_by_symbol={},
        open_symbols=[], new_entries_allowed=True)
    values.update(overrides)
    return values


def candidate(identity='a', symbol='TEST', target='14', **overrides):
    event=dict(event_id=identity, symbol=symbol, setup='initial_breakout',
               available_at=1000, proposed_stop='9')
    provenance=dict(price=target, available_at=990, horizon_minutes=120,
                    source_sha256='a'*64, method_version='synthetic')
    assessment=dict(event_id=identity, event_sha256=fingerprint(event), state='conditional_research_case',
        assessed_at=1000, valid_until=1060, entry_price='10', stop_price='9', target_price=target,
        target_provenance=provenance, target_sha256=fingerprint(provenance))
    group=dict(status='pass', available_at=1000, source_sha256=['a'*64])
    values=dict(event=event, assessment=assessment, evidence_groups=dict(momentum=deepcopy(group),liquidity=deepcopy(group)),
                maximum_quantity_from_liquidity=1000, liquidity_available_at=1000)
    values.update(overrides)
    return values


class AcquisitionTests(unittest.TestCase):
    def plan(self, rows, acc=None, pol=None):
        return plan_acquisitions(rows, acc or account(), pol or policy(), 1000)

    def test_shared_cash_is_not_spent_twice(self):
        result=self.plan([candidate('a','ONE'),candidate('b','TWO')],account(settled_cash='100'))
        self.assertEqual(sum(r['quantity'] for r in result['reviews']),10)
        self.assertEqual(D(result['remaining_settled_cash']),0)
        self.assertEqual(len(result['reviews']),2)

    def test_comparison_reports_roi_dominance_and_no_invented_expected_return(self):
        result=self.plan([candidate('a','ONE',target='13'),candidate('b','TWO',target='15')])
        best=result['comparisons'][0]
        self.assertEqual(best['event_id'],'b')
        self.assertEqual(best['conditionally_dominates'],['a'])
        self.assertIsNone(best['expected_net_return'])
        self.assertEqual(D(result['reviews'][1]['conditional_roi']),D('.5'))

    def test_multiple_indicators_do_not_create_a_confidence_score(self):
        one=candidate(); two=deepcopy(one)
        two['evidence_groups']['duplicate_momentum']=deepcopy(two['evidence_groups']['momentum'])
        self.assertEqual(self.plan([one])['reserved_cash'],self.plan([two])['reserved_cash'])
        self.assertEqual(self.plan([one])['comparisons'][0]['metrics_at_common_initial_budget'],
                         self.plan([two])['comparisons'][0]['metrics_at_common_initial_budget'])

    def test_better_conditional_opportunity_gets_budget_without_using_outcomes(self):
        rows=[candidate('a','ONE',target='13'),candidate('b','TWO',target='15')]
        result=self.plan(rows,account(settled_cash='100'))
        self.assertEqual([r['symbol'] for r in result['reviews'] if r['quantity']],['TWO'])
        rows[0]['future_profit']='99999'
        self.assertEqual(self.plan(rows,account(settled_cash='100'))['reviews'],result['reviews'])

    def test_aggregate_risk_ceiling_is_shared(self):
        result=self.plan([candidate(str(i),str(i)) for i in range(10)])
        self.assertEqual(D(result['total_planned_risk']),D('50'))
        self.assertTrue(all(D(r['planned_risk'])<=10 for r in result['reviews']))

    def test_expensive_ticker_is_preserved_as_track_only(self):
        row=candidate();row['assessment'].update(entry_price='2000',stop_price='9',target_price='10000')
        row['assessment']['target_provenance']['price']='10000'
        row['assessment']['target_sha256']=fingerprint(row['assessment']['target_provenance'])
        result=self.plan([row])
        self.assertEqual(len(result['reviews']),1)
        self.assertEqual(result['reviews'][0]['state'],'track_only')

    def test_missing_failed_and_future_indicators_block_reservation(self):
        for change, reason in ((None,'missing_momentum'),('fail','failed_momentum'),('future','unqualified_momentum')):
            row=candidate()
            if change is None:del row['evidence_groups']['momentum']
            elif change=='fail':row['evidence_groups']['momentum']['status']='fail'
            else:row['evidence_groups']['momentum']['available_at']=1001
            result=self.plan([row])
            self.assertEqual(result['reserved_cash'],'0')
            self.assertIn(reason,result['reviews'][0]['reasons'])

    def test_stale_assessment_and_future_liquidity_do_not_allocate(self):
        row=candidate();row['assessment']['assessed_at']=900
        self.assertEqual(self.plan([row])['reserved_cash'],'0')
        row=candidate(liquidity_available_at=1001)
        self.assertEqual(self.plan([row])['reserved_cash'],'0')

    def test_existing_position_needs_addition_review(self):
        result=self.plan([candidate()],account(open_symbols=['TEST']))
        self.assertIn('existing_or_reserved_position_requires_addition_review',result['reviews'][0]['reasons'])
        self.assertEqual(result['reserved_cash'],'0')

    def test_duplicate_setup_and_changed_stop_are_rejected(self):
        with self.assertRaises(DataError):self.plan([candidate(),candidate()])
        row=candidate();row['event']['proposed_stop']='8'
        with self.assertRaises(DataError):self.plan([row])

    def test_pause_retains_all_candidates_and_cash(self):
        result=self.plan([candidate()],account(new_entries_allowed=False))
        self.assertEqual(result['reserved_cash'],'0')
        self.assertEqual(len(result['reviews']),1)

    def test_fees_can_make_allowed_scale_uneconomic(self):
        result=self.plan([candidate(maximum_quantity_from_liquidity=1)],pol=policy(fee_per_side='1'))
        self.assertEqual(result['reserved_cash'],'0')
        self.assertIn('fees_remove_remaining_opportunity_at_allowed_scale',result['reviews'][0]['reasons'])

    def test_price_ceiling_and_size_retain_structural_stop(self):
        result=self.plan([candidate()])['reviews'][0]
        self.assertEqual(result['quantity'],10)
        self.assertEqual(result['management']['protective_stop'],'9')
        self.assertEqual(D(result['maximum_entry_price']),D(32)/3)
        self.assertFalse(result['recommendation_qualified'])

    def test_live_and_stale_account_are_rejected(self):
        for acc in (account(mode='live'),account(observed_at=900),account(total_open_risk='0',trade_risk_by_symbol={'ONE':'5'})):
            with self.assertRaises(DataError):self.plan([candidate()],acc)

    def test_pipeline_connects_allocation_without_basket_profit_claim(self):
        from test_purpose_pipeline import fixture, policies
        from dataclasses import asdict
        bars,u,q,t,a,b=fixture();s,p,o,r=policies()
        bundle=dict(universe=u,series={'QUIET':[asdict(bar) for bar in bars]},
            selection_policy=asdict(s),setup_policy=asdict(p),opportunity_policy=asdict(o),
            replay_policy=asdict(r),evaluation_start=a,evaluation_end=b,quotes=q,
            target_hypotheses=t,scenario_equity=10000,scenario_settled_cash=10000)
        result=run_bundle(bundle)
        plan=result['acquisition_plan']
        self.assertEqual(len(plan['snapshots']),2)
        self.assertFalse(plan['outcomes_used_for_selection'])
        self.assertIsNone(plan['portfolio_return'])
        self.assertTrue(plan['snapshots'][0]['reviews'][0]['quantity']>0)
        self.assertEqual(plan['snapshots'][1]['reviews'][0]['quantity'],0)
        self.assertFalse(plan['operational_assistant_ready'])


if __name__=='__main__':unittest.main()
