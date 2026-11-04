import unittest
from results_report import summarize,build

def outcome(event='a',status='modeled',net='0.123456789123456789'):
    row=dict(event_id=event,status=status,session='2026-11-02',symbol='FIXTURE',detector='B01_raw_2pct',
        delay_seconds=60,hold_minutes=15,budget=500,assumed_spread='0.002',assumed_fee='0')
    if status=='modeled':row['net_pnl']=net
    return row

class ReportTests(unittest.TestCase):
    def test_legacy_results_are_withdrawn_as_target_strategy_evidence(self):
        report=build([outcome()])
        self.assertFalse(report['intent_fit'])
        self.assertFalse(report['target_cohort_evidence'])
    def test_zero_signal_rules_are_explicit(self):
        report=build([outcome()])
        empty=next(r for r in report['detectors'] if r['detector']=='B02_aligned_2pct_rvol3')
        self.assertEqual(empty['scenario_rows'],0)
        self.assertIsNone(empty['mean_net_dollars'])
    def test_censored_is_not_a_zero_return(self):
        x=summarize([outcome(),outcome('b','missing_exit')])
        self.assertEqual(x['mean_net_dollars'],'0.123456789123456789')
        self.assertEqual(x['modeled'],1)
        self.assertEqual(x['scenario_rows'],2)
    def test_zero_modeled_has_no_return(self):
        x=summarize([outcome(status='unaffordable_or_activity_cap')])
        self.assertIsNone(x['mean_net_dollars']);self.assertIsNone(x['positive_fraction'])
    def test_reused_event_does_not_create_an_independent_sample(self):
        x=build([outcome(),{**outcome(), 'delay_seconds':120}])
        self.assertEqual(x['total']['event_ids'],1)
        self.assertIsNone(x['independent_sample_count']);self.assertIsNone(x['portfolio_return'])
    def test_sweep_changes_one_factor_only(self):
        x=build([outcome(net='1'),{**outcome(net='2'),'budget':250},
                 {**outcome(net='100'),'budget':250,'delay_seconds':120}])
        budget250=next(r for r in x['sensitivity']['budget'] if r['value']==250)
        self.assertEqual(budget250['mean_net_dollars'],'2')

if __name__=='__main__':unittest.main()
