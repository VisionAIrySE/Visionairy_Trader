"""A07 setup evidence from completed bars; never a forecast or order authority."""
from dataclasses import dataclass, asdict
from decimal import Decimal as D
import hashlib
import json

from replay import DataError


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str,
                                     separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True)
class MarketBar:
    timestamp: int
    session: str
    minute: int
    open: D
    high: D
    low: D
    close: D
    volume: D
    session_minutes: int = 390


def validate_bars(bars, step_minutes):
    from discovery_selection import Observation, SelectionPolicy, validate_observations
    # Reuse clock/value validation without imposing strategy eligibility thresholds.
    clock = SelectionPolicy('clock_validation',step_minutes,1,2,D(1),D(1),D(2),D(1),0)
    observations = [Observation(b.timestamp,b.session,b.minute,b.close,b.volume,b.session_minutes) for b in bars]
    validate_observations(observations,clock)
    opens = {}
    lengths = {}
    for bar in bars:
        values = (bar.open,bar.high,bar.low,bar.close)
        if any(not isinstance(v,D) or not v.is_finite() or v<=0 for v in values):
            raise DataError('Finite positive OHLC required')
        if bar.high < max(values) or bar.low > min(values):
            raise DataError('Invalid OHLC ordering')
        start = bar.timestamp-bar.minute*60
        if start != opens.setdefault(bar.session,start) or bar.session_minutes != lengths.setdefault(bar.session,bar.session_minutes):
            raise DataError('Inconsistent exchange session calendar')


@dataclass(frozen=True)
class SetupPolicy:
    version: str
    structure_bars: int
    atr_bars: int
    stop_atr_multiple: D
    maximum_extension_atr: D
    minimum_pullback_fraction: D
    maximum_pullback_fraction: D
    minimum_resumption_volume_ratio: D
    activation_lifetime_minutes: int

    def __post_init__(self):
        if not self.version or any(type(v) is not int or v<1 for v in
            (self.structure_bars,self.atr_bars,self.activation_lifetime_minutes)):
            raise DataError('Explicit versioned setup window required')
        for name in ('stop_atr_multiple','maximum_extension_atr','minimum_pullback_fraction',
                     'maximum_pullback_fraction','minimum_resumption_volume_ratio'):
            value=D(str(getattr(self,name)))
            if not value.is_finite() or value<=0:raise DataError('Invalid setup parameter')
            object.__setattr__(self,name,value)
        if not 0<self.minimum_pullback_fraction<self.maximum_pullback_fraction<1:
            raise DataError('Controlled pullback must preserve part of the impulse')


def trailing_atr(bars, index, count):
    if index<count:return None
    window=bars[index-count:index+1]
    if len({b.session for b in window})!=1:return None
    ranges=[max(b.high-b.low,abs(b.high-a.close),abs(b.low-a.close))
            for a,b in zip(window,window[1:])]
    return sum(ranges,D(0))/len(ranges)


