"""Observed appreciation leaders, separate from entry approval or return forecasts."""
from decimal import Decimal, InvalidOperation


def positive(value):
    try:
        if isinstance(value, bool):return None
        result=Decimal(str(value))
        return result if result.is_finite() and result>0 else None
    except (InvalidOperation, ValueError, TypeError):return None


def appreciation_leaders(observed, day, previous=None):
    """Rank positive same-session common shares; never use future bars or closing winners.

    The larger of since-open and prior-close appreciation is the initial ordering, not a buy score.
    Open and scan-to-scan changes distinguish gaps from subsequent movement.
    No minimum gain, price, capitalization or chart-pattern gate is imposed.
    """
    leaders=[]
    for symbol,q in observed.items():
        if q.get('session')!=day or q.get('security_status')!='directory_and_broker_common_share_indicated':continue
        last,close=positive(q.get('last')),positive(q.get('prevclose'))
        opening=positive(q.get('open'))
        if last is None:continue
        close_gain=(last/close-1)*100 if close else None
        open_gain=(last/opening-1)*100 if opening else None
        measured=[v for v in (close_gain,open_gain) if v is not None]
        if not measured or max(measured)<=0:continue
        recent=None;elapsed=None
        prior=(previous or {}).get(symbol,{})
        old=positive(prior.get('last'))
        if old is not None and prior.get('session')==day:
            seconds=q['received_at']-prior['received_at']
            if 0<seconds<=600 and prior['trade_at_ms']<q['trade_at_ms']:
                recent=str((last/old-1)*100);elapsed=seconds
        leaders.append(dict(symbol=symbol,last=str(last),gain_from_prior_close_pct=str(close_gain) if close_gain is not None else None,
            gain_from_open_pct=str(open_gain) if open_gain is not None else None,
            ranking_gain_pct=str(max(measured)),
            recent_change_pct=recent,recent_window_seconds=elapsed,volume=q.get('volume'),
            trade_at_ms=q.get('trade_at_ms'),received_at=q.get('received_at'),
            fresh_regular_session=q.get('fresh_regular_session',False),recommendation_qualified=False))
    return sorted(leaders,key=lambda r:(-Decimal(r['ranking_gain_pct']),r['symbol']))
