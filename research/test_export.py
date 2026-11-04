import unittest
from export_supabase import batch_sql,stable,iso,canon

class ExportTests(unittest.TestCase):
    def test_deterministic_namespaced_identity(self):
        self.assertEqual(stable('source','abc'),stable('source','abc'))
        self.assertNotEqual(stable('source','abc'),stable('observation','abc'))
    def test_exact_decimal_strings_survive(self):
        self.assertIn('0.123456789123456789',canon({'pnl':'0.123456789123456789'}))
        with self.assertRaises(ValueError):canon({'pnl':float('nan')})
    def test_composite_resume_keys_precede_conflict_trigger(self):
        sql=batch_sql('dataset_sources',[dict(dataset_id='a',source_id='b')])
        self.assertIn('where not exists',sql)
        self.assertIn('d.dataset_id=s.dataset_id and d.source_id=s.source_id',sql)
    def test_schema_is_allowlisted(self):
        with self.assertRaises(ValueError):batch_sql('users; drop table',[])
        with self.assertRaises(ValueError):batch_sql('dataset_sources',[{'source_id':'a'}])
    def test_epoch_units_and_sql_quotes(self):
        self.assertEqual(iso(1793716200000),'2026-11-03T14:30:00+00:00')
        sql=batch_sql('dataset_sources',[dict(dataset_id="a'b",source_id='c')])
        self.assertIn("a''b",sql)

if __name__=='__main__':unittest.main()