def classify_setups(symbol,bars,decisions,selection_policy,setup_policy,*,
                    activation_state="quiet_to_active_candidate",cohort="quiet_to_active"):
    """Emit the initial breakout and subsequent controlled-pullback resumption separately.

    A candidate cannot be created from bars that became observable after its event.
    Earlier structure and current volatility define a proposed stop, not affordability.
    """
    step=selection_policy.bar_minutes*60
    validate_bars(bars,selection_policy.bar_minutes)
    by_time={b.timestamp+step:i for i,b in enumerate(bars)}
    decisions_by_time={r['available_at']:r for r in decisions}
    events=[]
    activation=None
    policy_hash=fingerprint(asdict(setup_policy))
    for available,index in sorted(by_time.items()):
        row=bars[index]
        decision=decisions_by_time.get(available)
        if decision and decision['state']==activation_state:
            activation=dict(id=decision['event_id'],at=available,session=row.session,
                            origin=D(decision['first_price']),peak=row.high,peak_at=index,
                            floor=None,pullback_volume=None,resumption_emitted=False)
        if activation is None:continue
        if available-activation['at']>setup_policy.activation_lifetime_minutes*60 or row.session!=activation['session']:
            activation=None
            continue
        if index==0 or bars[index-1].timestamp+step!=row.timestamp:
            activation=None
            continue
        atr=trailing_atr(bars,index,setup_policy.atr_bars)
        recent=bars[max(0,index-setup_policy.structure_bars):index]
        if atr is None or atr<=0 or len(recent)<setup_policy.structure_bars:continue
        if any(b.timestamp-a.timestamp!=step or b.session!=a.session for a,b in zip(recent+[row],(recent+[row])[1:])):
            activation=None
            continue
        def event(kind,structure_stop,detail):
            distance=max(row.close-structure_stop,atr*setup_policy.stop_atr_multiple)
            stop=row.close-distance
            if stop<=0 or stop>=row.close:return None
            identity=fingerprint([symbol,kind,available,activation['id'],policy_hash])
            return dict(event_id=identity,symbol=symbol,setup=kind,available_at=available,
                        activation_id=activation['id'],activation_at=activation['at'],
                        cohort=cohort,basis='price_volume',
                        catalyst_status='unknown',entry_reference=str(row.close),
                        proposed_stop=str(stop),stop_percent=str(distance/row.close*100),
                        atr=str(atr),structure_stop=str(structure_stop),details=detail,
                        selection_policy_sha256=selection_policy.fingerprint(),setup_policy_sha256=policy_hash,
                        state='research_setup_only',recommendation_qualified=False)
        if available==activation['at']:
            resistance=max(b.high for b in recent)
            extension=(row.close-resistance)/atr
            if row.close>resistance and extension<=setup_policy.maximum_extension_atr:
                value=event('initial_breakout',min(b.low for b in recent),
                            dict(prior_resistance=str(resistance),extension_atr=str(extension)))
                if value:events.append(value)
            continue
        previous=bars[index-1]
        # Resumption must follow a completed earlier pullback; current lows cannot
        # retroactively create a pullback and higher-price confirmation in one bar.
        if activation['floor'] is not None:
            impulse=activation['peak']-activation['origin']
            depth=(activation['peak']-activation['floor'])/impulse if impulse>0 else D(1)
            controlled=setup_policy.minimum_pullback_fraction<=depth<=setup_policy.maximum_pullback_fraction
            base_volume=activation['pullback_volume']
            volume_ok=base_volume is not None and base_volume>0 and row.volume>=base_volume*setup_policy.minimum_resumption_volume_ratio
            if (controlled and row.close>previous.high and row.close>row.open and volume_ok
                    and not activation['resumption_emitted']):
                value=event('pullback_continuation',activation['floor'],
                            dict(pullback_fraction=str(depth),resumption_reference=str(previous.high),
                                 resumption_volume_ratio=str(row.volume/base_volume)))
                if value:
                    events.append(value)
                    activation['resumption_emitted']=True
        if row.high>activation['peak']:
            activation.update(peak=row.high,peak_at=index)
        elif row.close<previous.close and index>activation['peak_at']:
            activation['floor']=min(row.low,activation['floor']) if activation['floor'] is not None else row.low
            activation['pullback_volume']=row.volume
    return events


@dataclass(frozen=True)
class OpportunityPolicy:
    version: str
    maximum_signal_age_seconds: int
    maximum_quote_age_seconds: int
    maximum_target_horizon_minutes: int
    maximum_spread_fraction: D
    minimum_net_reward_to_risk: D
    entry_slippage_fraction: D
    exit_slippage_fraction: D
    roundtrip_fee_per_share: D

    def __post_init__(self):
        if not self.version or any(type(v) is not int or v<0 for v in
            (self.maximum_signal_age_seconds,self.maximum_quote_age_seconds)) or type(self.maximum_target_horizon_minutes) is not int or self.maximum_target_horizon_minutes<60:
            raise DataError('Explicit freshness policy required')
        for name in ('maximum_spread_fraction','minimum_net_reward_to_risk',
                     'entry_slippage_fraction','exit_slippage_fraction','roundtrip_fee_per_share'):
            value=D(str(getattr(self,name)))
            if not value.is_finite() or value<0:raise DataError('Invalid cost/edge policy')
            object.__setattr__(self,name,value)
        if self.minimum_net_reward_to_risk<=0 or self.maximum_spread_fraction>=1:
            raise DataError('Invalid opportunity requirement')


