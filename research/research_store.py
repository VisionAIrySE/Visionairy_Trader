"""Local SQLite research store. No network or credentials."""
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(
 id TEXT PRIMARY KEY, relative_path TEXT NOT NULL, sha256 TEXT NOT NULL,
 symbol TEXT NOT NULL, interval TEXT NOT NULL, imported_at TEXT NOT NULL,
 row_count INTEGER NOT NULL, UNIQUE(relative_path,sha256));
CREATE TABLE IF NOT EXISTS observations(
 id TEXT PRIMARY KEY, symbol TEXT NOT NULL, interval TEXT NOT NULL,
 timestamp_ms INTEGER NOT NULL, open TEXT, high TEXT, low TEXT, close TEXT,
 price TEXT, volume TEXT NOT NULL, vwap TEXT);
CREATE INDEX IF NOT EXISTS observation_symbol_time
 ON observations(symbol,interval,timestamp_ms);
CREATE INDEX IF NOT EXISTS observation_market_time
 ON observations(interval,timestamp_ms,symbol);
CREATE TABLE IF NOT EXISTS source_observations(
 source_id TEXT NOT NULL REFERENCES sources(id),
 observation_id TEXT NOT NULL REFERENCES observations(id),
 source_sequence INTEGER NOT NULL, source_time_text TEXT,
 PRIMARY KEY(source_id,source_sequence));
CREATE INDEX IF NOT EXISTS observation_provenance
 ON source_observations(observation_id,source_id);
