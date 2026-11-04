"""Behavioral acceptance: intent, not ticker names or attractive P&L, drives selection."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
import unittest

from discovery_selection import Observation, SelectionPolicy, scan_symbol, study_gate
from replay import DataError


def policy(**changes):
    p = SelectionPolicy('synthetic_acceptance_v1', 1, 2, 3, D('1000'), D('.02'),
                        D('3'), D('100'), 30)
    return replace(p, **changes)


def fixture(baseline=10, burst=100, rising=True, expensive=False):
    records = []
    start = datetime(2026, 11, 2, 14, 30, tzinfo=timezone.utc)
    for day in range(4):
        dt = start + timedelta(days=day)
        for minute in range(6):
            price = D(1000 if expensive else 2)
            if day == 3 and minute >= 3 and rising:
                price *= D('1.03')
            volume = D(burst if day == 3 and minute >= 3 else baseline)
            records.append(Observation(int(dt.timestamp())+minute*60, dt.date().isoformat(),
                                       minute, price, volume, 6))
    return records


class IntentSelectionTests(unittest.TestCase):
    def test_quiet_stock_price_and_activity_burst_is_discovered(self):
        rows = scan_symbol('UNFAMILIAR', fixture(), policy())
        found = [r for r in rows if r['state']=='quiet_to_active_candidate']
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['cohort'], 'quiet')
        self.assertEqual(found[0]['baseline_daily_shares'], '60')
        self.assertEqual(found[0]['recommendation'], 'not_qualified')
        self.assertEqual(found[0]['execution'], 'not_assessed')

    def test_already_busy_stock_is_control_not_target_cohort(self):
        rows = scan_symbol('ACTIVE', fixture(baseline=1000, burst=10000), policy())
        self.assertFalse(any(r['state']=='quiet_to_active_candidate' for r in rows))
        self.assertTrue(any(r['state']=='active_momentum_control' for r in rows))

    def test_price_movement_alone_does_not_establish_activation(self):
        rows = scan_symbol('QUIET', fixture(burst=10), policy())
        self.assertFalse(any(r['state']=='quiet_to_active_candidate' for r in rows))

    def test_volume_burst_without_upward_price_is_not_candidate(self):
        rows = scan_symbol('QUIET', fixture(rising=False), policy())
        self.assertFalse(any(r['state']=='quiet_to_active_candidate' for r in rows))

    def test_small_denominator_does_not_replace_absolute_activity(self):
        rows = scan_symbol('QUIET', fixture(baseline=1, burst=10), policy(minimum_window_dollars=D('10000')))
        self.assertFalse(any(r['state']=='quiet_to_active_candidate' for r in rows))
        self.assertTrue(any('insufficient_absolute_recent_activity' in r['reasons'] for r in rows))

    def test_zero_baseline_is_unknown_not_infinite_volume(self):
        rows = scan_symbol('SPARSE', fixture(baseline=0), policy())
        last = rows[-1]
        self.assertEqual(last['state'], 'insufficient_evidence')
        self.assertIsNone(last['relative_volume'])

    def test_ticker_name_does_not_determine_fit(self):
        rows = scan_symbol('AAPL', fixture(), policy())
        self.assertTrue(any(r['state']=='quiet_to_active_candidate' for r in rows))
        # Eligibility follows evidence even for a familiar name, never a blacklist.

    def test_price_and_account_affordability_do_not_filter_discovery(self):
        rows = scan_symbol('EXPENSIVE', fixture(expensive=True), policy())
        self.assertTrue(any(r['state']=='quiet_to_active_candidate' for r in rows))

    def test_future_bars_do_not_change_past_decisions(self):
        original = fixture()
        a = scan_symbol('QUIET', original, policy())
        future = fixture()[0:6]
        future = [replace(r, timestamp=r.timestamp+4*86400, session='2026-11-06',
                          close=D('99999'), volume=D('99999999')) for r in future]
        b = scan_symbol('QUIET', original+future, policy())
        self.assertEqual(a, b[:len(a)])

    def test_missing_prior_bars_are_not_zero_volume(self):
        records = fixture()
        del records[7]
        rows = scan_symbol('QUIET', records, policy())
        self.assertFalse(any(r['state']=='quiet_to_active_candidate' for r in rows))
        self.assertIn('incomplete_prior_session_coverage', rows[-1]['reasons'])

    def test_missing_current_bar_blocks_affected_window(self):
        records = fixture()
        del records[-3]
        rows = scan_symbol('QUIET', records, policy())
        self.assertIn('missing_current_window_bar', rows[-1]['reasons'])

    def test_unresolved_discontinuity_blocks_candidate(self):
        rows = scan_symbol('QUIET', fixture(), policy(), known_discontinuities=['2026-11-05'])
        self.assertFalse(any(r['state']=='quiet_to_active_candidate' for r in rows))

    def test_bad_dates_duplicate_and_nonfinite_data_rejected(self):
        rows = fixture()
        for broken in (rows+[rows[-1]], [replace(rows[0],session='2026-11-01')],
                       [replace(rows[0],volume=D('NaN'))]):
            with self.assertRaises(DataError):
                scan_symbol('QUIET', broken, policy())

    def test_convenience_roster_and_partial_market_study_are_blocked(self):
        rows = fixture()
        decisions = scan_symbol('QUIET', rows, policy())
        start = rows[-6].timestamp
        gate = study_gate({'symbols':['QUIET','ABSENT'], 'selection_basis':'convenience'},
                          {'QUIET':rows}, start, start+360, decisions, 1)
        self.assertFalse(gate['target_study_ready'])
        self.assertIn('universe_not_independently_sourced', gate['reasons'])
        self.assertEqual(gate['missing_symbols'], ['ABSENT'])

    def test_current_listing_cannot_be_backdated_to_historical_test(self):
        rows = fixture()
        start = rows[-6].timestamp
        universe = {'symbols':['QUIET'], 'selection_basis':'broad_listing_snapshot',
                    'source_sha256':'fixture', 'available_at':start+86400,
                    'instrument_types':{'QUIET':'stock'},
                    'session_windows':[{'open':start,'close':start+360}]}
        gate = study_gate(universe, {'QUIET':rows}, start, start+360,
                          scan_symbol('QUIET', rows, policy()), 1)
        self.assertFalse(gate['target_study_ready'])
        self.assertIn('universe_not_available_at_evaluation_start', gate['reasons'])

    def test_complete_synthetic_target_study_passes_coverage_not_performance(self):
        rows = fixture()
        start = rows[-6].timestamp
        universe = {'symbols':['QUIET'], 'selection_basis':'broad_listing_snapshot',
                    'source_sha256':'fixture', 'available_at':start-86400,
                    'instrument_types':{'QUIET':'stock'},
                    'session_windows':[{'open':start,'close':start+360}]}
        gate = study_gate(universe, {'QUIET':rows}, start, start+360,
                          scan_symbol('QUIET', rows, policy()), 1)
        self.assertTrue(gate['target_study_ready'])
        self.assertFalse(gate['performance_validated'])
        self.assertFalse(gate['live_eligible'])
        del rows[-2]
        broken = study_gate(universe, {'QUIET':rows}, start, start+360, [], 1)
        self.assertFalse(broken['target_study_ready'])


if __name__ == '__main__':
    unittest.main()
