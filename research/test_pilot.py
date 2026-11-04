import unittest
from decimal import Decimal as D
from datetime import datetime,timezone
from pilot_study import canonical_time,rvol_at
from replay import DataError

class PilotTests(unittest.TestCase):
 def test_tick_ms_maps_to_utc(self):
  r={"timestamp":1793716200000,"time":"2026-11-03T14:30:00"}
  self.assertEqual(canonical_time(r,"tick"),1793716200000)
 def test_bar_seconds_et_label_maps_to_same_instant(self):
  r={"timestamp":1793716200,"time":"2026-11-03T09:30:00"}
  self.assertEqual(canonical_time(r,"1min"),1793716200000)
 def test_wrong_units_rejected(self):
  with self.assertRaises(DataError):
   canonical_time({"timestamp":1793716200,"time":"2026-11-03T14:30:00"},"tick")
 def test_prior_only_baseline(self):
  start=1793716200
  rows=[{"timestamp":start+i*60,"time":f"2026-11-03T09:{30+i}:00","volume":100} for i in range(5)]
  past=[{"time":f"2026-10-{10+i:02}T09:30:00","volume":100} for i in range(10)]
  future=[{"time":"2026-11-04T09:30:00","volume":100000}]
  a=rvol_at(4,rows,past)
  b=rvol_at(4,rows,past+future)
  self.assertEqual(a,b)
  self.assertEqual(D(a["value"]),5)
if __name__=="__main__":unittest.main()

