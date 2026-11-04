"""Exploratory historical pilot: fixed parameter manifest, modeled bar execution."""
from collections import Counter, defaultdict
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
import hashlib,json
from pathlib import Path
from statistics import mean
from replay import parse_bars,benchmark_events,mark_outcome,DataError

ROOT=Path("pilot_data")
OUT=Path("pilot_results");OUT.mkdir(exist_ok=True)
MANIFEST={"version":"pilot_0.1","scope":"13-symbol convenience sample; exploratory only",
    "detectors":["B01_raw_2pct","B01_aligned_1pct","B02_aligned_1pct_rvol3",
                 "B01_aligned_2pct","B02_aligned_2pct_rvol3"],
    "entry_delays_seconds":[0,60,120],"holding_minutes":[5,15,60],
    "budgets":[25,50,100,250,500],"full_spread_assumptions":[.002,.01,.03],
    "commission_per_side":[0,.35],
    "minimum_prior_baseline_sessions":10,"maximum_prior_baseline_sessions":20,
    "activity_cap":"1% previous-minute volume; proxy only",
    "no_stops_targets_or_portfolio":True,
    "counterfactual_counts_not_independent":True,
    "bar_time_semantics":"start labeled; signals available after completed minute",
    "unavailable_data":"retained/censored, not automatically a loss or a win"}
(OUT/"trial_manifest.json").write_text(json.dumps(MANIFEST,indent=2))

def canonical_time(row,interval):
    stamp=int(row["timestamp"])
    ms=stamp if interval=="tick" else stamp*1000
    if not 946684800000 <= ms <= 4102444800000:
        raise DataError("Unexpected epoch units")
    parsed=datetime.fromisoformat(row["time"])
    utc=datetime.fromtimestamp(ms/1000,timezone.utc).replace(tzinfo=None)
    if interval=="tick":
        if abs((utc-parsed).total_seconds())>=1:
            raise DataError("Tick text/epoch mismatch")
    else:
        if utc-parsed not in (timedelta(hours=4),timedelta(hours=5)):
            raise DataError("Bar ET-label/UTC epoch mismatch")
    return ms

