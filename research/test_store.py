import json,tempfile,unittest
from pathlib import Path
from research_store import ResearchStore

class StoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.s=ResearchStore(self.root/"test.sqlite")
 def tearDown(self):
  self.s.close();self.tmp.cleanup()
 def source(self,filename="source.json",close=100,interval="1min"):
  row=dict(timestamp=1793716200000 if interval=="tick" else 1793716200,
           time="2026-11-03T09:30:00",open=100,high=101,low=99,close=close,
           price=100,volume=10)
  p=self.root/filename;p.write_text(json.dumps({"series":{"data":[row]}}))
  return p
 def test_duplicate_file_import_is_idempotent(self):
  p=self.source();self.s.import_source(p,"SPY","1min",p.name)
  self.s.import_source(p,"SPY","1min",p.name)
  self.assertEqual(self.s.stats()["observations"],1)
  self.assertEqual(self.s.stats()["sources"],1)
 def test_duplicate_market_data_keeps_both_provenances(self):
  a=self.source();b=self.source("copy.json")
  for p in [a,b]:self.s.import_source(p,"SPY","1min",p.name)
  self.assertEqual(self.s.stats()["observations"],1)
  self.assertEqual(self.s.stats()["sources"],2)
 def test_changed_source_retains_revision(self):
  p=self.source();self.s.import_source(p,"SPY","1min",p.name)
  p=self.source(close=101);self.s.import_source(p,"SPY","1min",p.name)
  self.assertEqual(self.s.stats()["observations"],2)
  self.assertEqual(self.s.stats()["sources"],2)
 def test_invalid_run_rolls_back(self):
  event=dict(event_id="e1",symbol="SPY",detector="B01",available_epoch=1793716260)
  bad=dict(event_id="missing",delay_seconds=0,hold_minutes=5,budget=100,
           assumed_spread=".002",assumed_fee=".35",status="missing_exit")
  with self.assertRaises(Exception):self.s.import_run({},[event],[bad],[],[],b"code")
  self.assertEqual(self.s.stats()["runs"],0)
  self.assertEqual(self.s.stats()["events"],0)
 def test_scenarios_are_shared(self):
  events=[dict(event_id="e"+str(i),symbol="SPY",detector="B01",available_epoch=1793716260) for i in range(2)]
  outcomes=[dict(event_id=e["event_id"],delay_seconds=0,hold_minutes=5,budget=100,
      assumed_spread=".002",assumed_fee=".35",status="modeled",quantity=1,net_pnl="1.01") for e in events]
  self.s.import_run({},events,outcomes,[],[],b"code")
  self.assertEqual(self.s.stats()["scenarios"],1)
  self.assertEqual(self.s.stats()["outcomes"],2)
 def test_online_backup_includes_committed_data(self):
  p=self.source();self.s.import_source(p,"SPY","1min",p.name)
  self.s.snapshot(self.root/"backup.sqlite")
  b=ResearchStore(self.root/"backup.sqlite")
  try:self.assertEqual(b.stats()["observations"],1)
  finally:b.close()
 def test_tick_ms_preserved(self):
  p=self.source(interval="tick");self.s.import_source(p,"SPY","tick",p.name)
  self.assertEqual(self.s.db.execute("SELECT timestamp_ms FROM observations").fetchone()[0],1793716200000)
 def test_run_is_pinned_to_original_data_after_revision(self):
  p=self.source();s1=self.s.import_source(p,"SPY","1min",p.name)["source_id"]
  run=self.s.import_run({},[],[],[],[s1],b"code")
  p=self.source(close=101);self.s.import_source(p,"SPY","1min",p.name)
  rows=self.s.read_run_observations(run,"SPY","1min",0,9999999999999)
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0][5],"100")
 def test_conflicting_revisions_are_flagged(self):
  p=self.source();s1=self.s.import_source(p,"SPY","1min",p.name)["source_id"]
  p=self.source(close=101);s2=self.s.import_source(p,"SPY","1min",p.name)["source_id"]
  run=self.s.import_run({},[],[],[],[s1,s2],b"code")
  with self.assertRaises(ValueError):self.s.read_run_observations(run,"SPY","1min",0,9999999999999)
 def test_symbol_range_uses_index(self):
  plan=self.s.db.execute("EXPLAIN QUERY PLAN SELECT close FROM observations WHERE symbol=? AND interval=? AND timestamp_ms BETWEEN ? AND ?",("SPY","1min",0,9999999999999)).fetchall()
  self.assertTrue(any("observation_symbol_time" in x[3] for x in plan))
if __name__=="__main__":unittest.main()

