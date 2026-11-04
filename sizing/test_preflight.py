import unittest
from decimal import Decimal as D
from preflight import scenario

class PreflightTests(unittest.TestCase):
    def test_full_roundtrip_spread(self):
        r = scenario(100, 5, "0.002", "0.03", 0)
        self.assertEqual(r["quantity"], 19)
        self.assertEqual(D(r["unchanged_midpoint_roundtrip_loss"]), D("0.190"))
    def test_commission_in_purchase_budget(self):
        r = scenario(25, 5, 0, "0.03", "0.35")
        self.assertEqual(r["quantity"], 4)
        self.assertLessEqual(D(r["entry_cash"]), D(25))
        self.assertEqual(D(r["unchanged_midpoint_roundtrip_loss"]), D("0.70"))
    def test_unaffordable_is_not_fractional(self):
        self.assertEqual(scenario(25, 100, "0.002", "0.03", 0)["status"], "unaffordable")
    def test_break_even_exit_exact(self):
        r = scenario(100, 5, "0.01", "0.03", "0.35")
        q = D(r["quantity"]); g = D(r["break_even_midpoint_rise"])
        proceeds = q * D(5) * (1 + g) * (1 - D("0.01")/2) - D("0.35")
        self.assertAlmostEqual(proceeds, D(r["entry_cash"]), places=20)
    def test_costs_included_in_stop_budget(self):
        r = scenario(100, 5, "0.002", "0.03", "0.35")
        self.assertFalse(r["within_2dollar_loss_budget"])
    def test_bad_spread(self):
        with self.assertRaises(ValueError):
            scenario(100, 5, "-0.01", "0.03", 0)
    def test_more_spread_increases_break_even(self):
        a=scenario(100, 5, "0.002", "0.03", 0)
        b=scenario(100, 5, "0.03", "0.03", 0)
        self.assertGreater(D(b["break_even_midpoint_rise"]),D(a["break_even_midpoint_rise"]))

if __name__ == "__main__":
    unittest.main()

