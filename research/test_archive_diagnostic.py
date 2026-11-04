from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from datetime import datetime,timedelta,timezone

from archive_diagnostic import load_archive,run


class ArchiveDiagnosticTests(unittest.TestCase):
    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'archive.sqlite'
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE sources(id TEXT,symbol TEXT,interval TEXT,sha256 TEXT,row_count INTEGER);
                CREATE TABLE observations(id TEXT,symbol TEXT,interval TEXT,timestamp_ms INTEGER,
                    open TEXT,high TEXT,low TEXT,close TEXT,volume TEXT);
                CREATE TABLE source_observations(source_id TEXT,observation_id TEXT,
                    source_sequence INTEGER,source_time_text TEXT);
            ''')
            db.execute('INSERT INTO sources VALUES (?,?,?,?,?)',('source','TEST','5min','a'*64,858))
            base = datetime(2026,10,1,13,30,tzinfo=timezone.utc)
            for day in range(11):
                for slot in range(78):
                    i = day*78+slot
                    stamp = base+timedelta(days=day,minutes=slot*5)
                    # One upward activation after ten complete prior observed dates.
                    close,volume = ('11','1000') if day == 10 and slot == 1 else ('10','10')
                    db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)',
                        (str(i),'TEST','5min',int(stamp.timestamp()*1000),'10',close,'10',close,volume))
                    label = (stamp-timedelta(hours=4)).replace(tzinfo=None).isoformat()
                    db.execute('INSERT INTO source_observations VALUES (?,?,?,?)',('source',str(i),i,label))
        self.start = int((base+timedelta(days=10)).timestamp())
        self.end = self.start+390*60+1

    def test_repeatable_source_pinned_and_control_only_even_with_candidate(self):
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        a = run(self.path,self.start,self.end)
        self.assertEqual(json.dumps(a,default=str),json.dumps(run(self.path,self.start,self.end),default=str))
        self.assertEqual(before,hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(1,a['experiments'][0]['symbols']['TEST']['states']['quiet_to_active_candidate'])
        self.assertFalse(a['experiments'][0]['study_gate']['target_study_ready'])
        self.assertIsNone(a['portfolio_return'])
        self.assertEqual([],a['financial_outcomes'])
        self.assertEqual(78,len(a['experiments'][0]['decisions']))

    def test_duplicate_import_keeps_provenance_without_multiplying_bars(self):
        with self.connect() as db:
            db.execute("INSERT INTO sources SELECT 'copy',symbol,interval,sha256,row_count FROM sources")
            db.execute("INSERT INTO source_observations SELECT 'copy',observation_id,source_sequence,source_time_text FROM source_observations")
        sources,groups,rows,duplicates = load_archive(self.path)
        self.assertEqual(858,duplicates)
        self.assertEqual(858,len(groups['TEST','5min']))
        self.assertEqual(['copy','source'],rows[0]['source_ids'])

    def test_missing_prior_bar_blocks_activation_without_backfilling(self):
        with self.connect() as db:
            db.execute("DELETE FROM source_observations WHERE observation_id='1'")
            db.execute('UPDATE sources SET row_count=row_count-1')
        result = run(self.path,self.start,self.end)
        summary = result['experiments'][0]['symbols']['TEST']
        self.assertEqual({'insufficient_evidence':78},summary['states'])
        self.assertEqual(77,summary['reasons']['incomplete_prior_session_coverage'])

    def test_conflicting_duplicate_session_label_is_not_silently_selected(self):
        with self.connect() as db:
            db.execute("INSERT INTO sources VALUES ('copy','TEST','5min',?,1)",('b'*64,))
            db.execute("INSERT INTO source_observations VALUES ('copy','0',0,'2026-10-01T10:30:00')")
        with self.assertRaisesRegex(ValueError,'Conflicting'): load_archive(self.path)

    def test_future_bar_changes_manifest_but_not_earlier_decisions(self):
        before = run(self.path,self.start,self.end)
        with self.connect() as db:
            db.execute("UPDATE observations SET high='999',close='999' WHERE id='857'")
        after = run(self.path,self.start,self.end)
        self.assertNotEqual(before['manifest_sha256'],after['manifest_sha256'])
        def early(result):
            return [{k:v for k,v in r.items() if k != 'manifest_sha256'}
                    for r in result['experiments'][0]['decisions'][:-1]]
        self.assertEqual(early(before),early(after))

    def test_count_mismatch_and_clock_conflict_rejected(self):
        with self.connect() as db:
            db.execute('UPDATE sources SET row_count=1')
        with self.assertRaisesRegex(ValueError,'membership count'): load_archive(self.path)
        with self.connect() as db:
            db.execute('UPDATE sources SET row_count=858')
            db.execute("UPDATE source_observations SET source_time_text='2026-10-01T12:30:00' WHERE source_sequence=0")
        with self.assertRaisesRegex(ValueError,'UTC epoch'): load_archive(self.path)

    def test_empty_evaluation_rejected_and_missing_file_not_created(self):
        with self.assertRaises(ValueError): run(self.path,self.start,self.start)
        missing = self.path.with_name('missing.sqlite')
        with self.assertRaises(sqlite3.OperationalError): load_archive(missing)
        self.assertFalse(missing.exists())


if __name__ == '__main__': unittest.main()
