"""Validate provider bid/ask timestamps; receipt time is not quote time."""
from decimal import Decimal as D

def quote_evidence(row,now):
    try:
        stamps=[row[k] for k in ('bid_date','ask_date')]
        if any(type(s) is not int or not 0<=now-s/1000<=60 for s in stamps):return None
        bid,ask=D(str(row['bid'])),D(str(row['ask']))
        if not bid.is_finite() or not ask.is_finite() or not 0<bid<=ask:return None
        return dict(symbol=row['symbol'],bid=str(bid),ask=str(ask),observed_at=min(stamps)//1000)
    except (KeyError,TypeError,ValueError,ArithmeticError):return None

