"""Read-only historical qualification and BAR-LEVEL benchmark replay.
No brokerage order methods exist. Not the complete 32-variant platform.
"""
import argparse
from bisect import bisect_left
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

D = Decimal
ENDPOINT = "https://api.tradier.com/v1/markets/timesales"

class DataError(ValueError):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DataError("Redirect rejected; no credential forwarded.")

def request_data(symbol, start, end, token, opener=None, interval="1min"):
    if interval not in ("1min", "5min", "15min", "tick"):
        raise DataError("Unsupported historical interval.")
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", symbol):
        raise DataError("Invalid symbol.")
    for value in (start, end):
        datetime.strptime(value, "%Y-%m-%d %H:%M")
    if start >= end or not token or "\n" in token or "\r" in token:
        raise DataError("Invalid time range or credential.")
    query = urllib.parse.urlencode(dict(symbol=symbol, start=start, end=end,
                                        interval=interval, session_filter="open"))
    req = urllib.request.Request(ENDPOINT + "?" + query,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        method="GET")
    opener = opener or urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=30) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        # Never echo credential-bearing requests or arbitrary provider response bodies.
        raw = exc.read(4096)
        if b"Quota Violation" in raw or exc.code == 429:
            raise DataError("Market-data quota reached; stopped. Retry after reset.") from None
        raise DataError("Historical request failed: HTTP " + str(exc.code)) from None
    except urllib.error.URLError:
        raise DataError("Historical network request failed; no automatic retry.") from None
    if len(raw) > 16 * 1024 * 1024:
        raise DataError("Payload exceeds 16 MiB; request a shorter interval.")
    if b"Quota Violation" in raw:
        raise DataError("Market-data quota reached; stopped.")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise DataError("Expected JSON historical response.") from None
    return payload

@dataclass(frozen=True)
class Bar:
    timestamp: int
    open: D
    high: D
    low: D
    close: D
    volume: D

def parse_bars(payload):
    if not isinstance(payload, dict):
        raise DataError("Expected object response.")
    series = payload.get("series")
    if not isinstance(series, dict) or not series.get("data"):
        raise DataError("No historical bars returned; access/range not qualified.")
    rows = series["data"]
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        raise DataError("Unsupported historical series shape.")
    result = []
    seen = set()
    for row in rows:
        try:
            stamp = int(row["timestamp"])
            if stamp < 946684800 or stamp > 4102444800:
                raise DataError("Expected epoch seconds, not milliseconds.")
            values = [D(str(row[k])) for k in ("open","high","low","close","volume")]
            if not all(v.is_finite() for v in values):
                raise DataError("Nonfinite bar.")
            o,h,l,c,v = values
            if min(o,h,l,c) <= 0 or v < 0 or h < max(o,l,c) or l > min(o,h,c):
                raise DataError("Invalid OHLC/volume.")
        except (KeyError, TypeError, ValueError, ArithmeticError):
            raise DataError("Invalid or unsupported bar fields.") from None
        if stamp in seen:
            raise DataError("Duplicate timestamp; reconcile corrections first.")
        seen.add(stamp)
        result.append(Bar(stamp,o,h,l,c,v))
    # Do not conceal provider sequencing defects by sorting them silently.
    if any(a.timestamp >= b.timestamp for a,b in zip(result,result[1:])):
        raise DataError("Unordered historical observations.")
    return result

def qualify(payload, bars):
    rows = payload["series"]["data"]
    if isinstance(rows, dict):
        rows = [rows]
    return {
        "bars": len(bars), "first_epoch": bars[0].timestamp,
        "last_epoch": bars[-1].timestamp,
        "gaps_over_one_minute": sum(b.timestamp-a.timestamp != 60 for a,b in zip(bars,bars[1:])),
        "zero_volume_bars": sum(b.volume == 0 for b in bars),
        "fields_returned": sorted(set.intersection(*(set(r) for r in rows))),
        "tier": "bar_screening_only",
        "historical_quote_depth_validated": False,
        "bar_timestamp_start_convention_validated": False,
        "corporate_actions_validated": False,
        "point_in_time_universe_validated": False,
        "same_time_of_day_baseline_validated": False,
        "approved_for_exact_execution_claims": False
    }

def benchmark_events(bars, threshold=D("0.02"), window=5, cooldown_seconds=1800):
    if window < 1 or threshold <= 0 or cooldown_seconds < 0:
        raise DataError("Invalid detector parameters.")
    last_event = -10**15
    events = []
    was_qualified = False
    for i in range(window, len(bars)):
        chunk = bars[i-window:i+1]
        contiguous = all(b.timestamp-a.timestamp == 60 for a,b in zip(chunk,chunk[1:]))
        if not contiguous:
            was_qualified = False
            continue
        move = bars[i].close / bars[i-window].close - 1
        qualified = move >= threshold
        if qualified and not was_qualified and bars[i].timestamp-last_event >= cooldown_seconds:
            # Explicit assumed start-label convention; complete signal bar first.
            available = bars[i].timestamp + 60
            key = str(available) + ":" + str(window) + ":" + str(threshold)
            events.append({"event_id": hashlib.sha256(key.encode()).hexdigest()[:16],
                "signal_index": i, "available_epoch": available,
                "observed_return": str(move), "window_minutes": window,
                "threshold": str(threshold),
                "prior_five_bar_low": str(min(b.low for b in bars[max(0,i-4):i+1]))})
            last_event = bars[i].timestamp
        was_qualified = qualified
    return events

