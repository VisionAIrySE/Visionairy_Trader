"""End-to-end intent examples; all prices/targets/calendars below are synthetic."""
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
import unittest

from discovery_selection import Observation,SelectionPolicy,scan_symbol
from setup_detection import MarketBar,SetupPolicy,OpportunityPolicy,classify_setups,assess_remaining_opportunity
from managed_replay import ReplayPolicy,replay_case,size_research_case
from purpose_pipeline import run_research
from purpose_runner import run_bundle
from dataclasses import asdict
from replay import DataError


def policies():
    select=SelectionPolicy('synthetic_intent',1,2,3,D(10000),D('.02'),D(3),D(100),30)
    setup=SetupPolicy('synthetic_structural',3,3,D(1),D(3),D('.1'),D('.6'),D('1.2'),60)
    opportunity=OpportunityPolicy('synthetic_conditional',300,60,120,D('.02'),D(2),D(0),D(0),D(0))
    replay=ReplayPolicy('synthetic_two_hours',1,0,120,3,True,D(0),D(0),D(0),D(0),D('.1'),D(2),D('.1'))
    return select,setup,opportunity,replay


def fixture():
    start=datetime(2026,11,2,14,30,tzinfo=timezone.utc)
    bars=[]
    shape={10:('2','2.11','2','2.1',100),11:('2.1','2.21','2.09','2.2',100),
           12:('2.2','2.20','2.13','2.14',40),13:('2.14','2.15','2.12','2.13',30),
           14:('2.14','2.19','2.13','2.18',90)}
    for day in range(4):
        dt=start+timedelta(days=day)
        for minute in range(180):
            values=shape.get(minute) if day==3 else None
            if values is None:
                price=D('2.18') if day==3 and minute>=15 else D(2)
                # This positive fixture sustains activity through the modeled exit.
                # The separate exit-volume test covers liquidity disappearing.
                values=(price,price+D('.01'),price-D('.01'),price,100 if day==3 and minute>=15 else 10)
            o,h,l,c,v=map(lambda x:D(str(x)),values)
            bars.append(MarketBar(int(dt.timestamp())+minute*60,dt.date().isoformat(),minute,o,h,l,c,v,180))
    a=bars[-180].timestamp;b=a+180*60
    universe=dict(symbols=['QUIET'],selection_basis='broad_listing_snapshot',available_at=a-86400,
                  source_sha256='a'*64,calendar_source_sha256='b'*64,
                  instrument_types={'QUIET':'stock'},session_windows=[{'open':a,'close':b}],
                  evidence_origin='synthetic_acceptance_fixture')
    quotes=[dict(symbol='QUIET',observed_at=row.timestamp+60,bid=str(row.close-D('.001')),ask=str(row.close))
            for row in bars[-180:]]
    targets=[dict(symbol='QUIET',available_at=a,price='2.7',source_sha256='c'*64,
                  method_version='unvalidated_fixture_hypothesis',horizon_minutes=120,
                  evidence='synthetic_unvalidated_hypothesis')]
    return bars,universe,quotes,targets,a,b


