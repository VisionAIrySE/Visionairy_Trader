from copy import deepcopy
import io
import threading
import unittest
from market_monitor import unpack,ScanCancelled
from replay import DataError
from universe_refresh import UniverseRefresh,current_universe,URLS

NOW=1793914683
NASDAQ=b'Symbol|Security Name|Test Issue|ETF\nAAA|Fixture Common Stock|N|N\nFile Creation Time: 1105202615:41|||\n'
OTHER=b'NASDAQ Symbol|Security Name|Test Issue|ETF\nBBB|Fixture Fund|N|Y\nFile Creation Time: 1105202615:41|||\n'

class RefreshTests(unittest.TestCase):
    def make(self,source=None):
        calls=[];saved=[]
        class Opener:
            def open(self,request,timeout):
                calls.append((request.full_url,request.method,timeout))
                return io.BytesIO((source or {}).get(request.full_url,NASDAQ if request.full_url==URLS['nasdaq'] else OTHER))
        class Store:
            def call(self,op,p):saved.append((op,deepcopy(p)));return {'saved':True}
        return UniverseRefresh(Opener(),now=lambda:NOW,minimum_rows=1),Store(),calls,saved

    def test_refresh_pins_sources_and_saves_current_point_in_time_snapshot(self):
        refresh,store,calls,saved=self.make()
        result=refresh.refresh(store,'2026-11-05')
        self.assertEqual({c[0] for c in calls},set(URLS.values()))
        self.assertTrue(all(c[1]=='GET' and c[2]==8 for c in calls))
        self.assertEqual(result['available_at'],NOW)
        self.assertFalse(result['historical_membership_qualified'])
        self.assertTrue(current_universe(result,'2026-11-05',NOW))
        self.assertEqual(unpack(saved[0][1]['packed_universe']),result)
        self.assertFalse(current_universe(result,'2026-11-06',NOW+86400))
        self.assertFalse(current_universe(result,'2026-11-05',NOW-1))

    def test_stale_or_incomplete_source_does_not_replace_universe(self):
        for broken in (NASDAQ.replace(b'11052026',b'11042026'),b'<html>Unavailable</html>',b'x'*3000001):
            refresh,store,_,saved=self.make({URLS['nasdaq']:broken})
            with self.assertRaises((ValueError,DataError)):refresh.refresh(store,'2026-11-05')
            self.assertEqual(saved,[])
        refresh,store,_,saved=self.make();refresh.minimum_rows=1000
        with self.assertRaises(DataError):refresh.refresh(store,'2026-11-05')
        self.assertEqual(saved,[])

    def test_cancellation_before_refresh_makes_no_requests_or_writes(self):
        refresh,store,calls,saved=self.make();cancel=threading.Event();cancel.set()
        with self.assertRaises(ScanCancelled):refresh.refresh(store,'2026-11-05',cancel)
        self.assertEqual(calls,[]);self.assertEqual(saved,[])