def mark_outcome(bars, event, delay_seconds=60, hold_minutes=15,
                 budget=D("100"), spread=D("0.002"), fee=D("0.35"),
                 participation=D("0.01")):
    if delay_seconds < 0 or hold_minutes <= 0 or budget <= 0 or not (0 <= spread < 2) or fee < 0:
        raise DataError("Invalid execution assumptions.")
    if not (0 < participation <= 1):
        raise DataError("Invalid participation assumption.")
    times = [b.timestamp for b in bars]
    arrival = event["available_epoch"] + delay_seconds
    i = bisect_left(times, arrival)
    base = {"event_id": event["event_id"], "delay_seconds": delay_seconds,
            "hold_minutes": hold_minutes,
            "execution_tier": "modeled_bar_open_no_historical_quotes",
            "status": "missing_entry", "capital_scope": "standalone_not_portfolio"}
    # Round forward to next bar open; never fill inside the signal bar.
    if i >= len(bars) or times[i] - arrival >= 60:
        return base
    if i == 0 or times[i]-times[i-1] != 60:
        return {**base, "status": "entry_gap"}
    target = times[i] + hold_minutes * 60
    j = bisect_left(times, target)
    if j >= len(bars) or times[j] != target:
        return {**base, "status": "missing_exit"}
    if any(b.timestamp-a.timestamp != 60 for a,b in zip(bars[i:j], bars[i+1:j+1])):
        return {**base, "status": "holding_gap"}
    buy = bars[i].open * (1 + spread/2)
    sell = bars[j].open * (1 - spread/2)
    cash_qty = max(0, int(((budget-fee)/buy).to_integral_value(rounding=ROUND_FLOOR)))
    # Prior bar only: future entry-bar volume must never determine entry size.
    liquidity_qty = int((bars[i-1].volume * participation).to_integral_value(rounding=ROUND_FLOOR))
    qty = min(cash_qty, liquidity_qty)
    if qty <= 0:
        return {**base, "status": "unaffordable_or_activity_cap"}
    return {**base, "status": "modeled", "entry_epoch": times[i],
        "exit_epoch": times[j], "quantity": qty,
        "entry": str(buy), "exit": str(sell),
        "entry_cash": str(qty*buy+fee),
        "net_pnl": str(qty*(sell-buy)-2*fee),
        "liquidity_capped": qty < cash_qty,
        "spread_assumed": str(spread), "fee_per_side": str(fee),
        "previous_bar_participation_assumed": str(participation),
        "stops_or_targets_simulated": False,
        "sell_decision_delay_simulated": False}

def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2), encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--symbol", required=True)
    fetch.add_argument("--start", required=True)
    fetch.add_argument("--end", required=True)
    fetch.add_argument("--out", required=True)
    fetch.add_argument("--ask-token", action="store_true")
    replay = sub.add_parser("replay")
    replay.add_argument("--input", required=True)
    replay.add_argument("--symbol", required=True)
    replay.add_argument("--out", required=True)
    replay.add_argument("--bar-start-confirmed", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "fetch":
            token = os.environ.get("TRADIER_PRODUCTION_TOKEN")
            if not token and args.ask_token:
                token = getpass.getpass("Tradier production token (hidden; not saved): ").strip()
            if not token:
                raise DataError("No credential configured. Set TRADIER_PRODUCTION_TOKEN or use --ask-token. No request sent.")
            payload = request_data(args.symbol.upper(),args.start,args.end,token)
            token = None
            bars = parse_bars(payload)
            dump(args.out, payload)
            dump(str(args.out)+".quality.json", {
                **qualify(payload,bars), "symbol":args.symbol.upper(),
                "requested_start":args.start,"requested_end":args.end,
                "interval":"1min","session_filter":"open",
                "retrieved_at_utc":datetime.now(timezone.utc).isoformat()})
            print("Saved historical bars and quality report. Coverage remains unqualified.")
        else:
            if not args.bar_start_confirmed:
                raise DataError("Validate provider timestamp convention, then pass --bar-start-confirmed.")
            payload=json.loads(Path(args.input).read_text(encoding="utf-8"))
            bars=parse_bars(payload)
            events=benchmark_events(bars)
            for event in events:
                event["event_id"]=args.symbol.upper()+":"+event["event_id"]
            outcomes=[mark_outcome(bars,e,delay,horizon) for e in events
                for delay in (0,60,120) for horizon in (5,15,60)]
            dump(args.out, {"data_scope":args.symbol.upper(),
                "stage":"exploratory_bar_screening", "detector":"B01_price_only_5min_2pct",
                "events":events,"outcomes":outcomes,
                "limitations":["Not a complete universe or portfolio simulation.",
                    "No historical bid/ask, fills or current news inferred.",
                    "No stops, targets, adds or discretionary sell delays implemented.",
                    "Not the full 32-variant platform. Synthetic inputs prove no trading edge."]})
            print("Replay saved; inspect missing/censored cases, not just modeled outcomes.")
    except (DataError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, str(exc)+"\n")
if __name__ == "__main__":
    main()

