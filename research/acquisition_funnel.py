"""Point-in-time research allocation, never an order or a return forecast.

Evidence gates precede transparent conditional risk-efficiency ranking. Shared
cash/risk reservations are one snapshot, not a settlement or portfolio simulator.
No outcome, subsequent high, ticker price ceiling or account-affordability filter
is allowed to determine discovery. Every reviewed candidate remains in output.
"""
from dataclasses import dataclass, asdict
from decimal import Decimal as D

from managed_replay import size_research_case, replay_case
from replay import DataError
from setup_detection import fingerprint


def number(value):
    try:
        result = D(str(value))
        if not result.is_finite():
            raise ValueError()
        return result
    except (ValueError, TypeError, ArithmeticError):
        raise DataError('Finite numeric evidence required') from None


@dataclass(frozen=True)
class AllocationPolicy:
    version: str
    required_evidence_groups: tuple
    maximum_evidence_age_seconds: int
    minimum_net_reward_to_risk: D
    fee_per_side: D
    exit_slippage: D
    exit_full_spread: D
    ranking_order: tuple = ('net_reward_to_risk', 'conditional_roi')

    def __post_init__(self):
        if not self.version or type(self.maximum_evidence_age_seconds) is not int or self.maximum_evidence_age_seconds < 0:
            raise DataError('Versioned allocation/freshness policy required')
        groups = tuple(self.required_evidence_groups)
        if not groups or len(groups) != len(set(groups)) or any(not isinstance(g, str) or not g for g in groups):
            raise DataError('Distinct explicit evidence groups required')
        object.__setattr__(self, 'required_evidence_groups', groups)
        ranking = tuple(self.ranking_order)
        if not ranking or len(ranking) != len(set(ranking)) or any(k not in ('net_reward_to_risk', 'conditional_roi') for k in ranking):
            raise DataError('Explicit supported financial comparison order required')
        object.__setattr__(self, 'ranking_order', ranking)
        for field in ('minimum_net_reward_to_risk', 'fee_per_side', 'exit_slippage', 'exit_full_spread'):
            object.__setattr__(self, field, number(getattr(self, field)))
        if self.minimum_net_reward_to_risk <= 0 or self.fee_per_side < 0 or not 0 <= self.exit_slippage < 1 or not 0 <= self.exit_full_spread < 1:
            raise DataError('Invalid allocation cost/risk policy')


