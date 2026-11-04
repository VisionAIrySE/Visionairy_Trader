"""Export the preserved local research into deterministic, typed Supabase batches.
No credentials/network. Outputs are private research data, excluded from Git.
"""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib,json,sqlite3,uuid
from pathlib import Path

def stable(kind,key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL,"visionairy-trader/"+kind+"/"+str(key)))
def canon(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)
def sha(value):
    return hashlib.sha256(canon(value).encode()).hexdigest()
def iso(ms):
    return (datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(milliseconds=int(ms))).isoformat()

TYPES={
"instruments":"id uuid,symbol text,exchange text,asset_type text",
"sources":"id uuid,provider text,source_key text,sha256 text,instrument_id uuid,interval_label text,received_at timestamptz,row_count bigint,source_metadata jsonb",
"observations":"id uuid,fingerprint text,instrument_id uuid,interval_label text,observed_at timestamptz,available_at timestamptz,open numeric,high numeric,low numeric,close numeric,price numeric,volume numeric,vwap numeric",
"source_observations":"source_id uuid,sequence bigint,observation_id uuid,source_time_text text",
"datasets":"id uuid,name text,fingerprint text,status text,universe_definition jsonb,quality_tier text",
"dataset_sources":"dataset_id uuid,source_id uuid",
"hypotheses":"id uuid,key text,family text,claim text,success_criteria jsonb",
"strategy_versions":"id uuid,hypothesis_id uuid,version text,parameters jsonb,spec_sha256 text,code_sha256 text",
"runs":"id uuid,dataset_id uuid,purpose text,status text,manifest jsonb,code_sha256 text,started_at timestamptz",
"run_strategies":"run_id uuid,strategy_version_id uuid",
"opportunities":"id uuid,instrument_id uuid,first_observable_at timestamptz,clustering_version text,cluster_key text,context jsonb",
"signals":"id uuid,run_id uuid,opportunity_id uuid,strategy_version_id uuid,available_at timestamptz,basis text,details jsonb",
"execution_scenarios":"id uuid,fingerprint text,parameters jsonb,assumptions jsonb",
"outcomes":"id uuid,run_id uuid,signal_id uuid,scenario_id uuid,status text,evidence_tier text,quantity numeric,net_pnl numeric,entry_at timestamptz,exit_at timestamptz,details jsonb",
"result_summaries":"id uuid,run_id uuid,summary_key text,dimensions jsonb,statistics jsonb,opportunity_count integer",
}
KEYS={"source_observations":["source_id","sequence"],"dataset_sources":["dataset_id","source_id"],
      "run_strategies":["run_id","strategy_version_id"]}
ORDER=["instruments","sources","observations","source_observations","datasets","dataset_sources",
       "hypotheses","strategy_versions","runs","run_strategies","opportunities","signals",
       "execution_scenarios","outcomes","result_summaries"]

def batch_sql(table,rows):
    if table not in TYPES: raise ValueError("Unknown target table")
    fields=[x.strip().split()[0] for x in TYPES[table].split(",")]
    if any(set(r)!=set(fields) for r in rows):raise ValueError("Column mismatch: "+table)
    payload=canon(rows).replace("'","''")
    keys=KEYS.get(table,["id"])
    exists=" and ".join("d."+k+"=s."+k for k in keys)
    return ("insert into trader."+table+"("+",".join(fields)+") select "+
       ",".join("s."+f for f in fields)+" from jsonb_to_recordset('"+payload+
       "'::jsonb) as s("+TYPES[table]+") where not exists (select 1 from trader."+table+
       " d where "+exists+") on conflict do nothing;")

