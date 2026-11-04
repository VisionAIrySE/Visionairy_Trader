"""Deterministic sizing/cost preflight. No network, credentials or broker actions.
Synthetic arithmetic only: not historical/forward strategy performance.
"""
from decimal import Decimal, ROUND_FLOOR
from itertools import product
import json
from pathlib import Path

D = Decimal

def scenario(budget, midpoint, spread_pct, stop_pct, commission, gain_pct="0.05"):
    budget, mid, spread, stop, fee, gain = map(D, map(str,
        (budget, midpoint, spread_pct, stop_pct, commission, gain_pct)))
    if budget <= 0 or mid <= 0 or not (0 <= spread < 2) or not (0 < stop < 1) or fee < 0:
        raise ValueError("Invalid scenario")
    ask = mid * (1 + spread / 2)
    qty = max(0, int(((budget - fee) / ask).to_integral_value(rounding=ROUND_FLOOR)))
    if not qty:
        return {"budget": str(budget), "midpoint": str(mid), "spread_pct": str(spread),
                "stop_pct": str(stop), "commission_per_side": str(fee),
                "quantity": 0, "status": "unaffordable"}
    entry = qty * ask + fee
    unchanged_bid = mid * (1 - spread / 2)
    stop_bid = mid * (1 - stop) * (1 - spread / 2)
    gain_bid = mid * (1 + gain) * (1 - spread / 2)
    friction = entry - (qty * unchanged_bid - fee)
    stop_loss = entry - (qty * stop_bid - fee)
    net_gain = qty * gain_bid - fee - entry
    break_even = (ask + 2 * fee / qty) / unchanged_bid - 1
    return {"budget": str(budget), "midpoint": str(mid), "spread_pct": str(spread),
            "stop_pct": str(stop), "commission_per_side": str(fee),
            "quantity": qty, "status": "calculated", "entry_cash": str(entry),
            "unchanged_midpoint_roundtrip_loss": str(friction),
            "modeled_stop_loss": str(stop_loss),
            "break_even_midpoint_rise": str(break_even),
            "net_at_5pct_midpoint_rise": str(net_gain),
            "within_2dollar_loss_budget": stop_loss <= 2}

def run():
    rows = [scenario(*args) for args in product(
        [25, 50, 100, 250, 500], [1, 5, 25, 100],
        ["0.002", "0.01", "0.03"], ["0.01", "0.03", "0.05"], ["0", "0.35"])]
    result = {"type": "synthetic_arithmetic_not_market_performance",
              "count": len(rows),
              "assumptions": [
                  "Budget includes entry commission; whole shares only.",
                  "Full fill assumed only to calculate an arithmetic boundary, not a fill prediction.",
                  "Symmetric spread as fraction of midpoint, unchanged at exit.",
                  "Stop distance and 5% move are midpoint changes from initial midpoint.",
                  "No slippage, gaps, regulatory fees, taxes, fixed subscription or hosting costs.",
                  "Broker funding and data entitlement have not been tested."
              ], "scenarios": rows}
    Path("preflight_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"scenarios": len(rows),
        "unaffordable": sum(x["status"] == "unaffordable" for x in rows),
        "calculated": sum(x["status"] == "calculated" for x in rows)}))
    for budget in [25,50,100]:
        for fee in ["0","0.35"]:
            print(json.dumps(scenario(budget, 5, "0.002", "0.03", fee)))

if __name__ == "__main__":
    run()

