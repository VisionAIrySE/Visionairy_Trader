"""One purpose-aligned research path: coverage -> discovery -> setup -> opportunity -> outcome.

Completion of software components never promotes missing market evidence, user
approval, unvalidated targets, or independent order cases into platform readiness.
"""
from collections import Counter
from dataclasses import asdict
from decimal import Decimal as D
import re

from discovery_selection import Observation,scan_symbol,study_gate
from setup_detection import classify_setups,assess_remaining_opportunity,validate_bars,fingerprint
from managed_replay import replay_case
from decision_analysis import DecisionGraph
from replay import DataError
from acquisition_funnel import plan_research_series, replay_acquisition_plan


def _known_at(records,symbol,cutoff):
    available=[r for r in records if r.get('symbol')==symbol and type(r.get('available_at',r.get('observed_at'))) is int
               and r.get('available_at',r.get('observed_at'))<=cutoff]
    return max(available,key=lambda r:r.get('available_at',r.get('observed_at'))) if available else None


def run_research(universe,series,selection_policy,setup_policy,opportunity_policy,replay_policy,
                 evaluation_start,evaluation_end,quotes,targets,equity,settled_cash):
    if selection_policy.bar_minutes!=replay_policy.bar_minutes:
        raise DataError('Discovery and replay bar durations must agree')
    if opportunity_policy.maximum_target_horizon_minutes>replay_policy.holding_trading_minutes:
        raise DataError('Target evidence cannot exceed the tested holding horizon')
    if not universe.get('evidence_origin') in ('historical_market_data','synthetic_acceptance_fixture'):
        raise DataError('Explicit data evidence origin required')
    for bars in series.values():validate_bars(bars,selection_policy.bar_minutes)
    observations={symbol:[Observation(b.timestamp,b.session,b.minute,b.close,b.volume,b.session_minutes)
                         for b in bars] for symbol,bars in series.items()}
    decisions={symbol:scan_symbol(symbol,rows,selection_policy,
                  known_discontinuities=universe.get('discontinuity_sessions',{}).get(symbol,[]))
               for symbol,rows in observations.items()}
    all_decisions=[r for rows in decisions.values() for r in rows]
    gate=study_gate(universe,observations,evaluation_start,evaluation_end,all_decisions,
                    selection_policy.bar_minutes)
    # Content/source identity and independently qualified calendar are additional
    # requirements of this joined path; current exchange listings alone cannot pass.
    for field in ('source_sha256','calendar_source_sha256'):
        if not re.fullmatch('[0-9a-f]{64}',str(universe.get(field,''))):
            gate['reasons'].append('missing_qualified_'+field)
    gate['target_study_ready']=not gate['reasons']
    relevant=[r for r in all_decisions if evaluation_start<=r['available_at']<evaluation_end]
    result=dict(status='blocked_data_or_intent_fit',coverage=gate,
                experiment_cohort='quiet_to_active',
                evidence_origin=universe['evidence_origin'],
                input_sha256=fingerprint({s:[asdict(b) for b in bars] for s,bars in series.items()}),
                policy_sha256=fingerprint([asdict(selection_policy),asdict(setup_policy),
                                           asdict(opportunity_policy),asdict(replay_policy)]),
                discovery_states=dict(Counter(r['state'] for r in relevant)),
                setup_counts={'initial_breakout':0,'pullback_continuation':0},
                setups=[],assessments=[],outcomes=[],decision_records=[],acquisition_plan=None,
                acquisition_outcomes=None,
                recommendation_qualified=False,operational_assistant_ready=False,
                profitable_strategy_demonstrated=False,portfolio_return=None,
                missing_platform_evidence=['representative_real_market_candidates',
                    'validated_remaining_opportunity_model','joint_portfolio_and_settlement',
                    'correlation_and_giveback_rules','broker_protective_order_qualification',
                    'authenticated_approval_delivery','hosted_recovery_and_cost_qualification',
                    'held_out_and_forward_validation'])
    if not gate['target_study_ready']:return result
    graph=DecisionGraph()
    roots={}
    source_evidence=dict(source_ids=[universe['source_sha256']],
                         evidence_origin=universe['evidence_origin'],actor='counterfactual_policy_not_user')
    for decision in relevant:
        if decision['state']=='quiet_to_active_candidate':
            root=graph.record(decision['event_id'],[],'discovery','observe',decision['available_at'],
                              decision['available_at'],decision,source_evidence,
                              selection_policy.version)
            roots[decision['event_id']]=root
    for symbol,bars in series.items():
        events=[e for e in classify_setups(symbol,bars,decisions[symbol],selection_policy,setup_policy)
                if evaluation_start<=e['available_at']<evaluation_end]
        result['setups'].extend(events)
        for event in events:
            root=roots.get(event['activation_id'])
            if root is None:
                raise DataError('Setup cannot detach from its discovery evidence')
            review=graph.record(root.opportunity_id,[root.decision_id],'entry_review','wait',
                                event['available_at'],event['available_at'],event,source_evidence,
                                setup_policy.version)
            quote=_known_at(quotes,symbol,event['available_at'])
            target=_known_at(targets,symbol,event['available_at'])
            assessment=assess_remaining_opportunity(event,quote,target,event['available_at'],opportunity_policy)
            considered=graph.record(root.opportunity_id,[review.decision_id],'entry_review',
                        'enter' if assessment['state']=='conditional_research_case' else 'wait',
                        event['available_at'],event['available_at'],assessment,source_evidence,
                        opportunity_policy.version)
            result['assessments'].append(assessment)
            outcome=replay_case(event,assessment,bars,universe['session_windows'],
                                    replay_policy,D(str(equity)),D(str(settled_cash)))
            if outcome.get('quantity'):
                sized=graph.record(root.opportunity_id,[considered.decision_id],'sizing','retain',
                            outcome['entry_at'],outcome['entry_at'],
                            {k:outcome[k] for k in ('quantity','entry_cash','planned_risk','stop_price')},
                            source_evidence,replay_policy.version)
                entry=graph.record(root.opportunity_id,[sized.decision_id],'execution','filled',
                            outcome['entry_at'],outcome['entry_at'],
                            dict(price=outcome['entry_price'],quantity=outcome['quantity'],
                                 evidence='conditional_bar_model_not_actual_fill'),source_evidence,replay_policy.version)
                if outcome['status']=='modeled':
                    exit_record=graph.record(root.opportunity_id,[entry.decision_id],'exit_review','exit',
                               outcome['exit_at'],outcome['exit_at'],
                               dict(price=outcome['exit_price'],reason=outcome['exit_reason'],
                                    net_pnl=outcome['net_pnl']),source_evidence,replay_policy.version)
                    outcome['final_decision_id']=exit_record.decision_id
            outcome['opportunity_id']=root.opportunity_id
            outcome['entry_review_decision_id']=considered.decision_id
            result['outcomes'].append(outcome)
    result['setup_counts'].update(Counter(e['setup'] for e in result['setups']))
    result['status']='conditional_research_replay_only'
    result['outcome_counts']=dict(Counter(r['status'] for r in result['outcomes']))
    if not result['setups']:result['status']='no_qualified_entry_setup'
    elif not any(r['status']=='modeled' for r in result['outcomes']):result['status']='outcome_evidence_incomplete'
    result['decision_records']=[asdict(r) for r in graph.records]
    result['acquisition_plan']=plan_research_series(result['setups'], result['assessments'],
        series, universe['source_sha256'], equity, settled_cash, opportunity_policy, replay_policy)
    result['acquisition_outcomes']=replay_acquisition_plan(result['acquisition_plan'],
        result['setups'], result['assessments'], series, universe['session_windows'], replay_policy, equity)
    return result
