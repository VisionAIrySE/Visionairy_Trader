"""Synthetic acceptance cases, never evidence of profitable market decisions."""
from dataclasses import replace
from decimal import Decimal as D
import unittest

from acquisition_funnel import plan_research_series
from managed_replay import replay_case
from purpose_pipeline import run_research
from replay import DataError
from setup_detection import MarketBar
from test_purpose_pipeline import fixture, policies


class AllocationReplayTests(unittest.TestCase):
    def inputs(self, cash=10000):
        bars,u,q,t,a,b=fixture();s,p,o,r=policies()
        result=run_research(u,{'QUIET':bars},s,p,o,r,a,b,q,t,10000,cash)
        reservation=result['acquisition_plan']['snapshots'][0]['reviews'][0]
        return bars,u,result['setups'][0],result['assessments'][0],r,reservation,result

    def replay(self, bars,u,event,assessment,r,reservation):
        return replay_case(event,assessment,bars,u['session_windows'],r,10000,
                           D(reservation['entry_cash']),reservation=reservation)

    def test_joined_outcomes_follow_selection_not_independent_case_count(self):
        *_,result=self.inputs()
        self.assertEqual(len(result['outcomes']),2)
        rows=result['acquisition_outcomes']['outcomes']
        self.assertEqual([r['status'] for r in rows],['modeled','not_selected_by_acquisition_plan'])
        self.assertIsNone(rows[1]['net_pnl'])
        self.assertIsNone(result['acquisition_outcomes']['portfolio_return'])
        self.assertEqual(result['acquisition_outcomes']['orders_submitted'],0)

    def test_entry_price_increase_cannot_overspend_reserved_cash_or_risk(self):
        bars,u,e,a,r,res,_=self.inputs()
        i=next(i for i,b in enumerate(bars) if b.timestamp==e['available_at'])
        bars[i]=replace(bars[i],open=D('2.205'),high=D('2.21'))
        row=self.replay(bars,u,e,a,r,res)
        self.assertEqual(row['status'],'modeled')
        self.assertLessEqual(row['quantity'],res['quantity'])
        self.assertLessEqual(D(row['entry_cash']),D(res['entry_cash']))
        self.assertLessEqual(D(row['planned_risk']),D(res['planned_risk']))
        self.assertLess(row['quantity'],res['quantity'])

    def test_better_entry_does_not_silently_increase_reserved_quantity(self):
        bars,u,e,a,r,res,_=self.inputs()
        i=next(i for i,b in enumerate(bars) if b.timestamp==e['available_at'])
        bars[i]=replace(bars[i],open=D('2.09'))
        row=self.replay(bars,u,e,a,r,res)
        self.assertEqual(row['quantity'],res['quantity'])

    def test_price_above_ceiling_is_nonfill_even_with_looser_replay_ratio(self):
        bars,u,e,a,r,res,_=self.inputs()
        i=next(i for i,b in enumerate(bars) if b.timestamp==e['available_at'])
        price=D(res['maximum_entry_price'])+D('.001')
        bars[i]=replace(bars[i],open=price,high=price+D('.01'),low=price-D('.01'),close=price)
        row=self.replay(bars,u,e,a,replace(r,maximum_entry_change=D('.9'),minimum_net_reward_to_risk=D('.1')),res)
        self.assertEqual(row['status'],'not_filled_acquisition_price_ceiling')
        self.assertIsNone(row['net_pnl'])
        self.assertNotIn('quantity',row)

    def test_changed_assessment_or_costs_cannot_reuse_reservation(self):
        bars,u,e,a,r,res,_=self.inputs()
        for changed_a,changed_r in ((dict(a,valid_until=a['valid_until']+60),r),
                                   (a,replace(r,fee_per_side=D('.35')))):
            with self.assertRaises(DataError):self.replay(bars,u,e,changed_a,changed_r,res)

    def test_fixed_fees_and_smaller_fill_recheck_allocation_ratio(self):
        bars,u,e,a,r,res,result=self.inputs()
        _,_,o,_=policies()
        r=replace(r,fee_per_side=D('.1'))
        plan=plan_research_series(result['setups'],result['assessments'],{'QUIET':bars},
                                 u['source_sha256'],10000,10000,o,r)
        res=plan['snapshots'][0]['reviews'][0]
        i=next(i for i,b in enumerate(bars) if b.timestamp==e['available_at'])
        # One-share liquidity leaves the two fixed fees payable on one share.
        bars[i-1]=replace(bars[i-1],volume=D(10))
        row=self.replay(bars,u,e,a,replace(r,minimum_net_reward_to_risk=D('.1')),res)
        self.assertEqual(row['status'],'track_only_insufficient_edge_after_entry_delay')
        self.assertIsNone(row['net_pnl'])

    def test_nonreservation_and_future_reservation_are_rejected(self):
        bars,u,e,a,r,res,_=self.inputs()
        for change in (dict(state='track_only'),dict(reserved_at=a['valid_until']+1),dict(quantity=0)):
            with self.assertRaises(DataError):self.replay(bars,u,e,a,r,dict(res,**change))

    def test_insufficient_cash_preserves_discovery_without_modeled_allocated_profit(self):
        *_,result=self.inputs(cash=1)
        self.assertEqual(sum(result['setup_counts'].values()),2)
        self.assertTrue(all(r['status']=='not_selected_by_acquisition_plan'
                            for r in result['acquisition_outcomes']['outcomes']))

    def test_competing_symbols_cannot_both_replay_independent_cash_budget(self):
        bars,u,q,t,start,end=fixture();s,p,o,r=policies()
        u['symbols'].append('OTHER');u['instrument_types']['OTHER']='stock'
        q += [dict(x,symbol='OTHER') for x in q]
        t += [dict(x,symbol='OTHER') for x in t]
        result=run_research(u,{'QUIET':bars,'OTHER':bars},s,p,o,r,start,end,q,t,10000,10)
        rows=result['acquisition_outcomes']['outcomes']
        selected=[x for x in rows if x.get('quantity',0)]
        self.assertEqual(len(selected),1)
        self.assertLessEqual(sum(D(x['entry_cash']) for x in selected),10)
        self.assertEqual(len(rows),4)

    def test_future_exit_changes_do_not_change_allocations(self):
        bars,u,e,a,r,res,result=self.inputs()
        s,p,o,_=policies()
        before=result['acquisition_plan']
        i=next(i for i,b in enumerate(bars) if b.timestamp==e['available_at']+120*60)
        bars[i]=replace(bars[i],open=D('1.5'),low=D('1.49'),high=D('1.51'),close=D('1.5'))
        after=plan_research_series(result['setups'],result['assessments'],{'QUIET':bars},
                                  u['source_sha256'],10000,10000,o,r)
        self.assertEqual(before,after)
        self.assertNotEqual(result['acquisition_outcomes']['outcomes'][0]['net_pnl'],
                            self.replay(bars,u,e,a,r,res)['net_pnl'])

    def test_censored_exit_does_not_become_zero_profit_or_release_reservation(self):
        bars,u,e,a,r,res,_=self.inputs()
        i=next(i for i,b in enumerate(bars) if b.timestamp==e['available_at']+120*60)
        bars[i-1]=replace(bars[i-1],volume=D(0))
        row=self.replay(bars,u,e,a,r,res)
        self.assertEqual(row['status'],'censored_exit_activity')
        self.assertIsNone(row['net_pnl'])
        self.assertEqual(row['reservation_sha256'],self.replay(bars,u,e,a,r,res)['reservation_sha256'])

    def test_reserved_position_holds_across_sessions_and_preserves_gap_loss(self):
        bars,u,e,a,r,res,_=self.inputs()
        next_open=u['session_windows'][0]['open']+86400
        u['session_windows'].append(dict(open=next_open,close=next_open+180*60))
        extra=[MarketBar(next_open+i*60,'2026-11-06',i,D('2.18'),D('2.19'),
                         D('2.17'),D('2.18'),D(100),180) for i in range(180)]
        long_policy=replace(r,holding_trading_minutes=300)
        row=self.replay(bars+extra,u,e,a,long_policy,res)
        self.assertEqual(row['status'],'modeled')
        self.assertEqual(row['observed_trading_minutes'],300)
        self.assertGreaterEqual(row['exit_at'],next_open)
        extra[0]=replace(extra[0],open=D('1.5'),high=D('1.51'),low=D('1.49'),close=D('1.5'))
        loss=self.replay(bars+extra,u,e,a,long_policy,res)
        self.assertEqual(loss['exit_reason'],'gap_through_stop')
        self.assertGreater(-D(loss['net_pnl']),D(res['planned_risk']))


if __name__=='__main__':unittest.main()
