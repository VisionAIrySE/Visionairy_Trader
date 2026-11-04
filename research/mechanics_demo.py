"""Reproducible synthetic mechanics walkthrough; never real market evidence."""
from dataclasses import asdict
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D

from discovery_selection import SelectionPolicy
from setup_detection import MarketBar,SetupPolicy,OpportunityPolicy
from managed_replay import ReplayPolicy
from purpose_runner import run_bundle


def demo_bundle():
    start=datetime(2026,11,2,14,30,tzinfo=timezone.utc)
    series={};quotes=[];targets=[]
    # A declared synthetic calendar, not a claim about actual exchange dates.
    windows=[dict(open=int((start+timedelta(days=d)).timestamp()),
                  close=int((start+timedelta(days=d)).timestamp())+390*60) for d in range(3,6)]
    for symbol,scale in [('DEMO-A',D(1)),('DEMO-B',D('1.4'))]:
        bars=[]
        for day in range(6):
            day_start=int((start+timedelta(days=day)).timestamp())
            for minute in range(390):
                price=D('2');volume=D(10)
                if day==3 and minute>=10:
                    price=D('2.1') if minute==10 else D('2.2');volume=D(100)
                if day==4:price=D('2.35')+D(minute)/D(2000);volume=D(100)
                if day==5:price=D('2.24');volume=D(100)
                bar=MarketBar(day_start+minute*60,(start+timedelta(days=day)).date().isoformat(),
                    minute,price*scale,(price+D('.01'))*scale,(price-D('.01'))*scale,price*scale,volume,390)
                bars.append(asdict(bar))
                if day>=3:quotes.append(dict(symbol=symbol,observed_at=bar.timestamp+60,
                    bid=str(bar.close-D('.001')),ask=str(bar.close)))
        series[symbol]=bars
        targets.append(dict(symbol=symbol,available_at=windows[0]['open'],price=str(D('3')*scale),
            source_sha256='c'*64,method_version='synthetic_demo_not_prediction',horizon_minutes=780))
    return dict(universe=dict(symbols=list(series),selection_basis='broad_listing_snapshot',
        available_at=windows[0]['open']-86400,source_sha256='a'*64,calendar_source_sha256='b'*64,
        instrument_types={s:'stock' for s in series},session_windows=windows,evidence_origin='synthetic_acceptance_fixture'),
        series=series,quotes=quotes,target_hypotheses=targets,
        evaluation_start=windows[0]['open'],evaluation_end=windows[-1]['close'],
        selection_policy=asdict(SelectionPolicy('demo_selection',1,2,3,D(10000),D('.02'),D(3),D(100),30)),
        setup_policy=asdict(SetupPolicy('demo_structure',3,3,D(1),D(3),D('.1'),D('.6'),D('1.2'),60)),
        opportunity_policy=asdict(OpportunityPolicy('demo_opportunity',300,60,780,D('.02'),D(2),D(0),D(0),D(0))),
        replay_policy=asdict(ReplayPolicy('demo_two_sessions',1,0,780,7,True,D('.002'),D('.001'),D('.001'),D('.05'),D('.1'),D(2),D('.1'))),
        scenario_equity=1000,scenario_settled_cash=1000,
        portfolio_experiment=dict(settlement_sessions=1,management_variants=[dict(version='Hold initial protection'),
            dict(version='Take half at 1R',partial_at_r='1'),dict(version='Trail by 1R',trail_distance_r='1')]))


def run_demo():
    result=run_bundle(demo_bundle())
    result['demo_notice']='Synthetic mechanics walkthrough. All symbols, prices, calendar and fills are fabricated.'
    result['market_validation_ready']=False
    return result