class PurposePipelineTests(unittest.TestCase):
    def run_case(self,**changes):
        bars,u,q,t,a,b=fixture();s,p,o,r=policies()
        return run_research(changes.get('universe',u),{'QUIET':changes.get('bars',bars)},s,p,o,
                            changes.get('replay_policy',r),a,b,changes.get('quotes',q),changes.get('targets',t),
                            changes.get('equity',10000),changes.get('cash',10000))

    def test_both_entry_setups_connect_to_two_hour_outcomes(self):
        result=self.run_case()
        self.assertTrue(result['coverage']['target_study_ready'])
        self.assertEqual(result['setup_counts'],{'initial_breakout':1,'pullback_continuation':1})
        self.assertEqual(result['outcome_counts'],{'modeled':2})
        self.assertTrue(all(r['exit_reason']=='time_horizon' for r in result['outcomes']))
        self.assertTrue(all(r['observed_trading_minutes']==120 for r in result['outcomes']))
        self.assertFalse(result['recommendation_qualified'])
        self.assertFalse(result['operational_assistant_ready'])
        self.assertFalse(result['profitable_strategy_demonstrated'])
        self.assertIsNone(result['portfolio_return'])
        records={r['decision_id']:r for r in result['decision_records']}
        for outcome in result['outcomes']:
            self.assertEqual(records[outcome['final_decision_id']]['opportunity_id'],outcome['opportunity_id'])
            self.assertEqual(records[outcome['entry_review_decision_id']]['kind'],'entry_review')
        self.assertTrue(all(r['mode']=='counterfactual' for r in records.values()))

    def test_source_bundle_runs_the_same_joined_path(self):
        bars,u,q,t,a,b=fixture();s,p,o,r=policies()
        bundle=dict(universe=u,series={'QUIET':[asdict(bar) for bar in bars]},
                    selection_policy=asdict(s),setup_policy=asdict(p),opportunity_policy=asdict(o),
                    replay_policy=asdict(r),evaluation_start=a,evaluation_end=b,quotes=q,
                    target_hypotheses=t,scenario_equity=10000,scenario_settled_cash=10000)
        result=run_bundle(bundle)
        self.assertEqual(result['setup_counts'],{'initial_breakout':1,'pullback_continuation':1})
        self.assertFalse(result['operational_assistant_ready'])

    def test_no_price_target_or_quotes_no_hypothetical_profit(self):
        result=self.run_case(quotes=[],targets=[])
        self.assertEqual(result['status'],'outcome_evidence_incomplete')
        self.assertTrue(all(r['net_pnl'] is None for r in result['outcomes']))

    def test_target_inside_cost_risk_boundary_is_track_only(self):
        _,_,_,targets,_,_=fixture()
        targets[0]['price']='2.11'
        result=self.run_case(targets=targets)
        self.assertFalse(any(r['state']=='conditional_research_case' for r in result['assessments']))

    def test_future_target_cannot_be_used_to_enter_earlier(self):
        _,_,_,targets,_,end=fixture();targets[0]['available_at']=end+1
        result=self.run_case(targets=targets)
        self.assertTrue(all(r['net_pnl'] is None for r in result['outcomes']))

    def test_unaffordable_setup_stays_discovered_and_track_only(self):
        result=self.run_case(equity=10,cash=1)
        self.assertEqual(sum(result['setup_counts'].values()),2)
        self.assertTrue(all(r['status']=='track_only_risk_cash_or_activity' for r in result['outcomes']))

    def test_partial_or_convenience_universe_cannot_reach_outcome_stage(self):
        _,u,_,_,_,_=fixture();u['selection_basis']='convenience'
        result=self.run_case(universe=u)
        self.assertEqual(result['status'],'blocked_data_or_intent_fit')
        self.assertEqual(result['outcomes'],[])

    def test_missing_current_calendar_bar_blocks_complete_study(self):
        bars,_,_,_,_,_=fixture();del bars[-30]
        result=self.run_case(bars=bars)
        self.assertEqual(result['status'],'blocked_data_or_intent_fit')

    def test_stale_quotes_do_not_become_recommendations(self):
        _,_,quotes,_,start,_=fixture()
        result=self.run_case(quotes=[dict(quotes[0],observed_at=start-600)])
        self.assertTrue(all(r['state']=='insufficient_evidence' for r in result['assessments']))

    def test_target_horizon_must_fit_hours_to_days_experiment(self):
        _,_,_,targets,_,_=fixture();targets[0]['horizon_minutes']=10000
        result=self.run_case(targets=targets)
        self.assertTrue(all('target_not_supported_in_intended_holding_window' in r['reasons'] for r in result['assessments']))

    def test_stalled_pullback_is_not_resumed_momentum(self):
        bars,u,_,_,_,_=fixture()
        # Keep the initial activation, but eliminate higher-price follow-through.
        for i,b in enumerate(bars):
            if b.session=='2026-11-05' and b.minute>=14:
                bars[i]=replace(b,open=D('2.13'),high=D('2.14'),low=D('2.12'),close=D('2.13'),volume=D(10))
        s,p,_,_=policies()
        observations=[Observation(b.timestamp,b.session,b.minute,b.close,b.volume,b.session_minutes) for b in bars]
        events=classify_setups('QUIET',bars,scan_symbol('QUIET',observations,s),s,p)
        self.assertEqual([e['setup'] for e in events],['initial_breakout'])

    def test_late_extended_breakout_does_not_pass_structure_gate(self):
        bars,_,_,_,_,_=fixture();s,p,_,_=policies()
        p=replace(p,maximum_extension_atr=D('.1'))
        observations=[Observation(b.timestamp,b.session,b.minute,b.close,b.volume,b.session_minutes) for b in bars]
        events=classify_setups('QUIET',bars,scan_symbol('QUIET',observations,s),s,p)
        self.assertFalse(any(e['setup']=='initial_breakout' for e in events))


