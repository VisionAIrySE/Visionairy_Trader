"""Explicit conditional target and paper-liquidity assumptions, never forecasts."""
from dataclasses import asdict
from decimal import Decimal as D,ROUND_FLOOR
from setup_detection import fingerprint,validate_bars
from quote_evidence import quote_evidence
from replay import DataError


def target_hypotheses(event,bars,now,source_sha256,bar_minutes=5):
    if type(now) is not int or event['available_at']>now:raise DataError('Observable setup required')
    prior=[b for b in bars if b.timestamp+bar_minutes*60<=event['available_at']]
    validate_bars(prior,bar_minutes)
    entry,stop=D(event['entry_reference']),D(event['proposed_stop'])
    if not entry.is_finite() or not stop.is_finite() or not 0<stop<entry:raise DataError('Supported target geometry required')
    if not prior or prior[-1].timestamp+bar_minutes*60!=event['available_at']:
        raise DataError('Completed setup bar required')
    source=fingerprint(dict(event=event,bars=[asdict(b) for b in prior]))
    return [dict(symbol=event['symbol'],available_at=event['available_at'],price=str(entry+r*(entry-stop)),
        source_sha256=source,source_packet_sha256=source_sha256,method_version='risk_multiple_hypothesis_v1',
        horizon_minutes=780,risk_multiple=str(r),reference_entry=str(entry),stop_price=str(stop),
        evidence='unvalidated_geometry_not_price_forecast',support='experimental_assumption',
        expected_return=None,win_probability=None) for r in (D(2),D(3))]


def paper_liquidity(row,bars,now,source_sha256,quote_sha256,participation=D('.01')):
    participation=D(str(participation))
    if not participation.is_finite() or not 0<participation<=D('.01'):raise DataError('Bounded paper participation required')
    result=dict(status='unknown',available_at=now,source_sha256=[source_sha256,quote_sha256],
        maximum_quantity=None,method_version='recent_bar_participation_assumption_v1',
        participation_fraction=str(participation),support='unvalidated_execution_assumption',
        displayed_size_units_qualified=False,fill_guaranteed=False,reasons=[])
    q=quote_evidence(row or {},now)
    if q is None:result['reasons']=['fresh_bid_ask_required'];return result
    prior=[b for b in bars if b.timestamp+300<=now]
    validate_bars(prior,5);recent=prior[-3:]
    if (len(recent)!=3 or any(b.timestamp-a.timestamp!=300 or b.session!=a.session for a,b in zip(recent,recent[1:]))
            or not 0<=now-(recent[-1].timestamp+300)<=300):
        result['reasons']=['fresh_contiguous_bar_volume_required'];return result
    cap=int((min(b.volume for b in recent)*participation).to_integral_value(rounding=ROUND_FLOOR))
    spread=(D(q['ask'])-D(q['bid']))/((D(q['ask'])+D(q['bid']))/2)
    result.update(maximum_quantity=cap,spread_fraction=str(spread),quote=q,
        status='pass' if cap>0 and spread<=D('.02') else 'fail',
        reasons=['paper_participation_and_spread_assumptions_pass'] if cap>0 and spread<=D('.02')
        else ['paper_capacity_or_spread_limit_failed'])
    return result