def rvol_at(i,rows,five_rows):
    row=rows[i]
    local=datetime.fromisoformat(row["time"])
    # A completed minute ending a five-minute bucket, e.g. 09:34 -> 09:35.
    if (local.minute+1)%5 or i<4:
        return None
    chunk=rows[i-4:i+1]
    if any(int(b["timestamp"])-int(a["timestamp"])!=60 for a,b in zip(chunk,chunk[1:])):
        return None
    block=local-timedelta(minutes=4)
    day=block.date().isoformat(); clock=block.time().isoformat()
    past=[x for x in five_rows if x["time"][:10]<day and x["time"][11:19]==clock]
    past=past[-20:]
    if len(past)<10:
        return None
    values=sorted(D(str(x["volume"])) for x in past)
    n=len(values)
    median=values[n//2] if n%2 else (values[n//2-1]+values[n//2])/2
    current=sum(D(str(x["volume"])) for x in chunk)
    return {"value":str(current/median) if median>0 else None,
            "prior_sessions":n,"baseline_median":str(median),"window_volume":str(current)}

def filter_aligned(events,rows,five_rows,need_rvol):
    result=[]
    # Trigger state/cooldown must be computed AFTER the filter, not on a different universe.
    last=-10**15
    for e in events:
        if (datetime.fromisoformat(rows[e["signal_index"]]["time"]).minute+1)%5:
            continue
        rv=rvol_at(e["signal_index"],rows,five_rows)
        if need_rvol and (rv is None or rv["value"] is None or D(rv["value"])<3):
            continue
        if e["available_epoch"]-last<1800:
            continue
        result.append({**e,"relative_volume":rv})
        last=e["available_epoch"]
    return result

def all_qualified_events(bars,threshold):
    # Evaluate aligned conditions on every eligible five-minute edge; suppress repeats afterward.
    result=[]
    for i in range(5,len(bars)):
        chunk=bars[i-5:i+1]
        if any(b.timestamp-a.timestamp!=60 for a,b in zip(chunk,chunk[1:])):
            continue
        change=bars[i].close/bars[i-5].close-1
        if change>=threshold:
            result.append({"signal_index":i,"available_epoch":bars[i].timestamp+60,
                "observed_return":str(change),"threshold":str(threshold),"window_minutes":5})
    return result

def run():
    summary=[]; all_events=[];all_outcomes=[];timing=[];diagnostics=[]
    for path in sorted(ROOT.glob("*_1min.json")):
        symbol=path.name.split("_")[0]
        five=ROOT/(symbol+"_5min.json")
        if not five.exists():
            diagnostics.append({"symbol":symbol,"status":"no_baseline_file"});continue
        rows=json.loads(path.read_text())["series"]["data"]
        five_rows=json.loads(five.read_text())["series"]["data"]
        if not rows or not five_rows: continue
        bars=parse_bars({"series":{"data":rows}})
        for row in rows:canonical_time(row,"1min")
        for row in five_rows:canonical_time(row,"5min")
        days=Counter(r["time"][:10] for r in rows)
        timing.append({"symbol":symbol,"minute_bars":len(rows),"five_minute_bars":len(five_rows),
            "sessions":dict(days),"text_epoch_consistent":True,
            "earliest_baseline":five_rows[0]["time"],"last_baseline":five_rows[-1]["time"]})
        groups={"B01_raw_2pct":benchmark_events(bars)}
        for threshold,label in [(D(".01"),"1pct"),(D(".02"),"2pct")]:
            candidates=all_qualified_events(bars,threshold)
            groups["B01_aligned_"+label]=filter_aligned(candidates,rows,five_rows,False)
            groups["B02_aligned_"+label+"_rvol3"]=filter_aligned(candidates,rows,five_rows,True)
        for detector,events in groups.items():
            for e in events:
                key=f"{symbol}:{detector}:{e['available_epoch']}"
                e.update(event_id=hashlib.sha256(key.encode()).hexdigest()[:20],
                         symbol=symbol,detector=detector)
                all_events.append(e)
                for delay in [0,60,120]:
                 for horizon in [5,15,60]:
                  for budget in [25,50,100,250,500]:
                   for spread in [D(".002"),D(".01"),D(".03")]:
                    for fee in [D(0),D(".35")]:
                     o=mark_outcome(bars,e,delay,horizon,D(budget),spread,fee)
                     o.update(symbol=symbol,detector=detector,budget=budget,
                              assumed_spread=str(spread),assumed_fee=str(fee),
                              session=rows[e["signal_index"]]["time"][:10])
                     all_outcomes.append(o)
    grouped=defaultdict(list)
    for o in all_outcomes:
        key=tuple(o[k] for k in ["detector","delay_seconds","hold_minutes","budget",
                                "assumed_spread","assumed_fee"])
        grouped[key].append(o)
    for key,group in grouped.items():
        modeled=[o for o in group if o["status"]=="modeled"]
        pnl=[float(o["net_pnl"]) for o in modeled]
        row=dict(zip(["detector","delay_seconds","hold_minutes","budget",
                      "assumed_spread","assumed_fee"],key))
        row.update(opportunities=len(group),modeled=len(modeled),
                   statuses=dict(Counter(o["status"] for o in group)),
                   mean_net_dollars=mean(pnl) if pnl else None,
                   positive_fraction=sum(x>0 for x in pnl)/len(pnl) if pnl else None,
                   distinct_days=len({o["session"] for o in modeled}),
                   distinct_symbols=len({o["symbol"] for o in modeled}))
        summary.append(row)
    for name,value in [("timing.json",timing),("events.json",all_events),
                       ("outcomes.json",all_outcomes),("summary.json",summary),
                       ("diagnostics.json",diagnostics)]:
        (OUT/name).write_text(json.dumps(value,indent=2))
    print(json.dumps({"symbols":len(timing),"named_detector_events":len(all_events),
        "unique_symbol_signal_times":len({(e["symbol"],e["available_epoch"]) for e in all_events}),
        "modeled_outcome_scenarios":len(all_outcomes),
        "events_by_detector":dict(Counter(e["detector"] for e in all_events)),
        "statuses":dict(Counter(o["status"] for o in all_outcomes))}))
    from research_store import ResearchStore
    db=ResearchStore("research/visionairy_research.sqlite")
    names=[]
    for t in timing:
        names.extend(["pilot_data/"+t["symbol"]+"_1min.json","pilot_data/"+t["symbol"]+"_5min.json"])
    code=b"".join(p.name.encode()+p.read_bytes() for p in [Path("pilot_study.py"),Path("replay.py"),Path("research_store.py")])
    run_id=db.import_run(MANIFEST,all_events,all_outcomes,summary,db.source_ids(names),code)
    snapshot_sha=db.snapshot("research/research_snapshot.sqlite")
    print(json.dumps({"run_id":run_id,"db_counts":db.stats(),"snapshot_sha":snapshot_sha}))
    db.close()
    display=[s for s in summary if s["budget"]==100 and s["assumed_spread"]=="0.002"
             and s["delay_seconds"]==60 and s["hold_minutes"]==15]
    print(json.dumps(display,indent=2))

if __name__=="__main__":run()