class RiskAndExitTests(unittest.TestCase):
    def event_and_assessment(self):
        bars,u,q,t,a,b=fixture();s,p,o,r=policies()
        obs=[Observation(x.timestamp,x.session,x.minute,x.close,x.volume,x.session_minutes) for x in bars]
        event=classify_setups('QUIET',bars,scan_symbol('QUIET',obs,s),s,p)[0]
        quote=next(x for x in q if x['observed_at']==event['available_at'])
        assessed=assess_remaining_opportunity(event,quote,t[0],event['available_at'],o)
        return bars,u,event,assessed,r

    def test_wider_stop_reduces_size_instead_of_increasing_risk(self):
        a=size_research_case(10,9,10000,10000,0,0,0,0)
        b=size_research_case(10,8,10000,10000,0,0,0,0)
        self.assertEqual(a['quantity'],100);self.assertEqual(b['quantity'],50)
        self.assertEqual(a['planned_risk'],b['planned_risk'])
        self.assertEqual(b['stop_unchanged'],'8')

    def test_addition_uses_remaining_trade_budget_not_a_new_one_percent(self):
        row=size_research_case(10,9,10000,10000,80,80,0,0)
        self.assertEqual(row['quantity'],20)

    def test_aggregate_risk_ceiling_blocks_additional_exposure(self):
        row=size_research_case(10,9,10000,10000,0,500,0,0)
        self.assertEqual(row['quantity'],0)

    def test_stop_risk_includes_both_fees_and_exit_friction(self):
        row=size_research_case(10,9,10000,10000,0,0,D('.35'),D('.01'),exit_spread_fraction=D('.02'))
        self.assertLessEqual(D(row['planned_risk']),D(100))
        self.assertGreater(D(row['planned_risk'])/row['quantity'],D(1))

    def test_risk_ceiling_cannot_be_raised_by_research_parameter(self):
        with self.assertRaises(DataError):size_research_case(10,9,10000,10000,0,0,0,0,per_trade_fraction=D('.02'))

    def test_stop_target_same_bar_uses_conservative_stop_first(self):
        bars,u,event,assessment,r=self.event_and_assessment()
        index=next(i for i,b in enumerate(bars) if b.timestamp==event['available_at'])
        bars[index]=replace(bars[index],low=D('1.5'),high=D(3))
        row=replay_case(event,assessment,bars,u['session_windows'],r,D(10000),D(10000))
        self.assertEqual(row['exit_reason'],'protective_stop')
        self.assertLess(D(row['net_pnl']),0)

    def test_entry_delay_rechecks_remaining_opportunity(self):
        bars,u,event,assessment,r=self.event_and_assessment()
        index=next(i for i,b in enumerate(bars) if b.timestamp==event['available_at'])
        bars[index]=replace(bars[index],open=D('2.7'),high=D('2.71'),low=D('2.6'),close=D('2.7'))
        row=replay_case(event,assessment,bars,u['session_windows'],r,D(10000),D(10000))
        self.assertEqual(row['status'],'track_only_changed_entry_terms')
        self.assertIsNone(row['net_pnl'])

    def test_expired_opportunity_cannot_be_reused_after_entry_delay(self):
        bars,u,event,assessment,r=self.event_and_assessment()
        row=replay_case(event,assessment,bars,u['session_windows'],replace(r,entry_delay_seconds=360),10000,10000)
        self.assertEqual(row['status'],'track_only_expired_opportunity')
        self.assertIsNone(row['net_pnl'])

    def test_missing_horizon_never_becomes_zero_return(self):
        bars,u,event,assessment,r=self.event_and_assessment()
        shorter=[b for b in bars if b.timestamp<event['available_at']+60*60]
        row=replay_case(event,assessment,shorter,u['session_windows'],r,D(10000),D(10000))
        self.assertTrue(row['status'].startswith('censored_'));self.assertIsNone(row['net_pnl'])

    def test_exit_volume_uses_prior_observation_not_future_volume(self):
        bars,u,event,assessment,r=self.event_and_assessment()
        exit_time=event['available_at']+120*60
        i=next(i for i,b in enumerate(bars) if b.timestamp==exit_time)
        bars[i-1]=replace(bars[i-1],volume=D(0))
        row=replay_case(event,assessment,bars,u['session_windows'],r,D(10000),D(10000))
        self.assertEqual(row['status'],'censored_exit_activity')
        self.assertIsNone(row['net_pnl'])

    def test_overnight_gap_can_exceed_planned_stop_loss(self):
        bars,u,event,assessment,r=self.event_and_assessment()
        start=u['session_windows'][0]['open'];end=u['session_windows'][0]['close']
        # Enter late enough that a 2-hour hold spans the supplied next session.
        event=dict(event,available_at=end-20*60,proposed_stop='1.99')
        _,_,op,_=policies()
        assessment=assess_remaining_opportunity(event,
                 dict(symbol='QUIET',observed_at=event['available_at'],bid='2.179',ask='2.18'),
                 assessment['target_provenance'],event['available_at'],op)
        next_open=start+86400
        next_day=[MarketBar(next_open+i*60,'2026-11-06',i,D('1.5'),D('1.51'),D('1.49'),D('1.5'),D(10000),180) for i in range(180)]
        calendar=u['session_windows']+[{'open':next_open,'close':next_open+180*60}]
        row=replay_case(event,assessment,bars+next_day,calendar,r,D(10000),D(10000))
        self.assertEqual(row['exit_reason'],'gap_through_stop')
        self.assertGreater(-D(row['net_pnl']),D(row['planned_risk']))

    def test_changed_stop_or_target_requires_new_assessment(self):
        bars,u,event,assessment,r=self.event_and_assessment()
        with self.assertRaises(DataError):
            replay_case(dict(event,proposed_stop='1.5'),assessment,bars,u['session_windows'],r,10000,10000)
        assessment['target_provenance']['price']='100'
        with self.assertRaises(DataError):
            replay_case(event,assessment,bars,u['session_windows'],r,10000,10000)


if __name__=='__main__':unittest.main()
