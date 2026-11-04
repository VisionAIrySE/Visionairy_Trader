"""Explicit profit-taking/protection experiments; not approved trading rules."""
from dataclasses import dataclass, asdict
from decimal import Decimal as D, ROUND_FLOOR

from acquisition_funnel import number
from managed_replay import replay_case
from replay import DataError
from setup_detection import fingerprint


@dataclass(frozen=True)
class ManagementPolicy:
    version: str
    partial_at_r: D | None = None
    partial_fraction: D = D('.5')
    trail_distance_r: D | None = None

    def __post_init__(self):
        if not self.version:raise DataError('Versioned management experiment required')
        for name in ('partial_at_r','partial_fraction','trail_distance_r'):
            value=getattr(self,name)
            if value is not None:object.__setattr__(self,name,number(value))
        if not 0<self.partial_fraction<1 or any(x is not None and x<=0 for x in (self.partial_at_r,self.trail_distance_r)):
            raise DataError('Positive explicit management thresholds required')


def replay_management(event, assessment, bars, calendar, replay_policy, equity, reservation, management):
    base=replay_case(event,assessment,bars,calendar,replay_policy,equity,
                     D(reservation['entry_cash']),reservation=reservation)
    base.update(management_policy_sha256=fingerprint(asdict(management)),management_version=management.version,
                fills=[],stop_changes=[])
    if not base.get('quantity'):return base
    quantity=remaining=base['quantity'];entry=D(base['entry_price']);stop=D(base['stop_price'])
    initial_distance=entry-stop;target=D(base['target_price']);partial_done=False
    friction=(1-replay_policy.assumed_full_spread/2)*(1-replay_policy.exit_slippage)
    step=replay_policy.bar_minutes*60;by_stamp={b.timestamp:i for i,b in enumerate(bars)}
    expected=[t for w in calendar for t in range(w['open'],w['close'],step) if t>=base['entry_at']]
    first_session=next(w for w in calendar if w['open']<=base['entry_at']<w['close'])
    base.update(status='censored_missing_horizon',net_pnl=None)
    # Drop baseline exit fields; a management comparison has its own outcomes.
    for key in ('exit_at','exit_price','exit_reason','observed_trading_minutes','final_decision_id'):
        base.pop(key,None)
    held=0
    def sell(qty,reference,stamp,index,reason):
        nonlocal remaining
        prior=bars[index-1] if index else None
        if prior is None or int(prior.volume*replay_policy.prior_volume_participation)<qty:
            base.update(status='censored_exit_activity',attempted_exit_at=stamp,exit_reason=reason)
            return False
        price=reference*friction
        base['fills'].append(dict(at=stamp,quantity=qty,price=str(price),fee=str(replay_policy.fee_per_side),reason=reason))
        remaining-=qty
        if not remaining:
            proceeds=sum((D(f['price'])*f['quantity']-D(f['fee']) for f in base['fills']),D(0))
            base.update(status='modeled',exit_at=stamp,exit_price=str(price),exit_reason=reason,
                net_pnl=str(proceeds-quantity*entry-replay_policy.fee_per_side),
                observed_trading_minutes=held*replay_policy.bar_minutes)
        return True
    for stamp in expected:
        if stamp not in by_stamp:base['status']='censored_holding_gap';break
        i=by_stamp[stamp];b=bars[i]
        session=next(w for w in calendar if w['open']<=stamp<w['close'])
        if not replay_policy.allow_overnight and session!=first_session:
            base['status']='censored_missing_session_close';break
        if held*replay_policy.bar_minutes>=replay_policy.holding_trading_minutes or stamp>=base['entry_at']+replay_policy.maximum_calendar_days*86400:
            sell(remaining,b.open,stamp,i,'time_horizon');break
        if b.open<=stop or b.low<=stop:
            sell(remaining,b.open if b.open<=stop else stop,stamp if b.open<=stop else stamp+step,i,
                 'gap_through_stop' if b.open<=stop else 'protective_stop');break
        if b.open>=target or b.high>=target:
            sell(remaining,b.open if b.open>=target else target,stamp if b.open>=target else stamp+step,i,'conditional_target');break
        if management.partial_at_r is not None and not partial_done:
            threshold=entry+management.partial_at_r*initial_distance
            if b.high>=threshold:
                qty=int((quantity*management.partial_fraction).to_integral_value(rounding=ROUND_FLOOR))
                if qty>0:
                    # Stop already wins ambiguous bars; never assume a partial happened first.
                    if not sell(qty,max(b.open,threshold),stamp if b.open>=threshold else stamp+step,i,'partial_profit'):break
                partial_done=True
        if management.trail_distance_r is not None:
            new_stop=max(stop,b.close-management.trail_distance_r*initial_distance)
            if new_stop>stop:
                base['stop_changes'].append(dict(available_at=stamp+step,old_stop=str(stop),new_stop=str(new_stop),
                    basis='completed_close_minus_declared_initial_risk_distance',user_approval='counterfactual_policy_not_user'))
                stop=new_stop
        held+=1
        if not replay_policy.allow_overnight and stamp+step==session['close']:
            sell(remaining,b.close,stamp+step,i,'explicit_no_overnight_experiment');break
    base['remaining_quantity']=remaining
    return base
