from pathlib import Path
import tempfile
import unittest
from universe_snapshot import parse_directory,snapshot


NASDAQ='Symbol|Security Name|Test Issue|ETF\nQUIET|Quiet Company|N|N\nACTIVE|Active Company|N|N\nTEST|Test issue|Y|N\nFile Creation Time: fixture|||\n'
OTHER='NASDAQ Symbol|Security Name|Test Issue|ETF\nFUND|Fund|N|Y\nFile Creation Time: fixture|||\n'


class UniverseTests(unittest.TestCase):
    def test_broad_membership_does_not_preselect_active_or_affordable_names(self):
        rows,_=parse_directory(NASDAQ,'nasdaq')
        self.assertEqual([r['symbol'] for r in rows],['QUIET','ACTIVE'])
        self.assertTrue(all(r['instrument_type']=='unqualified' for r in rows))

    def test_truncated_or_changed_schema_rejected(self):
        for text in (NASDAQ.replace('File Creation Time: fixture|||\n',''),NASDAQ.replace('Test Issue','Bad')):
            with self.assertRaises(ValueError):parse_directory(text,'nasdaq')

    def test_snapshot_preserves_as_of_and_unqualified_status(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=Path(folder)/'a',Path(folder)/'b'
            a.write_text(NASDAQ);b.write_text(OTHER)
            result=snapshot(a,b,1793716200)
            self.assertEqual(result['available_at'],1793716200)
            self.assertEqual(len(result['symbols']),3)
            self.assertFalse(result['historical_membership_qualified'])
            self.assertFalse(result['market_data_coverage'])
            self.assertEqual(result['instrument_types']['FUND'],'etf')
