"""Local credential entry for one historical sample; token stays in memory."""
import json
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk
from replay import request_data, parse_bars, qualify, dump

root=tk.Tk()
root.title("VisionAIry - Historical Data Check")
root.geometry("690x420")
root.columnconfigure(1, weight=1)
ttk.Label(root,text="Ghost research only. No funding or orders.",font=("Segoe UI",12,"bold")).grid(row=0,column=0,columnspan=2,padx=16,pady=12)
ttk.Label(root,text="Paste the PRODUCTION API token below. It is masked and is not saved.\nThis application sends only a GET request to Tradier's historical market-data endpoint.",
    wraplength=650).grid(row=1,column=0,columnspan=2,padx=16,pady=6)
fields={}
for row,(key,label,value) in enumerate([
    ("token","Production API token",""),("symbol","Sample symbol","SPY"),
    ("start","Start (provider time)","2026-10-21 09:30"),
    ("end","End (provider time)","2026-11-03 16:00")],start=2):
    ttk.Label(root,text=label).grid(row=row,column=0,padx=16,pady=7,sticky="w")
    box=ttk.Entry(root,show="*" if key=="token" else "",width=53)
    box.insert(0,value);box.grid(row=row,column=1,padx=16,pady=7,sticky="ew")
    fields[key]=box
status=tk.StringVar(value="Not connected. No request sent.")
ttk.Label(root,textvariable=status,wraplength=650).grid(row=7,column=0,columnspan=2,padx=16,pady=12)

def collect():
    token=fields["token"].get().strip()
    symbol=fields["symbol"].get().strip().upper()
    start=fields["start"].get().strip()
    end=fields["end"].get().strip()
    if not token:
        status.set("Enter the production token. Do not paste it into chat.")
        return
    fields["token"].delete(0,"end")
    button.state(["disabled"])
    status.set("Requesting one symbol; no orders are available in this application.")
    def work():
        message=""
        try:
            payload=request_data(symbol,start,end,token)
            bars=parse_bars(payload)
            output=Path(__file__).resolve().parent/"sample"
            output.mkdir(exist_ok=True)
            dump(output/(symbol+".json"),payload)
            dump(output/(symbol+".quality.json"),{**qualify(payload,bars),
                "symbol":symbol,"requested_start":start,"requested_end":end,
                "interval":"1min","session_filter":"open",
                "time_convention_requires_validation":True,
                "scope":"one_symbol_access_sample_not_universe"})
            message="Saved "+str(len(bars))+" bars in the sample folder. Token not saved. Share the two JSON files for the coverage review; never share your token."
        except Exception:
            # Do not expose arbitrary exception messages from credential-bearing transports.
            message="Sample check failed. No orders sent. Verify token, dates and data entitlement; the token was not saved."
        root.after(0,lambda:finish(message))
    threading.Thread(target=work,daemon=True).start()

def finish(message):
    status.set(message)
    button.state(["!disabled"])

button=ttk.Button(root,text="Fetch historical sample",command=collect)
button.grid(row=6,column=0,columnspan=2,pady=10)
root.mainloop()

