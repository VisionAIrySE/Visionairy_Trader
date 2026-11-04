"""Small authenticated read-only history qualification. Credentials never saved."""
import getpass
import json
from datetime import datetime, timezone
from pathlib import Path
from replay import request_data, parse_bars, qualify, DataError

token=getpass.getpass("Tradier production token (hidden; not saved): ").strip()
root=Path("qualified_samples")
root.mkdir(exist_ok=True)
results=[]
for symbol,start,end,interval in [
    ("SPY","2026-10-01 09:30","2026-11-03 16:00","1min"),
    ("AAPL","2026-10-21 09:30","2026-11-03 16:00","1min"),
    ("KOPN","2026-10-21 09:30","2026-11-03 16:00","1min"),
    ("SPY","2026-11-03 09:30","2026-11-03 09:31","tick")
]:
    name=symbol+"_"+interval
    meta={"symbol":symbol,"interval":interval,"requested_start":start,
          "requested_end":end,"retrieved_at_utc":datetime.now(timezone.utc).isoformat()}
    try:
        p=request_data(symbol,start,end,token,interval=interval)
        (root/(name+".json")).write_text(json.dumps(p),encoding="utf-8")
        series=p.get("series")
        rows=series.get("data") if isinstance(series,dict) else None
        if isinstance(rows,dict): rows=[rows]
        if not rows: raise DataError("No observations")
        meta.update({"rows":len(rows),"first_time":rows[0].get("time"),
            "last_time":rows[-1].get("time"),
            "fields":sorted(set.intersection(*(set(r) for r in rows))),
            "sessions":sorted({r.get("time","")[:10] for r in rows}),
            "status":"retrieved"})
        if interval=="1min":
            b=parse_bars(p); meta["quality"]=qualify(p,b)
    except DataError as exc:
        meta.update(status="unqualified",reason=str(exc))
    results.append(meta)
    print(json.dumps({k:v for k,v in meta.items() if k!="quality"}))
token=None
(root/"qualification_summary.json").write_text(json.dumps(results,indent=2),encoding="utf-8")

