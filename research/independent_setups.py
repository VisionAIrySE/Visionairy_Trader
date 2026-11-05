"""Independent breakout/pullback research; no quiet-stock or account-price gate."""
from dataclasses import dataclass,asdict
from decimal import Decimal as D
from replay import DataError
from setup_detection import validate_bars,classify_setups,fingerprint,SetupPolicy,trailing_atr

@dataclass(frozen=True)
class IndependentPolicy:
    version:str
    bar_minutes:int
    minimum_breakout_volume_ratio:D
    setup:SetupPolicy
    def __post_init__(self):
        if not self.version or type(self.bar_minutes) is not int or self.bar_minutes not in (1,5,15):
            raise DataError('Explicit supported completed-bar policy required')
        ratio=D(str(self.minimum_breakout_volume_ratio))
        if not ratio.is_finite() or ratio<=1:raise DataError('Explicit unusual-volume threshold required')
        if not isinstance(self.setup,SetupPolicy):raise DataError('Explicit structural setup policy required')
        object.__setattr__(self,'minimum_breakout_volume_ratio',ratio)
    def fingerprint(self):return fingerprint(asdict(self))


def scan_independent(symbol,bars,policy,*,now):
    if type(now) is not int:raise DataError('Explicit observation cutoff required')
    # Ignore uncompleted/future bars before validation or baseline calculation.
    step=policy.bar_minutes*60
    bars=[b for b in bars if b.timestamp+step<=now]
    validate_bars(bars,policy.bar_minutes)
    decisions=[];events=[];active=False;activation_at=None;activation_session=None
    for i,row in enumerate(bars):
        available=row.timestamp+step
        record=dict(symbol=symbol,available_at=available,state='not_activated',reasons=[],
            cohort='independent_momentum',policy_sha256=policy.fingerprint(),experimental=True)
        if active and (row.session!=activation_session or available-activation_at>policy.setup.activation_lifetime_minutes*60):
            active=False
        count=max(policy.setup.structure_bars,policy.setup.atr_bars)
        recent=bars[max(0,i-count):i]
        contiguous=len(recent)==count and all(a.session==b.session and b.timestamp-a.timestamp==step
            for a,b in zip(recent+[row],(recent+[row])[1:]))
        if not contiguous:
            active=False;record.update(state='insufficient_evidence',reasons=['contiguous_completed_structure_required'])
        elif active:
            record['reasons']=['tracking_existing_activation']
        else:
            structure=recent[-policy.setup.structure_bars:]
            resistance=max(b.high for b in structure)
            normal=sum((b.volume for b in structure),D(0))/len(structure)
            record.update(prior_resistance=str(resistance),prior_mean_bar_volume=str(normal))
            if normal<=0:record.update(state='insufficient_evidence',reasons=['positive_prior_volume_required'])
            elif row.close>resistance and row.volume>=normal*policy.minimum_breakout_volume_ratio:
                root=dict(symbol=symbol,available_at=available,first_price=str(structure[0].close),
                    state='independent_breakout_activation',policy_sha256=policy.fingerprint())
                root['event_id']=fingerprint(root)
                atr=trailing_atr(bars,i,policy.setup.atr_bars)
                distance=max(row.close-min(b.low for b in structure),
                    atr*policy.setup.stop_atr_multiple) if atr is not None else row.close
                if (atr is not None and atr>0 and row.close-distance>0
                        and (row.close-resistance)/atr<=policy.setup.maximum_extension_atr):
                    active=True;activation_at=available;activation_session=row.session
                    record.update(root,state='independent_breakout_activation')
                else:record['reasons']=['extension_or_stop_geometry_failed']
            else:record['reasons']=['price_and_volume_breakout_not_confirmed']
        decisions.append(record)
    events=classify_setups(symbol,bars,decisions,policy,policy.setup,
        activation_state='independent_breakout_activation',cohort='independent_momentum')
    return dict(decisions=decisions,events=events,policy_sha256=policy.fingerprint(),
        recommendation_qualified=False,orders_submitted=0,experimental=True)