def assess_remaining_opportunity(event,quote,target,now,policy):
    """Evaluate a timestamped target hypothesis; never obtain it from future highs.

    A favorable conditional ratio is not an estimated win probability or proven
    positive expectancy. Research cases remain ineligible for actual orders.
    """
    result=dict(event_id=event['event_id'],state='insufficient_evidence',reasons=[],
                recommendation_qualified=False,live_eligible=False,
                opportunity_policy_sha256=fingerprint(asdict(policy)),assessed_at=now,
                event_sha256=fingerprint(event),
                valid_until=event['available_at']+policy.maximum_signal_age_seconds)
    if now<event['available_at'] or now-event['available_at']>policy.maximum_signal_age_seconds:
        result['reasons']=['signal_stale_or_not_yet_observable'];return result
    if not quote or not target:
        result['reasons']=['fresh_quotes_and_point_in_time_target_required'];return result
    if type(target.get('horizon_minutes')) is not int or not 0<target['horizon_minutes']<=policy.maximum_target_horizon_minutes:
        result['reasons']=['target_not_supported_in_intended_holding_window'];return result
    try:
        bid,ask,stop,price=map(lambda x:D(str(x)),(quote['bid'],quote['ask'],event['proposed_stop'],target['price']))
        if not all(x.is_finite() and x>0 for x in (bid,ask,stop,price)):raise ValueError()
        if type(quote['observed_at']) is not int or type(target['available_at']) is not int:raise ValueError()
    except (KeyError,ValueError,TypeError,ArithmeticError):
        result['reasons']=['malformed_quote_or_target'];return result
    if (bid>ask or quote.get('symbol')!=event['symbol'] or quote['observed_at']>now or
            now-quote['observed_at']>policy.maximum_quote_age_seconds or
            target.get('symbol')!=event['symbol'] or target['available_at']>now or
            not target.get('source_sha256') or not target.get('method_version')):
        result['reasons']=['invalid_stale_or_future_quote_or_target'];return result
    spread=(ask-bid)/((ask+bid)/2)
    entry=ask*(1+policy.entry_slippage_fraction)
    target_exit=price*(1-policy.exit_slippage_fraction)
    stop_exit=stop*(1-policy.exit_slippage_fraction)
    reward=target_exit-entry-policy.roundtrip_fee_per_share
    risk=entry-stop_exit+policy.roundtrip_fee_per_share
    result.update(entry_price=str(entry),target_price=str(price),stop_price=str(stop),
                  net_reward_per_share=str(reward),planned_risk_per_share=str(risk),
                  spread_fraction=str(spread),target_provenance=json.loads(json.dumps(target,default=str)),
                  target_sha256=fingerprint(target),
                  target_evidence=target.get('evidence','unvalidated_hypothesis'))
    if spread>policy.maximum_spread_fraction:
        result.update(state='track_only',reasons=['spread_exceeds_experimental_limit']);return result
    if stop>=entry or reward<=0 or risk<=0 or reward/risk<policy.minimum_net_reward_to_risk:
        result.update(state='track_only',reasons=['insufficient_remaining_opportunity_after_costs']);return result
    result.update(state='conditional_research_case',net_reward_to_risk=str(reward/risk),
                  reasons=['conditional_target_clears_experimental_cost_risk_test',
                           'target_not_a_guaranteed_or_statistically_validated_return'])
    return result
