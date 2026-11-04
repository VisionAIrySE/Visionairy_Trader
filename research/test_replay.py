import io
import json
import unittest
from decimal import Decimal as D
from unittest.mock import patch
from urllib.error import HTTPError
from replay import (Bar, DataError, ENDPOINT, NoRedirect, benchmark_events,
                    mark_outcome, parse_bars, request_data, qualify)

T = 1793716200

def fixture(n=100):
    bars=[]
    for i in range(n):
        price=D("100") if i<6 else D("103")
        bars.append(Bar(T+i*60,price,price+D("0.1"),price-D("0.1"),price,D(10000)))
    return bars

class ReplayTests(unittest.TestCase):
    def test_signal_waits_for_bar_completion(self):
        bars=fixture()
        e=benchmark_events(bars)[0]
        self.assertEqual(e["signal_index"],6)
        self.assertEqual(e["available_epoch"],T+7*60)
        r=mark_outcome(bars,e,0,5,budget=D(200))
        self.assertEqual(r["entry_epoch"],T+7*60)
    def test_delay_forward_not_backward(self):
        bars=fixture(); e=benchmark_events(bars)[0]
        r=mark_outcome(bars,e,30,5,budget=D(200))
        self.assertEqual(r["entry_epoch"],T+8*60)
    def test_no_repeated_burst_when_still_above_threshold(self):
        self.assertEqual(len(benchmark_events(fixture())),1)
    def test_future_prices_do_not_change_past_signals(self):
        bars=fixture()
        cutoff=bars[:20]
        early=benchmark_events(cutoff)
        changed=cutoff+[Bar(T+i*60,D(200),D(201),D(199),D(200),D(1)) for i in range(20,100)]
        self.assertEqual(early,[e for e in benchmark_events(changed) if e["signal_index"]<20])
    def test_discontinuous_window_cannot_trigger(self):
        bars=fixture()
        bars=[b for i,b in enumerate(bars) if i!=4]
        self.assertTrue(all(e['available_epoch'] >= T+11*60 for e in benchmark_events(bars)))
    def test_missing_horizon_is_censored(self):
        bars=fixture(10); e=benchmark_events(bars)[0]
        self.assertEqual(mark_outcome(bars,e,0,60)["status"],"missing_exit")
    def test_volume_cap_uses_only_past_bar(self):
        bars=fixture(); e=benchmark_events(bars)[0]
        i=e["signal_index"]+1
        b=bars[i]; bars[i]=Bar(b.timestamp,b.open,b.high,b.low,b.close,D(0))
        a=mark_outcome(bars,e,0,5,budget=D(1000))
        self.assertEqual(a["quantity"],9)
        b=bars[i-1]; bars[i-1]=Bar(b.timestamp,b.open,b.high,b.low,b.close,D(100))
        capped=mark_outcome(bars,e,0,5,budget=D(1000))
        self.assertEqual(capped["quantity"],1)
    def test_spread_and_fees_both_sides(self):
        bars=fixture(); e=benchmark_events(bars)[0]
        r=mark_outcome(bars,e,0,5,budget=D(200))
        self.assertLess(D(r["net_pnl"]),0)
        self.assertEqual(D(r["net_pnl"]),D("-0.906"))
    def test_duplicate_bars_rejected(self):
        row=dict(timestamp=T,open=100,high=101,low=99,close=100,volume=100)
        with self.assertRaises(DataError):
            parse_bars({"series":{"data":[row,row]}})
    def test_millisecond_epoch_rejected(self):
        row=dict(timestamp=T*1000,open=100,high=101,low=99,close=100,volume=100)
        with self.assertRaises(DataError):
            parse_bars({"series":{"data":[row]}})
    def test_arbitrary_symbols_rejected_before_network(self):
        with self.assertRaises(DataError):
            request_data("../accounts/orders","2026-10-21 09:30","2026-11-03 16:00","TEST")
    def test_get_only_fixed_market_endpoint(self):
        payload={"series":{"data":[]}}
        response=io.BytesIO(json.dumps(payload).encode())
        class Opener:
            def open(self,request,timeout):
                self.request=request
                return response
        op=Opener()
        request_data("SPY","2026-10-21 09:30","2026-11-03 16:00","TEST",op)
        self.assertEqual(op.request.get_method(),"GET")
        self.assertTrue(op.request.full_url.startswith(ENDPOINT+"?"))
    def test_redirect_rejected(self):
        with self.assertRaises(DataError):
            NoRedirect().redirect_request(None,None,302,"",None,"https://elsewhere.test")
    def test_quota400_detected_without_error_body_leak(self):
        class Opener:
            def open(self,request,timeout):
                raise HTTPError(ENDPOINT,400,"",{},io.BytesIO(b"Quota Violation SECRET"))
        with self.assertRaises(DataError) as ctx:
            request_data("SPY","2026-10-21 09:30","2026-11-03 16:00","TEST",Opener())
        self.assertNotIn("SECRET",str(ctx.exception))
        self.assertIn("quota",str(ctx.exception))
    def test_no_token_stops_before_network(self):
        with self.assertRaises(DataError):
            request_data("SPY","2026-10-21 09:30","2026-11-03 16:00","")
    def test_quality_does_not_infer_quotes(self):
        row=dict(timestamp=T,open=100,high=101,low=99,close=100,volume=100)
        p={"series":{"data":[row]}}
        self.assertFalse(qualify(p,parse_bars(p))["approved_for_exact_execution_claims"])
if __name__ == "__main__":
    unittest.main()

