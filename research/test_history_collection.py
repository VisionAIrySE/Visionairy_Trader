import unittest
from history_collection import plan


class CollectionPlanTests(unittest.TestCase):
    def snapshot(self):
        return dict(symbols=['TEST','OTHER','THIRD','UNMAPPED^'],source_sha256='a'*64,available_at=1800000000)
    def build(self,**kw):return plan(self.snapshot(),'2026-10-01 09:30','2026-11-03 16:00',**kw)
    def test_reproducible_without_prices_and_no_backdated_qualification(self):
        a=self.build(sample_size=2)
        self.assertEqual(a,self.build(sample_size=2));self.assertEqual([],a['price_or_outcome_filters'])
        self.assertFalse(a['historical_membership_qualified']);self.assertFalse(a['replacement_on_failure'])
    def test_increasing_sample_preserves_original_choices(self):
        a=self.build(sample_size=2);b=self.build(sample_size=4)
        self.assertEqual(a['selected_symbols'],b['selected_symbols'][:2])
    def test_mapping_failure_retained_not_replaced_and_controls_explicit(self):
        a=self.build(sample_size=4,controls=['CONTROL'])
        self.assertEqual(5,len(a['requests']))
        blocked=next(r for r in a['requests'] if r['query']['symbol']=='UNMAPPED^')
        self.assertEqual('blocked_symbol_mapping',blocked['status'])
        self.assertEqual(['preserved_archive_control'],next(r for r in a['requests'] if r['query']['symbol']=='CONTROL')['roles'])
    def test_unbounded_sample_and_duplicate_membership_rejected(self):
        with self.assertRaises(ValueError):self.build(sample_size=1000)
        s=self.snapshot();s['symbols'].append('TEST')
        with self.assertRaises(ValueError):plan(s,'2026-10-01 09:30','2026-11-03 16:00')


if __name__=='__main__':unittest.main()
