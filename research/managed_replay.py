"""Hours-to-days conditional historical cases, never brokerage or account returns.

Explicit experimental policies; conservative stop-first bar ambiguity; gaps and
missing evidence are retained. A source bar does not prove an executable fill.
"""
from dataclasses import dataclass, asdict
from decimal import Decimal as D, ROUND_FLOOR

from replay import DataError
from setup_detection import validate_bars, fingerprint


def paper_entry_pause(start_equity,current_equity,net_external_flow,valuation_fresh,
                      already_paused,mode):
    """O11: 3% daily new-entry/addition pause for paper testing only.

    Caller persists the session baseline and latch; a recovering valuation does
    not reopen the session. This never liquidates a position or silences scans.
    """
    if mode not in ('paper','counterfactual'):
        raise DataError('A live daily-loss threshold has not been agreed')
    start,current,flow=map(lambda x:D(str(x)),(start_equity,current_equity,net_external_flow))
    if not all(x.is_finite() for x in (start,current,flow)) or start<=0:
        raise DataError('Valid daily equity baseline required')
    drawdown=(start-(current-flow))/start
    paused=bool(already_paused or not valuation_fresh or drawdown>=D('.03'))
    return dict(new_entries_allowed=not paused,additions_allowed=not paused,
                paused_for_session=paused,drawdown_excluding_flows=str(drawdown),
                discovery_continues=True,recommendation_tracking_continues=True,
                existing_protection_retained=True,forced_liquidation=False,
                reason='latched_daily_pause' if already_paused else
                       'stale_valuation' if not valuation_fresh else
                       'paper_daily_drawdown' if paused else 'within_paper_rule')


@dataclass(frozen=True)
class ReplayPolicy:
    version: str
    bar_minutes: int
    entry_delay_seconds: int
    holding_trading_minutes: int
    maximum_calendar_days: int
    allow_overnight: bool
    assumed_full_spread: D
    entry_slippage: D
    exit_slippage: D
    fee_per_side: D
    prior_volume_participation: D
    minimum_net_reward_to_risk: D
    maximum_entry_change: D

    def __post_init__(self):
        if not self.version or self.bar_minutes not in (1,5,15):raise DataError('Explicit replay version/duration required')
        if any(type(v) is not int or v<0 for v in (self.entry_delay_seconds,self.holding_trading_minutes,self.maximum_calendar_days)):
            raise DataError('Invalid replay horizon')
        if self.holding_trading_minutes<60 or self.maximum_calendar_days<1 or self.holding_trading_minutes%self.bar_minutes:
            raise DataError('Aligned hours-to-days research horizon required')
        if type(self.allow_overnight) is not bool:raise DataError('Explicit overnight research choice required')
        for name in ('assumed_full_spread','entry_slippage','exit_slippage','fee_per_side',
                     'prior_volume_participation','minimum_net_reward_to_risk','maximum_entry_change'):
            v=D(str(getattr(self,name)))
            if not v.is_finite() or v<0:raise DataError('Invalid replay cost or liquidity assumption')
            object.__setattr__(self,name,v)
        if self.assumed_full_spread>=1 or max(self.entry_slippage,self.exit_slippage,self.maximum_entry_change)>=1:
            raise DataError('Unbounded price assumptions')
        if not 0<self.prior_volume_participation<=1 or self.minimum_net_reward_to_risk<=0:
            raise DataError('Positive bounded activity and opportunity assumptions required')


def size_research_case(entry,stop,equity,settled_cash,existing_trade_risk,total_open_risk,fee,exit_slippage,
                       per_trade_fraction=D('.01'),aggregate_fraction=D('.05'),exit_spread_fraction=D(0)):
    """A44/A45 risk arithmetic, including prior additions; no extra allowance per add.

    Values are explicit scenario snapshots, not a connected live balance. Other
    allocation/correlation/giveback controls remain unqualified.
    """
    values=list(map(lambda x:D(str(x)),(entry,stop,equity,settled_cash,existing_trade_risk,total_open_risk,
                                      fee,exit_slippage,per_trade_fraction,aggregate_fraction,exit_spread_fraction)))
    entry,stop,equity,cash,prior,total,fee,slip,trade_cap,open_cap,spread=values
    if any(not x.is_finite() for x in values) or equity<=0 or min(cash,prior,total,fee,slip)<0:
        raise DataError('Invalid risk snapshot')
    if stop<=0 or stop>=entry or not 0<trade_cap<=open_cap<=1 or slip>=1 or not 0<=spread<1 or prior>total:
        raise DataError('Invalid stop or cumulative risk accounting')
    if trade_cap>D('.01') or open_cap>D('.05'):
        raise DataError('Standing risk ceilings cannot increase through a research call')
    risk_per_share=entry-stop*(1-spread/2)*(1-slip)
    allowance=min(equity*trade_cap-prior,equity*open_cap-total)
    qty=max(0,min(int(((cash-fee)/entry).to_integral_value(rounding=ROUND_FLOOR)),
                  int(((allowance-2*fee)/risk_per_share).to_integral_value(rounding=ROUND_FLOOR))))
    return dict(quantity=qty,planned_risk=str(qty*risk_per_share+2*fee) if qty else '0',
                entry_cash=str(qty*entry+fee) if qty else '0',
                remaining_risk_allowance=str(max(D(0),allowance)),stop_unchanged=str(stop),
                capital_scope='independent_case_not_portfolio',
                state='sized' if qty else 'track_only_risk_or_cash_limit')


