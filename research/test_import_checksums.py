from decimal import Decimal
import unittest

from import_checksums import pg_json, typed_row, checksum_sql, finalization_sql


class ImportChecksumTests(unittest.TestCase):
    def test_postgres_jsonb_key_order_and_decimal_precision(self):
        self.assertEqual(pg_json({'aa': Decimal('0.123456789123456789'), 'z': "a'b"}),
                         '{"z": "a\'b", "aa": 0.123456789123456789}')
        self.assertNotEqual(pg_json({'n': Decimal('1.000000000000001')}), pg_json({'n': Decimal('1')}))

    def test_jsonb_unicode_and_null_preserved(self):
        self.assertEqual(pg_json({'�': [None, True, 'line\nbreak']}),
                         '{"�": [null, true, "line\\nbreak"]}')

    def test_timestamp_offsets_normalize_to_same_instant(self):
        row = dict(id='a', provider='p', source_key='s', sha256='h', instrument_id='i',
                   interval_label='1min', received_at='2026-11-03T09:30:00.120000-05:00',
                   row_count=1, source_metadata={})
        self.assertEqual(typed_row('sources', row)['received_at'], '2026-11-03T14:30:00.12+00:00')
        row['received_at'] = '2026-11-03T09:30:00'
        with self.assertRaises(ValueError):
            typed_row('sources', row)

    def test_untrusted_table_or_incomplete_completion_rejected(self):
        with self.assertRaises(ValueError):
            checksum_sql('users')
        with self.assertRaises(ValueError):
            finalization_sql({}, 'delete from trader.runs;')


if __name__ == '__main__':
    unittest.main()