def plan_acquisitions(candidates, account, policy, now):
    """Gate, rank and reserve a simultaneous research basket using known inputs.

    Candidates contain an immutable setup and assessment plus named evidence
    groups. Required groups vary by declared experiment; all indicators are not
    mandatory simultaneously. Missing, stale and failed evidence stay distinct.
    Ranking uses conditional reward/risk, not an invented confidence score.
    """
    if type(now) is not int:
        raise DataError('Explicit decision timestamp required')
    if account.get('mode') not in ('paper', 'counterfactual'):
        raise DataError('This planner has no live authority')
    equity, cash, total = [number(account[k]) for k in ('equity', 'settled_cash', 'total_open_risk')]
    if equity <= 0 or min(cash, total) < 0:
        raise DataError('Invalid account snapshot')
    if type(account.get('observed_at')) is not int or not 0 <= now-account['observed_at'] <= policy.maximum_evidence_age_seconds:
        raise DataError('Fresh point-in-time account snapshot required')
    trade_risk = {s: number(v) for s, v in account.get('trade_risk_by_symbol', {}).items()}
    if any(v < 0 for v in trade_risk.values()) or sum(trade_risk.values(), D(0)) > total:
        raise DataError('Inconsistent cumulative trade risk')
    if type(account.get('new_entries_allowed')) is not bool:
        raise DataError('Explicit paper pause state required')
    occupied = set(account.get('open_symbols', [])) | {s for s, v in trade_risk.items() if v > 0}
    candidates = list(candidates)
    reviews, eligible, seen, by_id = [], [], set(), {}
    for candidate in candidates:
        event, assessment = candidate['event'], candidate['assessment']
        identity, symbol = event['event_id'], event['symbol']
        if identity in seen:
            raise DataError('Repeated opportunity must not consume capital twice')
        seen.add(identity)
        by_id[identity] = candidate
        row = dict(event_id=identity, symbol=symbol, setup=event['setup'],
                   event_sha256=fingerprint(event), assessment_sha256=fingerprint(assessment),
                   reserved_at=now, allocation_policy_sha256=fingerprint(asdict(policy)),
                   minimum_net_reward_to_risk=str(policy.minimum_net_reward_to_risk),
                   cost_assumptions=dict(fee_per_side=str(policy.fee_per_side),
                       exit_slippage=str(policy.exit_slippage), exit_full_spread=str(policy.exit_full_spread)),
                   state='wait_for_evidence', stage='evidence', reasons=[], rank=None,
                   quantity=0, acquisition_price=None, maximum_entry_price=None,
                   planned_risk='0', entry_cash='0', recommendation_qualified=False,
                   live_eligible=False, management=dict(protective_stop=event['proposed_stop'],
                       target_hypothesis=assessment.get('target_price'),
                       holding_horizon_minutes=assessment.get('target_provenance', {}).get('horizon_minutes'),
                       additions='separate_review_required', partial_exits='not_simulated',
                       overnight='separate_policy_required'))
        reviews.append(row)
        if assessment.get('event_id') != identity or assessment.get('event_sha256') != fingerprint(event):
            raise DataError('Assessment cannot detach from exact setup terms')
        if type(event.get('available_at')) is not int or event['available_at'] > now:
            row['reasons'].append('setup_not_yet_observable')
        if type(assessment.get('assessed_at')) is not int or not 0 <= now-assessment['assessed_at'] <= policy.maximum_evidence_age_seconds or type(assessment.get('valid_until')) is not int or now > assessment['valid_until']:
            row['reasons'].append('stale_or_future_opportunity_assessment')
        groups = candidate.get('evidence_groups', {})
        row['evidence_groups'] = groups
        for group in policy.required_evidence_groups:
            evidence = groups.get(group)
            if not evidence or evidence.get('status') == 'unknown':
                row['reasons'].append('missing_'+group)
                continue
            stamp = evidence.get('available_at')
            sources = evidence.get('source_sha256', [])
            if (type(stamp) is not int or not 0 <= now-stamp <= policy.maximum_evidence_age_seconds
                    or not sources or any(not isinstance(s, str) or len(s) != 64 or any(c not in '0123456789abcdef' for c in s) for s in sources)):
                row['reasons'].append('unqualified_'+group)
            elif evidence.get('status') != 'pass':
                row['reasons'].append('failed_'+group)
        if assessment.get('state') != 'conditional_research_case':
            row['reasons'].extend(assessment.get('reasons') or ['opportunity_not_qualified'])
        if row['reasons']:
            continue
        entry, stop, target = [number(assessment[k]) for k in ('entry_price', 'stop_price', 'target_price')]
        if stop != number(event['proposed_stop']) or not 0 < stop < entry < target:
            raise DataError('Invalid or changed acquisition geometry')
        provenance = assessment.get('target_provenance')
        if not provenance or assessment.get('target_sha256') != fingerprint(provenance) or number(provenance['price']) != target or provenance['available_at'] > now:
            raise DataError('Changed or future target evidence')
        friction = (1-policy.exit_full_spread/2)*(1-policy.exit_slippage)
        reward, risk = target*friction-entry, entry-stop*friction
        row.update(acquisition_price=str(entry), conditional_reward_to_risk=str(reward/risk),
                   conditional_roi_before_fixed_fees=str(reward/entry),
                   stage='remaining_opportunity', ranking_basis='conditional_reward_to_risk_before_fixed_fees_not_expected_return')
        if reward <= 0 or reward/risk < policy.minimum_net_reward_to_risk:
            row.update(state='track_only', reasons=['insufficient_remaining_opportunity'])
            continue
        preview=size_research_case(entry, stop, equity, cash, D(0), total,
            policy.fee_per_side, policy.exit_slippage, exit_spread_fraction=policy.exit_full_spread)
        cap=candidate.get('maximum_quantity_from_liquidity')
        qty=min(preview['quantity'], cap) if type(cap) is int and cap >= 0 else 0
        if qty:
            preview_reward=qty*reward-2*policy.fee_per_side
            preview_risk=qty*risk+2*policy.fee_per_side
            metrics=dict(net_reward_to_risk=preview_reward/preview_risk,
                         conditional_roi=preview_reward/(qty*entry+policy.fee_per_side))
        else:
            # An unfundable candidate stays visible but cannot outrank fundable
            # alternatives on an imagined affordable commission rate.
            metrics=dict(net_reward_to_risk=D('-Infinity'),conditional_roi=D('-Infinity'))
        row['comparison_at_initial_budget']={k:str(v) if v.is_finite() else None for k,v in metrics.items()}
        row['expected_net_return']=None
        row['ranking_basis']='lexicographic_conditional_financial_metrics_not_expected_return'
        eligible.append((tuple(-metrics[k] for k in policy.ranking_order), identity, row, entry, stop, target, friction))
    # Deterministic tie-break only, never ticker popularity or subsequently observed return.
    eligible.sort(key=lambda item: (item[0], item[1]))
    for rank, (_, _, row, entry, stop, target, friction) in enumerate(eligible, 1):
        row.update(rank=rank, stage='shared_capital_and_risk')
        if not account['new_entries_allowed']:
            row.update(state='track_only', reasons=['paper_new_exposure_paused'])
            continue
        if row['symbol'] in occupied:
            row.update(state='track_only', reasons=['existing_or_reserved_position_requires_addition_review'])
            continue
        sized = size_research_case(entry, stop, equity, cash, D(0), total,
                                  policy.fee_per_side, policy.exit_slippage,
                                  exit_spread_fraction=policy.exit_full_spread)
        qty = sized['quantity']
        candidate = by_id[row['event_id']]
        limit, stamp = candidate.get('maximum_quantity_from_liquidity'), candidate.get('liquidity_available_at')
        if (type(limit) is not int or limit < 0 or type(stamp) is not int
                or not 0 <= now-stamp <= policy.maximum_evidence_age_seconds):
            row.update(state='wait_for_evidence', reasons=['point_in_time_liquidity_quantity_required'])
            continue
        qty = min(qty, limit)
        if qty <= 0:
            row.update(state='track_only', reasons=['cash_risk_or_liquidity_capacity_unavailable'])
            continue
        fees = 2*policy.fee_per_side
        risk, reward = qty*(entry-stop*friction)+fees, qty*(target*friction-entry)-fees
        ceiling = (target*friction+policy.minimum_net_reward_to_risk*stop*friction-fees*(1+policy.minimum_net_reward_to_risk)/qty)/(1+policy.minimum_net_reward_to_risk)
        row['maximum_entry_price'] = str(ceiling)
        if reward <= 0 or reward/risk < policy.minimum_net_reward_to_risk:
            row.update(state='track_only', reasons=['fees_remove_remaining_opportunity_at_allowed_scale'])
            continue
        spent = qty*entry+policy.fee_per_side
        row.update(state='conditional_research_reservation', quantity=qty, entry_cash=str(spent),
                   planned_risk=str(risk), conditional_net_reward=str(reward),
                   conditional_roi=str(reward/spent),
                   break_even_win_probability_if_only_target_or_stop=str(risk/(reward+risk)),
                   conditional_reward_to_risk=str(reward/risk),
                   reasons=['evidence_and_conditional_geometry_pass', 'shared_cash_and_risk_reserved',
                            'target_and_ranking_not_statistically_validated'])
        cash -= spent
        total += risk
        occupied.add(row['symbol'])
    comparisons=[]
    for _, identity, row, *_ in eligible:
        metrics=row['comparison_at_initial_budget']
        dominates=[]
        if all(v is not None for v in metrics.values()):
            for _, other_id, other, *_ in eligible:
                other_metrics=other['comparison_at_initial_budget']
                if identity!=other_id and all(v is not None for v in other_metrics.values()):
                    if all(D(metrics[k])>=D(other_metrics[k]) for k in metrics) and any(D(metrics[k])>D(other_metrics[k]) for k in metrics):
                        dominates.append(other_id)
        comparisons.append(dict(event_id=identity,symbol=row['symbol'],rank=row['rank'],
            metrics_at_common_initial_budget=metrics,conditionally_dominates=dominates,
            evidence_groups=row['evidence_groups'],expected_net_return=None))
    return dict(status='research_allocation_snapshot_only', assessed_at=now, reviews=reviews,
                comparisons=comparisons,ranking_order=list(policy.ranking_order),
                reserved_cash=str(number(account['settled_cash'])-cash), remaining_settled_cash=str(cash),
                reserved_planned_risk=str(total-number(account['total_open_risk'])),
                total_planned_risk=str(total), policy_sha256=fingerprint(asdict(policy)),
                input_sha256=fingerprint(dict(candidates=candidates, account=account)),
                recommendation_qualified=False, operational_assistant_ready=False,
                profitable_strategy_demonstrated=False, orders_submitted=0,
                limitations=['unvalidated_conditional_ranking', 'liquidity_cap_is_input_not_fill_proof',
                             'no_joint_settlement_or_correlation_model', 'snapshot_reservations_not_orders'])