def export(db_path,outcomes_path,outdir,batch_size=1500):
    db=sqlite3.connect("file:"+str(Path(db_path).resolve()).replace("\\","/")+"?mode=ro",uri=True)
    db.row_factory=sqlite3.Row
    tables={k:[] for k in ORDER}
    obs=list(db.execute("select * from observations order by symbol,interval,timestamp_ms,id"))
    for symbol in sorted({r["symbol"] for r in obs}):
        tables["instruments"].append(dict(id=stable("instrument",symbol),symbol=symbol,exchange="UNKNOWN",asset_type="etf" if symbol=="SPY" else "stock"))
    for r in db.execute("select * from sources order by id"):
        tables["sources"].append(dict(id=stable("source",r["id"]),provider="tradier",source_key=r["relative_path"],
            sha256=r["sha256"],instrument_id=stable("instrument",r["symbol"]),interval_label=r["interval"],
            received_at=r["imported_at"],row_count=r["row_count"],
            source_metadata={"legacy_source_id":r["id"],"execution_evidence":"bars_or_trades_not_quotes","available_at_basis":"inferred_bar_completion_not_observed_feed_receipt"}))
    for r in obs:
        ms=r["timestamp_ms"];duration={"1min":60000,"5min":300000,"15min":900000,"tick":0}[r["interval"]]
        item=dict(id=stable("observation",r["id"]),fingerprint=r["id"],instrument_id=stable("instrument",r["symbol"]),
            interval_label=r["interval"],observed_at=iso(ms),available_at=iso(ms+duration))
        item.update({k:r[k] for k in ["open","high","low","close","price","volume","vwap"]})
        tables["observations"].append(item)
    for r in db.execute("select * from source_observations order by source_id,source_sequence"):
        tables["source_observations"].append(dict(source_id=stable("source",r["source_id"]),sequence=r["source_sequence"],
            observation_id=stable("observation",r["observation_id"]),source_time_text=r["source_time_text"]))
    event_rows=list(db.execute("select * from events"))
    original_outcomes=json.loads(Path(outcomes_path).read_text())
    # Original Decimal strings are authoritative; SQLite REAL PnL is only a diagnostic aggregate.
    scenario_map={r["id"]:json.loads(r["parameters_json"]) for r in db.execute("select * from scenarios")}
    outcome_map={}
    for o in original_outcomes:
        params={k:o[k] for k in ["delay_seconds","hold_minutes","budget","assumed_spread","assumed_fee"]}
        outcome_map[(o["event_id"],sha(params))]=o
    for run in db.execute("select * from runs order by created_at"):
        runid=run["id"];manifest=json.loads(run["manifest_json"]);source_ids=json.loads(run["dataset_sources_json"])
        dataset=stable("dataset",runid)
        tables["datasets"].append(dict(id=dataset,name="Preserved three-stock pilot",fingerprint=sha(sorted(source_ids)),
            status="building",universe_definition={"scope":"convenience_sample","symbols":["AAPL","AMD","AMZN"],"not_market_wide":True},
            quality_tier="bar_screening_modeled_execution"))
        tables["dataset_sources"] += [dict(dataset_id=dataset,source_id=stable("source",s)) for s in source_ids]
        tables["runs"].append(dict(id=runid,dataset_id=dataset,purpose="exploration",status="writing",
            manifest=manifest,code_sha256=run["code_sha256"],started_at=run["created_at"]))
        for detector in manifest["detectors"]:
            h=stable("hypothesis",detector);v=stable("strategy",runid+"/"+detector)
            tables["hypotheses"].append(dict(id=h,key=detector,family="price_activity_baseline",
                claim=detector+" predicts forward net movement",success_criteria={"stage":"exploratory_no_profitability_claim"}))
            params={"detector":detector,"source_manifest":manifest}
            tables["strategy_versions"].append(dict(id=v,hypothesis_id=h,version=runid,parameters=params,
                spec_sha256=sha(params),code_sha256=run["code_sha256"]))
            tables["run_strategies"].append(dict(run_id=runid,strategy_version_id=v))
        for e in [x for x in event_rows if x["run_id"]==runid]:
            cluster=e["symbol"]+":"+str(e["available_ms"]);opid=stable("opportunity",cluster)
            tables["opportunities"].append(dict(id=opid,instrument_id=stable("instrument",e["symbol"]),
                first_observable_at=iso(e["available_ms"]),clustering_version="symbol_timestamp_v1",
                cluster_key=cluster,context={"independence":"not_established","same_burst_may_span_multiple_timestamps":True}))
            tables["signals"].append(dict(id=stable("signal",runid+"/"+e["id"]),run_id=runid,opportunity_id=opid,
                strategy_version_id=stable("strategy",runid+"/"+e["detector"]),available_at=iso(e["available_ms"]),
                basis="price_volume_replay",details=json.loads(e["details_json"])))
        for o in db.execute("select * from outcomes where run_id=?",(runid,)):
            original=outcome_map[(o["event_id"],o["scenario_id"])]
            modeled=original["status"]=="modeled"
            tables["outcomes"].append(dict(id=stable("outcome",runid+"/"+o["event_id"]+"/"+o["scenario_id"]),
                run_id=runid,signal_id=stable("signal",runid+"/"+o["event_id"]),scenario_id=stable("scenario",o["scenario_id"]),
                status=o["status"],evidence_tier="modeled" if modeled else "censored",
                quantity=original.get("quantity"),net_pnl=original.get("net_pnl") if modeled else None,
                entry_at=iso(original["entry_epoch"]*1000) if "entry_epoch" in original else None,
                exit_at=iso(original["exit_epoch"]*1000) if "exit_epoch" in original else None,
                details=original))
        for r in db.execute("select * from summaries where run_id=?",(runid,)):
            stats=json.loads(r["data_json"])
            dimensions={k:stats[k] for k in ["detector","delay_seconds","hold_minutes","budget","assumed_spread","assumed_fee"]}
            tables["result_summaries"].append(dict(id=stable("summary",runid+"/"+r["summary_id"]),run_id=runid,
                summary_key=r["summary_id"],dimensions=dimensions,statistics=stats,opportunity_count=stats["opportunities"]))
    for sid,params in scenario_map.items():
        tables["execution_scenarios"].append(dict(id=stable("scenario",sid),fingerprint=sid,parameters=params,
            assumptions={"historical_quotes":False,"fills":"modeled_bar_open","liquidity":"prior_bar_participation_proxy"}))
    # Shared opportunities can appear in several detector rows.
    for table in ORDER:
        keys=KEYS.get(table,["id"])
        unique={}
        for r in tables[table]:unique[tuple(r[k] for k in keys)]=r
        tables[table]=list(unique.values())
    out=Path(outdir);out.mkdir(parents=True,exist_ok=True)
    batches=[]
    for table in ORDER:
        rows=tables[table]
        for offset in range(0,len(rows),batch_size):
            chunk=rows[offset:offset+batch_size]
            name=f"{len(batches):03}_{table}.sql"
            (out/name).write_text(batch_sql(table,chunk),encoding="utf-8")
            batches.append({"file":name,"table":table,"rows":len(chunk)})
    finish=[]
    for run in tables["runs"]:
        finish.append("update trader.datasets set status='frozen',frozen_at=now() where id='"+run["dataset_id"]+"' and status='building';")
        finish.append("update trader.runs set status='complete',completed_at=now() where id='"+run["id"]+"' and status='writing';")
    (out/"finish.sql").write_text("\n".join(finish),encoding="utf-8")
    record={"batches":batches,"expected_counts":{k:len(v) for k,v in tables.items()},
            "source":"preserved_local_pilot","not_independent_trades":True}
    (out/"manifest.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
    print(json.dumps(record["expected_counts"]))
    db.close()
    return record

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--database",required=True);p.add_argument("--outcomes",required=True)
    p.add_argument("--output",required=True);args=p.parse_args()
    export(args.database,args.outcomes,args.output)