CREATE TABLE IF NOT EXISTS runs(
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, state TEXT NOT NULL,
 manifest_json TEXT NOT NULL, code_sha256 TEXT NOT NULL,
 dataset_sources_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(
 run_id TEXT NOT NULL REFERENCES runs(id), id TEXT NOT NULL,
 symbol TEXT NOT NULL, detector TEXT NOT NULL, available_ms INTEGER NOT NULL,
 details_json TEXT NOT NULL, PRIMARY KEY(run_id,id));
CREATE INDEX IF NOT EXISTS event_by_symbol
 ON events(run_id,symbol,available_ms);
CREATE INDEX IF NOT EXISTS event_by_detector
 ON events(run_id,detector,available_ms);
CREATE TABLE IF NOT EXISTS scenarios(
 id TEXT PRIMARY KEY, parameters_json TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS outcomes(
 run_id TEXT NOT NULL, event_id TEXT NOT NULL, scenario_id TEXT NOT NULL REFERENCES scenarios(id),
 status TEXT NOT NULL, quantity INTEGER, net_pnl REAL,
 details_json TEXT NOT NULL,
 PRIMARY KEY(run_id,event_id,scenario_id),
 FOREIGN KEY(run_id,event_id) REFERENCES events(run_id,id));
CREATE INDEX IF NOT EXISTS outcome_summary
 ON outcomes(run_id,scenario_id,status,net_pnl);
CREATE TABLE IF NOT EXISTS summaries(
 run_id TEXT NOT NULL REFERENCES runs(id), summary_id TEXT NOT NULL,
 data_json TEXT NOT NULL, PRIMARY KEY(run_id,summary_id));
"""

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def number(value):
    if value is None: return None
    d=Decimal(str(value))
    if not d.is_finite(): raise ValueError("Nonfinite observation")
    return format(d.normalize(),"f")

class ResearchStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path,timeout=10)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SCHEMA)
    def close(self):
        self.db.close()
    def import_source(self,path,symbol,interval,relative_path):
        raw=Path(path).read_bytes()
        sha=hashlib.sha256(raw).hexdigest()
        source_id=digest([relative_path,sha])
        if self.db.execute("SELECT 1 FROM sources WHERE id=?",(source_id,)).fetchone():
            return {"source_id":source_id,"status":"already_imported"}
        data=json.loads(raw).get("series")
        rows=data.get("data") if isinstance(data,dict) else None
        if not rows: return {"status":"empty"}
        if isinstance(rows,dict):rows=[rows]
        observations=[];links=[]
        for seq,row in enumerate(rows):
            stamp=int(row["timestamp"])
            if interval=="tick":
                if not 946684800000<=stamp<=4102444800000:raise ValueError("Tick epoch unit mismatch")
                ms=stamp
            else:
                if not 946684800<=stamp<=4102444800:raise ValueError("Bar epoch unit mismatch")
                ms=stamp*1000
            values=[number(row.get(k)) for k in ["open","high","low","close","price","volume","vwap"]]
            if values[5] is None:raise ValueError("Missing volume")
            record=[symbol,interval,ms,*values]
            oid=digest(record)
            observations.append([oid,*record])
            links.append([source_id,oid,seq,row.get("time")])
        # File lineage and all its observations commit together or not at all.
        with self.db:
            self.db.execute("INSERT INTO sources VALUES(?,?,?,?,?,?,?)",
                (source_id,relative_path,sha,symbol,interval,datetime.now(timezone.utc).isoformat(),len(rows)))
            self.db.executemany("INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?,?,?,?,?,?,?)",observations)
            self.db.executemany("INSERT INTO source_observations VALUES(?,?,?,?)",links)
        return {"source_id":source_id,"status":"imported","rows":len(rows)}
    def source_ids(self,relative_paths):
        result=[]
        for name in relative_paths:
            matches=self.db.execute("SELECT id FROM sources WHERE relative_path=? ORDER BY imported_at DESC,id DESC",(name,)).fetchall()
            if not matches:raise ValueError("Required source not imported: "+name)
            result.append(matches[0][0])
        return result
    def import_run(self,manifest,events,outcomes,summaries,source_ids,code):
        missing=set(source_ids)-{r[0] for r in self.db.execute("SELECT id FROM sources")}
        if missing:raise ValueError("Run references missing data")
        run_id=str(uuid.uuid4())
        with self.db:
            self.db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?)",(run_id,
                datetime.now(timezone.utc).isoformat(),"writing",canonical(manifest),
                hashlib.sha256(code).hexdigest(),canonical(sorted(source_ids))))
            self.db.executemany("INSERT INTO events VALUES(?,?,?,?,?,?)",[
                (run_id,e["event_id"],e["symbol"],e["detector"],
                 e["available_epoch"]*1000,canonical(e)) for e in events])
            for o in outcomes:
                params={k:o[k] for k in ["delay_seconds","hold_minutes","budget","assumed_spread","assumed_fee"]}
                sid=digest(params)
                self.db.execute("INSERT OR IGNORE INTO scenarios VALUES(?,?)",(sid,canonical(params)))
                repeated=set(params)|{"event_id","symbol","detector","status","quantity","net_pnl"}
                extra={k:v for k,v in o.items() if k not in repeated}
                self.db.execute("INSERT INTO outcomes VALUES(?,?,?,?,?,?,?)",(
                    run_id,o["event_id"],sid,o["status"],o.get("quantity"),
                    float(o["net_pnl"]) if o.get("net_pnl") is not None else None,canonical(extra)))
            self.db.executemany("INSERT INTO summaries VALUES(?,?,?)",
                [(run_id,digest(s),canonical(s)) for s in summaries])
            self.db.execute("UPDATE runs SET state='complete' WHERE id=?",(run_id,))
        return run_id
    def read_run_observations(self,run_id,symbol,interval,start_ms,end_ms):
        row=self.db.execute("SELECT dataset_sources_json FROM runs WHERE id=? AND state='complete'",(run_id,)).fetchone()
        if row is None:raise ValueError("No complete run")
        ids=json.loads(row[0])
        if not ids:return []
        placeholders=','.join('?' for _ in ids)
        sql="SELECT DISTINCT o.id,o.timestamp_ms,o.open,o.high,o.low,o.close,o.volume FROM observations o JOIN source_observations p ON p.observation_id=o.id WHERE o.symbol=? AND o.interval=? AND o.timestamp_ms BETWEEN ? AND ? AND p.source_id IN ("+placeholders+") ORDER BY o.timestamp_ms,o.id"
        rows=self.db.execute(sql,[symbol,interval,start_ms,end_ms,*ids]).fetchall()
        seen=set()
        for item in rows:
            if item[1] in seen:raise ValueError("Conflicting revisions in frozen dataset")
            seen.add(item[1])
        return rows
    def snapshot(self,path):
        # SQLite backup includes committed WAL content, unlike copying the live file.
        target=Path(path)
        with closing(sqlite3.connect(target)) as dest:
            self.db.backup(dest)
        with closing(sqlite3.connect(target)) as check:
            if check.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("Snapshot integrity failed")
        return hashlib.sha256(target.read_bytes()).hexdigest()
    def stats(self):
        return {name:self.db.execute("SELECT count(*) FROM "+name).fetchone()[0]
                for name in ["sources","observations","source_observations","runs","events","scenarios","outcomes","summaries"]}

def ingest_local():
    root=Path(__file__).resolve().parent
    db=ResearchStore(root/"research"/"visionairy_research.sqlite")
    entries=[]
    initial=root/"SPY_history_sample.json"
    if initial.exists():entries.append((initial,"SPY","1min"))
    for folder in ["qualified_samples","pilot_data"]:
        for p in sorted((root/folder).glob("*.json")):
            stem=p.stem
            if "_" in stem and stem.rsplit("_",1)[1] in ("1min","5min","15min","tick"):
                symbol,interval=stem.rsplit("_",1)
                entries.append((p,symbol,interval))
    for p,symbol,interval in entries:
        db.import_source(p,symbol,interval,p.relative_to(root).as_posix())
    print(canonical(db.stats()))
    hash_value=db.snapshot(root/"research"/"research_snapshot.sqlite")
    print("Snapshot integrity checked; sha256="+hash_value)
    db.close()

if __name__=="__main__":ingest_local()

