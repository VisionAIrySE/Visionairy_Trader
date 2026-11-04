from dataclasses import FrozenInstanceError,asdict
import json
import unittest

from decision_analysis import DecisionGraph,ComparisonPlan,compare_decision_paths,digest,DECISIONS
from managed_replay import paper_entry_pause
from purpose_audit import audit
from replay import DataError


def graph_fixture():
    graph=DecisionGraph()
    terms={'price':'2','quantity':10}
    evidence={'source_ids':['synthetic_source'],'actor':'counterfactual_policy'}
    first=graph.record('opportunity',[],'discovery','observe',100,99,terms,evidence,'original')
    review=graph.record('opportunity',[first.decision_id],'entry_review','enter',110,109,terms,evidence,'original')
    execution=graph.record('opportunity',[review.decision_id],'execution','filled',120,120,terms,evidence,'original')
    management=graph.record('opportunity',[execution.decision_id],'exit_review','exit',150,150,terms,evidence,'managed')
    return graph,(first,review,execution,management)


def comparison_fixture():
    graph,records=graph_fixture()
    plan=ComparisonPlan('opportunity',90,100,'USD','common_notional_fixture','original','managed','a'*64)
    paths=('recommendation_baseline','decision_timing_terms','execution_effects','management_effects')
    outcomes={}
    for path,pnl,record in zip(paths,('10','6','5','2'),records):
        outcomes[path]=dict(opportunity_id='opportunity',currency='USD',capital_basis=plan.common_capital_basis,
            status='complete',net_pnl=pnl,available_at=160,evaluation_start=100,evaluation_end=150,
            decision_id=record.decision_id,comparison_plan_sha256=digest(asdict(plan)),
            strategy_version='managed' if path=='management_effects' else 'original',evidence_tier='modeled')
    return graph,plan,outcomes


class DecisionAnalysisTests(unittest.TestCase):
    def test_all_major_position_decisions_have_explicit_types(self):
        self.assertTrue({'entry_review','stop_review','addition_review','partial_exit_review',
            'overnight_review','exit_review','execution','feedback','preference_change','strategy_change',
            'portfolio_risk'}.issubset(DECISIONS))

    def test_records_are_immutable_and_keep_exact_terms(self):
        graph,records=graph_fixture()
        self.assertEqual(json.loads(records[0].terms_json)['quantity'],10)
        with self.assertRaises(FrozenInstanceError):records[0].action='filled'
        self.assertIsInstance(graph.records,tuple)
        self.assertEqual(records[1].previous_hash,records[0].record_hash)

    def test_duplicate_decision_does_not_create_duplicate_action_record(self):
        graph,records=graph_fixture()
        first=records[0]
        same=graph.record('opportunity',[],'discovery','observe',100,99,
             json.loads(first.terms_json),json.loads(first.evidence_json),'original')
        self.assertEqual(same.decision_id,first.decision_id)
        self.assertEqual(len(graph.records),4)

    def test_unlinked_or_future_evidence_is_rejected(self):
        graph,_=graph_fixture()
        for parents,evidence_at in (([],99),(['missing'],99),([],101)):
            with self.assertRaises(DataError):
                graph.record('opportunity',parents,'entry_review','enter',100,evidence_at,{},
                             {'source_ids':['fixture']},'v1')

    def test_parent_from_another_opportunity_is_rejected(self):
        graph,records=graph_fixture()
        with self.assertRaises(DataError):
            graph.record('different',[records[0].decision_id],'entry_review','enter',120,119,{},
                         {'source_ids':['fixture']},'v1')

    def test_attribution_separates_timing_execution_and_management(self):
        graph,plan,outcomes=comparison_fixture()
        result=compare_decision_paths(plan,outcomes,'enter',graph)
        self.assertEqual(result['components'],{'decision_timing_terms':'-4',
                                               'execution_effects':'-1','management_effects':'-3'})
        self.assertEqual(result['total_difference'],'-8')
        self.assertEqual(result['final_path_pnl'],'2')
        self.assertFalse(result['model_update_authorized'])
        self.assertFalse(result['preference_update_authorized'])

    def test_unanswered_declined_expired_and_track_only_are_distinct(self):
        graph,plan,outcomes=comparison_fixture()
        for action in ('decline','no_response','expired','track_only'):
            result=compare_decision_paths(plan,outcomes,action,graph)
            self.assertEqual(result['user_choice'],action)
            self.assertIsNone(result['actual_trade_pnl'])
            self.assertIsNone(result['inferred_preference'])

    def test_censored_outcome_blocks_performance_arithmetic(self):
        graph,plan,outcomes=comparison_fixture()
        outcomes['execution_effects']['status']='censored'
        result=compare_decision_paths(plan,outcomes,'enter',graph)
        self.assertEqual(result['status'],'insufficient_comparison_evidence')

    def test_unmatched_strategy_or_decision_cannot_support_attribution(self):
        for field,value in (('strategy_version','other'),('decision_id','unknown'),('comparison_plan_sha256','wrong')):
            graph,plan,outcomes=comparison_fixture();outcomes['execution_effects'][field]=value
            with self.assertRaises(DataError):compare_decision_paths(plan,outcomes,'enter',graph)

    def test_comparison_cannot_be_declared_after_outcomes_start(self):
        with self.assertRaises(DataError):ComparisonPlan('o',101,100,'USD','basis','v1','v2','hash')

    def test_all_accepted_requirements_remain_visible_and_not_falsely_complete(self):
        report=audit()
        self.assertEqual(report['accepted_items_mapped'],56)
        self.assertFalse(report['operating_platform_ready'])
        self.assertFalse(report['live_eligible'])


class PaperPauseTests(unittest.TestCase):
    def test_three_percent_pause_preserves_discovery_and_existing_protection(self):
        row=paper_entry_pause(10000,9700,0,True,False,'paper')
        self.assertFalse(row['new_entries_allowed']);self.assertFalse(row['additions_allowed'])
        self.assertTrue(row['discovery_continues']);self.assertTrue(row['existing_protection_retained'])
        self.assertFalse(row['forced_liquidation'])

    def test_cash_flow_does_not_create_false_trading_drawdown(self):
        row=paper_entry_pause(10000,9000,-1000,True,False,'paper')
        self.assertTrue(row['new_entries_allowed'])

    def test_session_pause_does_not_clear_after_temporary_recovery(self):
        row=paper_entry_pause(10000,10000,0,True,True,'paper')
        self.assertFalse(row['new_entries_allowed'])

    def test_stale_valuation_blocks_new_exposure(self):
        self.assertFalse(paper_entry_pause(10000,10000,0,False,False,'paper')['new_entries_allowed'])

    def test_paper_daily_pause_is_not_silently_used_live(self):
        with self.assertRaises(DataError):paper_entry_pause(10000,9700,0,True,False,'live')


if __name__=='__main__':unittest.main()
