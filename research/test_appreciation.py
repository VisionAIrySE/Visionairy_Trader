import unittest
from appreciation import appreciation_leaders


class AppreciationTests(unittest.TestCase):
    def quote(self,**kw):
        row=dict(session='2026-11-05',security_status='directory_and_broker_common_share_indicated',
            last='12',prevclose='10',open='12.5',received_at=200,trade_at_ms=200000,
            fresh_regular_session=True,volume='10000')
        row.update(kw);return row

    def test_leaders_need_no_prior_scan_or_pattern_and_keep_early_small_gains(self):
        rows=appreciation_leaders({'EARLY':self.quote(last='10.3'),'RUNNER':self.quote()},'2026-11-05')
        self.assertEqual([r['symbol'] for r in rows],['RUNNER','EARLY'])
        self.assertEqual(rows[0]['gain_from_prior_close_pct'],'20.0')
        self.assertEqual(rows[0]['gain_from_open_pct'],'-4.00')
        self.assertIsNone(rows[0]['recent_change_pct'])
        self.assertFalse(rows[0]['recommendation_qualified'])

    def test_recent_change_is_signed_and_cannot_cross_sessions_or_stale_windows(self):
        old=self.quote(last='12.5',received_at=100,trade_at_ms=100000)
        rows=appreciation_leaders({'X':self.quote()},'2026-11-05',{'X':old})
        self.assertEqual(rows[0]['recent_change_pct'],'-4.00')
        for update in ({'session':'2026-11-04'},{'received_at':-500},{'trade_at_ms':200000}):
            prior=dict(old,**update)
            self.assertIsNone(appreciation_leaders({'X':self.quote()},'2026-11-05',{'X':prior})[0]['recent_change_pct'])

    def test_invalid_baselines_other_sessions_and_noncommon_are_not_ranked(self):
        for update in ({'prevclose':'NaN','open':None},{'prevclose':'0','open':None},{'last':True},{'session':'2026-11-04'},
                       {'security_status':'etf_subtype_pending'},{'last':'9'}):
            self.assertEqual(appreciation_leaders({'X':self.quote(**update)},'2026-11-05'),[])
        row=appreciation_leaders({'X':self.quote(fresh_regular_session=False)},'2026-11-05')[0]
        self.assertFalse(row['fresh_regular_session'])

    def test_intraday_recovery_below_prior_close_is_still_discovered(self):
        row=appreciation_leaders({'RECOVERY':self.quote(last='9',prevclose='10',open='8')},'2026-11-05')[0]
        self.assertEqual(row['gain_from_open_pct'],'12.500')
        self.assertEqual(row['gain_from_prior_close_pct'],'-10.0')
        row=appreciation_leaders({'NO_CLOSE':self.quote(prevclose=None,open='10')},'2026-11-05')[0]
        self.assertIsNone(row['gain_from_prior_close_pct'])
