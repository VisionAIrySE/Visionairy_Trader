from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
import unittest

from collection_diagnostic import calendar_sessions
from discovery_selection import Observation,SelectionPolicy,scan_symbol
from replay import DataError


class CalendarDiagnosticTests(unittest.TestCase):
    def calendar(self,rows):return [dict(status='observed',payload={'calendar':{'days':{'day':rows}}})]
    def test_missing_calendar_day_is_not_inferred_closed(self):
        rows=[dict(date='2026-10-01',status='closed')]
        with self.assertRaisesRegex(ValueError,'Missing calendar date'):
            calendar_sessions(self.calendar(rows),'2026-10-01 09:30','2026-10-02 16:00')
    def test_closed_and_short_session_lengths_are_explicit(self):
        rows=[dict(date='2026-10-01',status='closed'),
              dict(date='2026-10-02',status='open',open={'start':'09:30','end':'13:00'})]
        self.assertEqual({'2026-10-02':210},calendar_sessions(self.calendar(rows),'2026-10-01 09:30','2026-10-02 16:00'))
    def test_conflicting_calendar_revisions_rejected(self):
        rows=[dict(date='2026-10-01',status='closed'),dict(date='2026-10-01',status='open')]
        with self.assertRaisesRegex(ValueError,'Conflicting calendar'):
            calendar_sessions(self.calendar(rows),'2026-10-01 09:30','2026-10-01 16:00')
    def test_entire_missing_session_cannot_be_skipped_for_older_baseline(self):
        base=datetime(2026,10,1,13,30,tzinfo=timezone.utc);bars=[]
        sessions=[(base+timedelta(days=i)).date().isoformat() for i in range(4)]
        for day in (0,2,3):
            for slot in range(78):
                stamp=base+timedelta(days=day,minutes=slot*5)
                bars.append(Observation(int(stamp.timestamp()),sessions[day],slot*5,D(10),D(10)))
        policy=SelectionPolicy('calendar_gap_test',5,1,2,D(500000),D('.02'),D(3),D(10000),30)
        legacy=scan_symbol('TEST',bars,policy)
        guarded=scan_symbol('TEST',bars,policy,expected_sessions=sessions)
        a=[r for r in legacy if r['session']==sessions[-1]][1]
        b=[r for r in guarded if r['session']==sessions[-1]][1]
        self.assertEqual('quiet',a['cohort'])
        self.assertEqual('unknown',b['cohort'])
        self.assertEqual(['incomplete_prior_session_coverage'],b['reasons'])
        with self.assertRaises(DataError):scan_symbol('TEST',bars,policy,expected_sessions=sessions[::-1])


if __name__=='__main__':unittest.main()