def replay_case(event,assessment,bars,calendar,policy,equity,settled_cash,
                existing_trade_risk=D(0),total_open_risk=D(0), *, reservation=None):
    """Replay a pre-existing setup/target through declared exchange sessions.

    Use modeled opening ask after delay; require the conditional opportunity to
    remain after revised entry costs. Hold across sessions only when explicitly
    enabled for this experiment. No user approval or actual fill is asserted.
    """
    validate_bars(bars,policy.bar_minutes)
    result=dict(event_id=event['event_id'],setup=event['setup'],cohort=event['cohort'],
                status='not_modeled',net_pnl=None,evidence_tier='conditional_bar_model',
                capital_scope='independent_case_not_portfolio',
                replay_policy_sha256=fingerprint(asdict(policy)),
                historical_user_approval='not_observed_counterfactual_only',
                live_eligible=False,assumptions=['bar_open_entry','assumed_spread_and_slippage',
                    'full_fill_only_when_previous_bar_activity_cap_allows',
                    'intrabar_stop_first_if_stop_and_target_both_touched'])
    if reservation is not None:
        if (reservation.get('state') != 'conditional_research_reservation'
                or reservation.get('event_id') != event['event_id']
                or reservation.get('symbol') != event['symbol']
                or reservation.get('event_sha256') != fingerprint(event)
                or reservation.get('assessment_sha256') != fingerprint(assessment)
                or type(reservation.get('reserved_at')) is not int
                or reservation['reserved_at'] < assessment['assessed_at']
                or reservation['reserved_at'] > assessment['valid_until']
                or type(reservation.get('quantity')) is not int or reservation['quantity'] <= 0):
            raise DataError('Exact qualified research reservation required')
        costs=reservation.get('cost_assumptions',{})
        if any(D(str(costs.get(k,'NaN'))) != v for k,v in (
                ('fee_per_side',policy.fee_per_side),('exit_slippage',policy.exit_slippage),
                ('exit_full_spread',policy.assumed_full_spread))):
            raise DataError('Replay costs differ from reserved acquisition terms')
        for field in ('entry_cash','planned_risk','maximum_entry_price','minimum_net_reward_to_risk'):
            value=D(str(reservation[field]))
            if not value.is_finite() or value <= 0:
                raise DataError('Positive finite reservation bounds required')
        result.update(capital_scope='allocation_bound_case_not_portfolio',
                      reservation_sha256=fingerprint(reservation),
                      allocation_policy_sha256=reservation['allocation_policy_sha256'])
    if assessment.get('event_id')!=event['event_id'] or assessment.get('state')!='conditional_research_case':
        result['status']='track_only_unqualified_opportunity';return result
    if assessment.get('event_sha256')!=fingerprint(event):
        raise DataError('Setup terms changed after opportunity assessment')
    if D(assessment['stop_price'])!=D(event['proposed_stop']):
        raise DataError('Assessment/stop identity mismatch')
    if assessment.get('assessed_at',event['available_at'])<event['available_at']:
        raise DataError('Assessment precedes setup')
    target=assessment['target_provenance']
    if assessment.get('target_sha256')!=fingerprint(target):
        raise DataError('Target hypothesis changed after opportunity assessment')
    if target['available_at']>assessment['assessed_at']:
        raise DataError('Future target cannot qualify entry')
    step=policy.bar_minutes*60
    sessions=[]
    last_close=None
    for window in calendar:
        a,b=window.get('open'),window.get('close')
        if type(a) is not int or type(b) is not int or a>=b or (b-a)%step or (last_close is not None and a<last_close):
            raise DataError('Qualified nonoverlapping exchange calendar required')
        sessions.append((a,b));last_close=b
    if not sessions:raise DataError('Exchange calendar required')
    arrival=max(event['available_at']+policy.entry_delay_seconds,assessment['assessed_at'])
    if reservation is not None:
        arrival=max(arrival,reservation['reserved_at'])
    by_stamp={b.timestamp:i for i,b in enumerate(bars)}
    expected=[t for a,b in sessions for t in range(a,b,step) if t>=arrival]
    if not expected:
        result['status']='censored_entry_calendar';return result
    entry_time=expected[0]
    if type(assessment.get('valid_until')) is not int or entry_time>assessment['valid_until']:
        result['status']='track_only_expired_opportunity';return result
    if entry_time not in by_stamp:
        result['status']='censored_missing_entry';return result
    if not any(a<=assessment['assessed_at']<b for a,b in sessions) or entry_time-assessment['assessed_at']>=86400:
        result['status']='track_only_expired_session_opportunity';return result
    entry_index=by_stamp[entry_time]
    if entry_index==0:
        result['status']='censored_prior_activity';return result
    prior=bars[entry_index-1]
    prior_session=next(((a,b) for a,b in sessions if a<=prior.timestamp<b),None)
    if prior_session is None:
        result['status']='censored_prior_activity';return result
    if prior.timestamp+step!=entry_time and prior.timestamp+step!=prior_session[1]:
        result['status']='censored_prior_activity';return result
    bar=bars[entry_index]
    entry=bar.open*(1+policy.assumed_full_spread/2)*(1+policy.entry_slippage)
    stop=D(event['proposed_stop']);target_price=D(target['price'])
    reference=D(assessment['entry_price'])
    result.update(entry_at=entry_time,entry_price=str(entry),stop_price=str(stop),target_price=str(target_price))
    if abs(entry/reference-1)>policy.maximum_entry_change or entry<=stop or entry>=target_price:
        result['status']='track_only_changed_entry_terms';return result
    if reservation is not None and entry>D(reservation['maximum_entry_price']):
        result['status']='not_filled_acquisition_price_ceiling';return result
    sizing=size_research_case(entry,stop,equity,settled_cash,existing_trade_risk,total_open_risk,
                              policy.fee_per_side,policy.exit_slippage,exit_spread_fraction=policy.assumed_full_spread)
    qty=sizing['quantity']
    if reservation is not None:
        risk_per_share=entry-stop*(1-policy.assumed_full_spread/2)*(1-policy.exit_slippage)
        cash_cap=int(((D(reservation['entry_cash'])-policy.fee_per_side)/entry).to_integral_value(rounding=ROUND_FLOOR))
        risk_cap=int(((D(reservation['planned_risk'])-2*policy.fee_per_side)/risk_per_share).to_integral_value(rounding=ROUND_FLOOR))
        qty=max(0,min(qty,reservation['quantity'],cash_cap,risk_cap))
    if qty>int(prior.volume*policy.prior_volume_participation):
        qty=int(prior.volume*policy.prior_volume_participation)
    if qty<=0:
        result['status']='track_only_risk_cash_or_activity';return result
    reward=qty*(target_price*(1-policy.assumed_full_spread/2)*(1-policy.exit_slippage)-entry)-2*policy.fee_per_side
    planned=qty*(entry-stop*(1-policy.assumed_full_spread/2)*(1-policy.exit_slippage))+2*policy.fee_per_side
    required_ratio=max(policy.minimum_net_reward_to_risk,D(reservation['minimum_net_reward_to_risk'])) if reservation is not None else policy.minimum_net_reward_to_risk
    if reward<=0 or planned<=0 or reward/planned<required_ratio:
        result['status']='track_only_insufficient_edge_after_entry_delay';return result
    result.update(quantity=qty,entry_cash=str(qty*entry+policy.fee_per_side),planned_risk=str(planned),
                  conditional_net_reward_to_risk=str(reward/planned))
    held=0
    entry_session=next((a,b) for a,b in sessions if a<=entry_time<b)
    maximum=entry_time+policy.maximum_calendar_days*86400
    adverse=D(0);favorable=D(0)
    def close_case(stamp,mid,reason,index):
        previous=bars[index-1] if index>0 else None
        if previous is None or int(previous.volume*policy.prior_volume_participation)<qty:
            result.update(status='censored_exit_activity',exit_reason=reason,
                          attempted_exit_at=stamp,attempted_exit_reference=str(mid))
            return result
        exit_price=mid*(1-policy.assumed_full_spread/2)*(1-policy.exit_slippage)
        result.update(status='modeled',exit_at=stamp,exit_price=str(exit_price),exit_reason=reason,
                      net_pnl=str(qty*(exit_price-entry)-2*policy.fee_per_side),
                      bar_extreme_adverse_bound=str(adverse),bar_extreme_favorable_bound=str(favorable),
                      observed_trading_minutes=held*policy.bar_minutes)
        return result
    for stamp in expected:
        if stamp not in by_stamp:
            result['status']='censored_holding_gap';return result
        index=by_stamp[stamp];b=bars[index]
        session=next((a,z) for a,z in sessions if a<=stamp<z)
        if not policy.allow_overnight and session!=entry_session:
            result['status']='censored_missing_session_close';return result
        if held*policy.bar_minutes>=policy.holding_trading_minutes or stamp>=maximum:
            return close_case(stamp,b.open,'time_horizon',index)
        adverse=min(adverse,b.low-entry);favorable=max(favorable,b.high-entry)
        if b.open<=stop:
            return close_case(stamp,b.open,'gap_through_stop',index)
        if b.low<=stop:
            return close_case(stamp+step,stop,'protective_stop',index)
        if b.open>=target_price:
            return close_case(stamp,b.open,'gap_above_target',index)
        if b.high>=target_price:
            return close_case(stamp+step,target_price,'conditional_target',index)
        held+=1
        if not policy.allow_overnight and stamp+step==session[1]:
            return close_case(stamp+step,b.close,'explicit_no_overnight_experiment',index)
    result['status']='censored_missing_horizon'
    return result
