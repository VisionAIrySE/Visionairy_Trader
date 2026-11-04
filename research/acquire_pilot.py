"""Small preregistered convenience pilot; fixed roster, not market-wide discovery."""
import getpass,json,time
from pathlib import Path
from replay import request_data,DataError

symbols=["AAPL","AMD","AMZN","F","GPRO","INTC","KOPN","LCID","MSFT","NVDA","RIVN","SOFI","SPY"]
root=Path("pilot_data");root.mkdir(exist_ok=True)
manifest={"roster":symbols,"selection":"convenience pilot fixed before observing outcomes; not representative",
          "test_start":"2026-10-21","test_end":"2026-11-03",
          "baseline_request_start":"2026-10-01","results":[]}
(root/"manifest.json").write_text(json.dumps(manifest,indent=2))
token=getpass.getpass("Tradier token (hidden; not saved): ").strip()
for symbol in symbols:
 for interval,start,end in [
     ("1min","2026-10-21 09:30","2026-11-03 16:00"),
     ("5min","2026-10-01 09:30","2026-11-03 16:00")]:
  p=root/(symbol+"_"+interval+".json")
  if p.exists():
   print(symbol,interval,"cached");continue
  status={"symbol":symbol,"interval":interval,"start":start,"end":end}
  try:
   payload=request_data(symbol,start,end,token,interval=interval)
   rows=(payload.get("series") or {}).get("data") or []
   if isinstance(rows,dict):rows=[rows]
   p.write_text(json.dumps(payload),encoding="utf-8")
   status.update(status="retrieved",rows=len(rows),first=rows[0].get("time") if rows else None,
                 last=rows[-1].get("time") if rows else None)
  except DataError as e:
   status.update(status="unqualified",reason=str(e))
  manifest["results"].append(status)
  (root/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
  print(json.dumps(status),flush=True)
  time.sleep(.55)
token=None

