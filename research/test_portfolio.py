"""Paper-account mechanics using synthetic paths, no profitability claims."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal as D
import unittest

from acquisition_funnel import plan_acquisitions
from management_replay import ManagementPolicy, replay_management
from portfolio_ledger import PaperLedger
from portfolio_replay import replay_portfolio, compare_management
from replay import DataError
from test_acquisition_funnel import candidate,policy
import test_allocation_replay as allocation_fixtures
from test_purpose_pipeline import policies


class LedgerTests(unittest.TestCase):
    def ledger(self):return PaperLedger(1000,[dict(open=1000,close=2000),dict(open=3000,close=4000)],1,'test')
    def reserve(self,ledger):
        row=plan_acquisitions([candidate()],ledger.snapshot(60),policy(),1000)['reviews'][0]
        ledger.reserve(row);return row

    def test_reservation_is_idempotent_and_does_not_reduce_equity(self):
        ledger=self.ledger();r=self.reserve(ledger);ledger.reserve(r)
        self.assertEqual(ledger.equity(),1000);self.assertEqual(ledger.available_cash(),900)
        self.assertEqual(len(ledger.events),1)

    def test_entry_cannot_exceed_reservation_or_repeat(self):
        ledger=self.ledger();r=self.reserve(ledger)
        with self.assertRaises(DataError):ledger.enter(r['event_id'],11,10,0,11)
        self.assertTrue(ledger.enter(r['event_id'],10,10,0,10))
        with self.assertRaises(DataError):ledger.enter(r['event_id'],10,10,0,10)

    def test_sale_proceeds_stay_unspendable_until_explicit_session_settlement(self):
        ledger=self.ledger();r=self.reserve(ledger);ledger.enter(r['event_id'],10,10,0,10)
        ledger.advance(1100);ledger.exit('TEST',10,12,0,'test')
        self.assertEqual(ledger.available_cash(),900);self.assertEqual(ledger.equity(),1020)
        ledger.advance(2999);self.assertEqual(ledger.available_cash(),900)
        ledger.advance(3000);self.assertEqual(ledger.available_cash(),1020)

    def test_partial_exit_preserves_remaining_basis_risk_and_quantity(self):
        ledger=self.ledger();r=self.reserve(ledger);ledger.enter(r['event_id'],10,10,0,10)
        ledger.exit('TEST',4,12,0,'partial')
        p=ledger.positions['TEST'];self.assertEqual(p['quantity'],6)
        self.assertEqual(p['entry_cost'],60);self.assertEqual(p['planned_risk'],6)
        self.assertEqual(ledger.realized,8)
        with self.assertRaises(DataError):ledger.exit('TEST',7,12,0,'oversell')

    def test_stale_and_future_marks_cannot_open_new_exposure(self):
        ledger=self.ledger();r=self.reserve(ledger);ledger.enter(r['event_id'],10,10,0,10)
        ledger.advance(1100)
        with self.assertRaises(DataError):ledger.mark('TEST',12,1101)
        self.assertFalse(ledger.snapshot(60)['new_entries_allowed'])
        ledger.mark('TEST',12,1100)
        self.assertFalse(ledger.snapshot(60)['new_entries_allowed'])

    def test_daily_drawdown_latches_without_liquidating_protection(self):
        ledger=self.ledger();r=self.reserve(ledger);ledger.enter(r['event_id'],10,10,0,10)
        ledger.mark('TEST',6,1000)
        self.assertFalse(ledger.snapshot(60)['new_entries_allowed'])
        ledger.mark('TEST',11,1000)
        self.assertFalse(ledger.snapshot(60)['new_entries_allowed'])
        self.assertIn('TEST',ledger.positions)

    def test_bad_exit_and_reverse_time_do_not_mutate_finances(self):
        ledger=self.ledger();r=self.reserve(ledger);ledger.enter(r['event_id'],10,10,0,10)
        ledger.advance(2100);before=ledger.report()
        with self.assertRaises(DataError):ledger.exit('TEST',10,11,0,'out_of_session')
        self.assertEqual(before,ledger.report())
        with self.assertRaises(DataError):ledger.advance(2000)

    def test_live_mode_and_invented_instant_settlement_are_rejected(self):
        for lag,mode in ((0,'paper'),(1,'live')):
            with self.assertRaises(DataError):PaperLedger(1000,[dict(open=1,close=2)],lag,'x',mode)


class JointReplayTests(unittest.TestCase):
    def inputs(self):return allocation_fixtures.AllocationReplayTests().inputs()
    def joint(self,management=None,bars_override=None):
        bars,u,e,a,r,res,result=self.inputs();_,_,o,_=policies()
        return replay_portfolio(result['setups'],result['assessments'],{'QUIET':bars_override or bars},
            u['session_windows'],u['source_sha256'],10000,10000,o,r,1,management or ManagementPolicy('hold'))

    def test_joint_cash_risk_and_pnl_reconcile(self):
        result=self.joint();ledger=result['ledger']
        self.assertEqual(result['status'],'joint_counterfactual_closed')
        self.assertEqual(D(ledger['marked_equity']),D('10000.80'))
        self.assertEqual(D(ledger['settled_cash'])+D(ledger['unsettled_proceeds']),D(ledger['marked_equity']))
        self.assertEqual(result['outcome_counts'],{'modeled':1,'not_selected_by_joint_plan':1})
        self.assertTrue(all(D(v['available_cash'])>=0 for v in result['valuations']))
        self.assertEqual(result['orders_submitted'],0)

    def test_completed_exit_can_release_symbol_but_not_unsettled_money(self):
        result=self.joint(ManagementPolicy('tight_trail',trail_distance_r=D('.1')))
        kinds=[e['kind'] for e in result['ledger']['events']]
        self.assertIn('modeled_exit',kinds)
        self.assertTrue(all(D(v['available_cash'])<=10000 for v in result['valuations']))

    def test_partial_profit_and_unchanged_path_are_alternatives(self):
        bars,u,e,a,r,res,result=self.inputs();_,_,o,_=policies()
        compared=compare_management(result['setups'],result['assessments'],{'QUIET':bars},
            u['session_windows'],u['source_sha256'],10000,10000,o,r,1,
            [dict(version='hold'),dict(version='partial',partial_at_r='.5')])
        hold,partial=compared['variants']
        fills=partial['outcomes'][0]['fills']
        self.assertEqual(fills[0]['reason'],'partial_profit')
        self.assertEqual(sum(f['quantity'] for f in fills),partial['outcomes'][0]['quantity'])
        self.assertFalse(compared['automatic_strategy_adoption'])
        self.assertNotEqual(hold['ledger']['realized_net_pnl'],partial['ledger']['realized_net_pnl'])

    def test_tightening_uses_completed_bar_and_never_widens(self):
        bars,u,e,a,r,res,_=self.inputs()
        row=replay_management(e,a,bars,u['session_windows'],r,10000,res,ManagementPolicy('trail',trail_distance_r='.5'))
        for change in row['stop_changes']:
            self.assertGreater(D(change['new_stop']),D(change['old_stop']))
            self.assertGreater(change['available_at'],e['available_at'])

    def test_censored_position_has_no_complete_account_return(self):
        bars,u,e,a,r,res,_=self.inputs()
        i=next(i for i,b in enumerate(bars) if b.timestamp==e['available_at']+120*60)
        bars[i-1]=replace(bars[i-1],volume=D(0))
        result=self.joint(bars_override=bars)
        self.assertEqual(result['status'],'joint_counterfactual_incomplete')
        self.assertIsNone(result['net_account_return'])
        self.assertIn('QUIET',result['ledger']['positions'])

    def test_future_price_perturbation_does_not_change_prior_allocations(self):
        before=self.joint();bars,u,e,a,r,res,_=self.inputs()
        index=next(i for i,b in enumerate(bars) if b.timestamp==e['available_at']+100*60)
        bars[index]=replace(bars[index],open=D('1.5'),high=D('1.51'),low=D('1.49'),close=D('1.5'))
        after=self.joint(bars_override=bars)
        cutoff=e['available_at']+100*60
        self.assertEqual([s for s in before['snapshots'] if s['assessed_at']<cutoff],
                         [s for s in after['snapshots'] if s['assessed_at']<cutoff])


if __name__=='__main__':unittest.main()
