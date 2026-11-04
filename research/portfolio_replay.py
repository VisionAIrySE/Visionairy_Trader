"""Joint chronological counterfactual cash/position experiments, not live orders."""
from collections import defaultdict, Counter
from dataclasses import asdict
from decimal import Decimal as D

from acquisition_funnel import AllocationPolicy, plan_acquisitions
from management_replay import ManagementPolicy, replay_management
from portfolio_ledger import PaperLedger
from replay import DataError
from setup_detection import fingerprint


def replay_portfolio(setups,assessments,series,calendar,source_sha256,equity,cash,
                     opportunity_policy,replay_policy,settlement_sessions,management):
    if D(str(equity))!=D(str(cash)):
        raise DataError('Joint experiment starts flat; initial equity must equal settled cash')
    if len({e['event_id'] for e in setups})!=len(setups):raise DataError('Duplicate portfolio opportunity')
    ledger=PaperLedger(cash,calendar,settlement_sessions,'joint_paper_v1')
    policy=AllocationPolicy('joint_acquisition_v1',('discovery','setup','opportunity','liquidity'),
        opportunity_policy.maximum_signal_age_seconds,opportunity_policy.minimum_net_reward_to_risk,
        replay_policy.fee_per_side,replay_policy.exit_slippage,replay_policy.assumed_full_spread)
    matched={a['event_id']:a for a in assessments};events=defaultdict(list);completed=defaultdict(list)
    step=replay_policy.bar_minutes*60
    for e in setups:events[e['available_at']].append(e)
    for symbol,bars in series.items():
        for b in bars:completed[b.timestamp+step].append((symbol,b))
    pending=defaultdict(list);snapshots=[];outcomes=[];valuations=[]
    clock=sorted({t for w in calendar for t in range(w['open'],w['close']+step,step)}|set(events)
                 |{a['valid_until'] for a in assessments if type(a.get('valid_until')) is int})
    def apply_scheduled(now):
        for kind,event,row,payload in pending.pop(now,[]):
            symbol=event['symbol'];identity=event['event_id']
            if kind=='nonfill':
                if identity in ledger.reservations:ledger.cancel(identity,row['status'])
            elif kind=='entry':
                ledger.snapshot(opportunity_policy.maximum_quote_age_seconds)
                entered=ledger.enter(identity,row['quantity'],row['entry_price'],replay_policy.fee_per_side,row['planned_risk'])
                if not entered:row.update(status='not_filled_current_portfolio_risk',net_pnl=None,entry_blocked_by_ledger=True)
            elif symbol in ledger.positions and ledger.positions[symbol]['event_id']==identity:
                ledger.exit(symbol,payload['quantity'],payload['price'],payload['fee'],payload['reason'])
    for now in clock:
        ledger.advance(now)
        for symbol,bar in completed.get(now,[]):ledger.mark(symbol,bar.close,now)
        apply_scheduled(now)
        if now in events:
            account=ledger.snapshot(opportunity_policy.maximum_quote_age_seconds)
            candidates=[]
            for event in events[now]:
                assessment=matched[event['event_id']]
                prior=[b for b in series[event['symbol']] if b.timestamp+step<=now]
                latest=prior[-1] if prior else None
                def evidence(state):return dict(status=state,available_at=now,source_sha256=[source_sha256])
                candidates.append(dict(event=event,assessment=assessment,
                    evidence_groups=dict(discovery=evidence('pass'),setup=evidence('pass'),
                        opportunity=evidence('pass' if assessment['state']=='conditional_research_case' else 'unknown'),
                        liquidity=evidence('pass' if latest else 'unknown')),
                    maximum_quantity_from_liquidity=int(latest.volume*replay_policy.prior_volume_participation) if latest else None,
                    liquidity_available_at=latest.timestamp+step if latest else None))
            snapshot=plan_acquisitions(candidates,account,policy,now);snapshots.append(snapshot)
            for reservation in snapshot['reviews']:
                identity=reservation['event_id'];event=next(e for e in events[now] if e['event_id']==identity)
                if reservation['state']!='conditional_research_reservation':
                    outcomes.append(dict(event_id=identity,status='not_selected_by_joint_plan',quantity=0,
                        reasons=reservation['reasons'],net_pnl=None));continue
                ledger.reserve(reservation)
                row=replay_management(event,matched[identity],series[event['symbol']],calendar,replay_policy,
                                      D(account['equity']),reservation,management)
                outcomes.append(row)
                if row.get('quantity'):
                    pending[row['entry_at']].append(('entry',event,row,None))
                    for fill in row['fills']:pending[fill['at']].append(('exit',event,row,fill))
                else:
                    effective=row.get('entry_at',matched[identity]['valid_until'])
                    pending[effective].append(('nonfill',event,row,None))
            apply_scheduled(now)
        account=ledger.snapshot(opportunity_policy.maximum_quote_age_seconds)
        valuations.append(dict(at=now,equity=account['equity'],available_cash=account['settled_cash'],
            unsettled_proceeds=account['unsettled_proceeds'],planned_risk=account['total_open_risk'],
            paused=account['pause']['paused_for_session'],valuation_fresh=account['valuation_fresh']))
    final=ledger.report()
    unresolved=bool(final['positions'] or final['reservations'] or pending)
    return dict(status='joint_counterfactual_incomplete' if unresolved else 'joint_counterfactual_closed',
        management=asdict(management),management_sha256=fingerprint(asdict(management)),
        input_sha256=fingerprint(dict(setups=setups,assessments=assessments,
            series={s:[asdict(b) for b in bars] for s,bars in series.items()},calendar=calendar,
            replay_policy=asdict(replay_policy),opportunity_policy=asdict(opportunity_policy),
            settlement_sessions=settlement_sessions,source_sha256=source_sha256,cash=str(cash),equity=str(equity))),
        snapshots=snapshots,outcomes=outcomes,outcome_counts=dict(Counter(r['status'] for r in outcomes)),
        ledger=final,valuations=valuations,
        net_account_return=None if unresolved else str((ledger.equity()-ledger.initial_cash)/ledger.initial_cash),
        observed_execution=False,orders_submitted=0,operational_assistant_ready=False,
        profitable_strategy_demonstrated=False,
        limitations=['experimental_settlement_lag_not_broker_qualification','no_additions_or_correlated_exposure_caps',
            'bar_liquidity_and_fills_are_modeled','management_policies_are_not_adopted_rules'])


def compare_management(setups,assessments,series,calendar,source_sha256,equity,cash,
                       opportunity_policy,replay_policy,settlement_sessions,variants):
    policies=[ManagementPolicy(**v) for v in variants]
    if not policies or len({p.version for p in policies})!=len(policies):
        raise DataError('Distinct declared management variants required')
    results=[replay_portfolio(setups,assessments,series,calendar,source_sha256,equity,cash,
        opportunity_policy,replay_policy,settlement_sessions,p) for p in policies]
    return dict(status='conditional_management_comparison',variants=results,
        comparison_unit='same_opportunities_and_initial_account_alternative_paths_not_independent_trades',
        variant_policy_sha256=fingerprint(variants),automatic_strategy_adoption=False,
        profitable_strategy_demonstrated=False,orders_submitted=0)
