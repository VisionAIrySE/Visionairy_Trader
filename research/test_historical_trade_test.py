from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch
import unittest
from historical_trade_test import run,summarize
from setup_detection import MarketBar

class HistoricalTradeTests(unittest.TestCase):
    def test_source_cohort_runs_real_replay_arithmetic_and_shared_ledger(self):
        start=datetime(2026,11,2,14,30,tzinfo=timezone.utc);bars=[];calendar=[]
        for day in range(3):
            dt=start+timedelta(days=day);stamp=int(dt.timestamp())
            calendar.append(dict(open=stamp,close=stamp+390*60))
            for minute in range(0,390,5):
                price=D('10') if day==0 and minute<30 else D('14.1')
                high=price+D('.1');low=price-D('.1');volume=D(1000)
                if day==0 and minute==30:price=D(11);high=D('11.1');low=D('10.9');volume=D(5000)
                if day==0 and minute==35:price=D(11);high=D('14.5');low=D('10.9');volume=D(5000)
                bars.append(MarketBar(stamp+minute*60,dt.date().isoformat(),minute,price,high,low,price,volume,390))
        coverage=[dict(symbol='FIXTURE',status='observed',source_sha256='a'*64,complete_for_portfolio=True)]
        args=({'FIXTURE':bars},coverage,calendar,dict(coverage=coverage,calendar=calendar,source='synthetic_fixture'))
        with patch('historical_trade_test.load_histories',return_value=args):
            report=run('unused',Path(__file__).with_name('historical_experiment.json'))
        primary=next(s for s in report['scenarios'] if s['name']=='3R_base')
        self.assertGreater(primary['portfolio_summary']['closed_trades'],0)
        ledger=primary['portfolio']['ledger']
        self.assertEqual(D(ledger['marked_equity']),D(1000)+D(ledger['realized_net_pnl']))
        self.assertEqual(ledger['positions'],{});self.assertEqual(ledger['reservations'],{})
        self.assertEqual(D(primary['portfolio_summary']['closed_trade_net_pnl']),D(ledger['realized_net_pnl']))
        self.assertEqual(report['orders_submitted'],0)
        self.assertTrue(all(s['portfolio']['ledger']['initial_cash']=='1000.00' for s in report['scenarios']))

    def test_censored_cases_do_not_become_zero_profit_or_closed_trades(self):
        result=summarize([dict(status='modeled',net_pnl='5',quantity=1),
            dict(status='censored_holding_gap',net_pnl=None,quantity=2),
            dict(status='not_selected_by_joint_plan',net_pnl=None,quantity=0)])
        self.assertEqual(result['closed_trades'],1);self.assertEqual(result['closed_trade_net_pnl'],'5')
        self.assertEqual(result['unresolved_entered'],1)