def plan_research_series(setups, assessments, series, source_sha256, equity, settled_cash,
                         opportunity_policy, replay_policy):
    """Connect the existing research path without looking at replay outcomes.

    Reserve chronologically; never recycle modeled proceeds or assume positions
    exited. This conservative research plan is separate from independent replays.
    Within a timestamp, compare competing opportunities using the same budget.
    """
    policy = AllocationPolicy('conditional_acquisition_v1',
        ('discovery', 'setup', 'opportunity', 'liquidity'),
        opportunity_policy.maximum_signal_age_seconds,
        opportunity_policy.minimum_net_reward_to_risk, replay_policy.fee_per_side,
        replay_policy.exit_slippage, replay_policy.assumed_full_spread)
    matched = {a['event_id']: a for a in assessments}
    cash, total, snapshots, occupied = number(settled_cash), D(0), [], set()
    for now in sorted({e['available_at'] for e in setups}):
        candidates = []
        for event in (e for e in setups if e['available_at'] == now):
            assessment = matched[event['event_id']]
            bars = [b for b in series[event['symbol']] if b.timestamp+replay_policy.bar_minutes*60 <= now]
            latest = bars[-1] if bars else None
            evidence = lambda status: dict(status=status, available_at=now, source_sha256=[source_sha256])
            candidates.append(dict(event=event, assessment=assessment,
                evidence_groups=dict(discovery=evidence('pass'), setup=evidence('pass'),
                    opportunity=evidence('pass' if assessment['state']=='conditional_research_case' else 'unknown'),
                    liquidity=evidence('pass' if latest else 'unknown')),
                maximum_quantity_from_liquidity=int(latest.volume*replay_policy.prior_volume_participation) if latest else None,
                liquidity_available_at=latest.timestamp+replay_policy.bar_minutes*60 if latest else None))
        account=dict(mode='counterfactual', equity=str(equity), settled_cash=str(cash),
            total_open_risk=str(total), observed_at=now, trade_risk_by_symbol={},
            open_symbols=sorted(occupied), new_entries_allowed=True)
        snapshot=plan_acquisitions(candidates, account, policy, now)
        snapshots.append(snapshot)
        cash, total=number(snapshot['remaining_settled_cash']), number(snapshot['total_planned_risk'])
        occupied.update(r['symbol'] for r in snapshot['reviews'] if r['quantity'] > 0)
    return dict(status='conservative_research_reservations_no_releases', snapshots=snapshots,
        remaining_settled_cash=str(cash), total_reserved_risk=str(total),
        scenario_equity=str(equity), outcomes_used_for_selection=False,
        portfolio_return=None, operational_assistant_ready=False,
        scope='quiet_to_active_price_volume_experiment_other_families_not_yet_connected',
        limitations=['no_proceeds_reuse_or_settlement', 'no_mark_to_market_or_paper_daily_pause_simulation',
                     'independent_replay_outcomes_are_not_basket_outcomes',
                     'conditional_geometry_is_not_a_profit_forecast'])


