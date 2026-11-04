"""Verify evidence inventory without converting sparse data into validation."""
from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import unittest
from hypothesis_readiness import audit


class ReadinessTests(unittest.TestCase):
    def test_measures_gaps_vwap_and_dates_without_inventing_calendar_or_returns(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'archive.sqlite'
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('create table sources(id,symbol,interval,sha256,row_count)')
                db.execute('insert into sources values(?,?,?,?,?)',('source','TEST','1min','a'*64,3))
                db.execute('create table observations(symbol,interval,timestamp_ms,open,high,low,close,volume,vwap)')
                for stamp,vwap in ((1800000000000,'10'),(1800000060000,None),(1800000180000,'10')):
                    db.execute('insert into observations values(?,?,?,?,?,?,?,?,?)',('TEST','1min',stamp,'10','11','9','10','100',vwap))
            before=path.read_bytes();result=audit(path)
            self.assertEqual(path.read_bytes(),before)
            row=result['coverage'][0]
            self.assertEqual(row['internal_grid_missing_slots'],1)
            self.assertEqual(row['supplied_vwap_rows'],2)
            self.assertEqual(row['observed_session_dates'],1)
            self.assertFalse(row['calendar_qualified'])
            self.assertFalse(result['representative_strategy_study_ready'])
            self.assertEqual(len(result['hypotheses']),18)
            self.assertTrue(all(not h['strategy_validation_ready'] for h in result['hypotheses']))
            relative=next(h for h in result['hypotheses'] if h['id']=='relative_volume')
            self.assertIn('1 observed dates',relative['available'])

    def test_missing_archive_is_not_created_as_empty_success(self):
        with tempfile.TemporaryDirectory() as temp:
            missing=Path(temp)/'missing.sqlite'
            with self.assertRaises(sqlite3.OperationalError):audit(missing)
            self.assertFalse(missing.exists())


if __name__=='__main__':unittest.main()
