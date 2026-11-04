import tempfile
import unittest
from pathlib import Path

from export_supabase import batch_sql
from verify_import import read_batch, verified_batch_sql


class ImportVerificationTests(unittest.TestCase):
    def test_roundtrip_preserves_sql_quotes_and_exact_decimals(self):
        # Read through the actual exported SQL format, including doubled quotes.
        rows = [dict(dataset_id="a'b", source_id='0.123456789123456789')]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'batch.sql'
            path.write_text(batch_sql('dataset_sources', rows))
            self.assertEqual(read_batch(path, 'dataset_sources'), rows)

    def test_conflict_does_not_silently_pass_changed_payload(self):
        sql = verified_batch_sql('dataset_sources', [dict(dataset_id='a', source_id='b')])
        self.assertIn('is distinct from', sql)
        self.assertIn('missing<>0 or mismatched<>0', sql)
        self.assertIn('raise exception', sql)
        self.assertIn('d.dataset_id=s.dataset_id and d.source_id=s.source_id', sql)

    def test_unknown_table_and_reserved_delimiter_rejected(self):
        with self.assertRaises(ValueError):
            verified_batch_sql('other', [{'id': 'x'}])
        with self.assertRaises(ValueError):
            verified_batch_sql('dataset_sources', [dict(dataset_id='$verify_import$', source_id='b')])

    def test_duplicate_identity_rejected(self):
        row = dict(dataset_id='a', source_id='b')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'batch.sql'
            path.write_text(batch_sql('dataset_sources', [row, row]))
            with self.assertRaises(ValueError):
                read_batch(path, 'dataset_sources')


if __name__ == '__main__':
    unittest.main()