def replay_acquisition_plan(plan, setups, assessments, series, calendar, policy, equity):
    """Evaluate reserved choices without reallocating from later fill/outcome data.

    Nonselected opportunities remain visible. Nonfills, censored exits and unused
    reservations never release funds here. This is not a settlement/return model.
    """
    events = {e['event_id']: e for e in setups}
    assessed = {a['event_id']: a for a in assessments}
    outcomes = []
    for snapshot in plan['snapshots']:
        for reservation in snapshot['reviews']:
            identity = reservation['event_id']
            if reservation['state'] != 'conditional_research_reservation':
                outcomes.append(dict(event_id=identity, status='not_selected_by_acquisition_plan',
                    allocation_state=reservation['state'], reasons=reservation['reasons'],
                    quantity=0, net_pnl=None, reservation_sha256=fingerprint(reservation)))
                continue
            event = events[identity]
            outcome = replay_case(event, assessed[identity], series[event['symbol']], calendar,
                policy, equity, D(reservation['entry_cash']), reservation=reservation)
            outcomes.append(outcome)
    return dict(status='allocation_bound_conditional_cases', outcomes=outcomes,
        plan_sha256=fingerprint(plan), replay_policy_sha256=fingerprint(asdict(policy)),
        input_sha256=fingerprint(dict(setups=setups, assessments=assessments,
            series={s:[asdict(b) for b in bars] for s,bars in series.items()}, calendar=calendar)),
        outcomes_used_for_selection=False, proceeds_reused=False, portfolio_return=None,
        orders_submitted=0, operational_assistant_ready=False,
        limitations=['reservations_remain_locked_even_for_nonfills',
            'no_settlement_mark_to_market_or_joint_equity_accounting',
            'bar_model_not_observed_execution', 'targets_and_ranking_unvalidated'])
