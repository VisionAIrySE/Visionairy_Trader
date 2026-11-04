"""Chronological paper ledger. Explicit session settlement; no broker transport."""
from copy import deepcopy
from decimal import Decimal as D

from acquisition_funnel import number
from managed_replay import paper_entry_pause
from replay import DataError
from setup_detection import fingerprint


class PaperLedger:
    def __init__(self, cash, calendar, settlement_sessions, version, mode='counterfactual'):
        if mode not in ('paper','counterfactual') or not version:
            raise DataError('Versioned paper ledger only')
        if type(settlement_sessions) is not int or settlement_sessions < 1:
            raise DataError('Explicit positive settlement-session lag required')
        self.calendar=deepcopy(calendar)
        prior=None
        for w in calendar:
            if (type(w.get('open')) is not int or type(w.get('close')) is not int
                    or w['open']>=w['close'] or prior is not None and w['open']<prior):
                raise DataError('Qualified chronological session calendar required')
            prior=w['close']
        if not calendar:raise DataError('Session calendar required')
        self.cash=number(cash)
        if self.cash<=0:raise DataError('Positive initial paper cash required')
        self.initial_cash=self.cash
        self.version=version;self.mode=mode;self.lag=settlement_sessions
        self.now=calendar[0]['open'];self.session=0
        self.positions={};self.reservations={};self.unsettled=[];self.events=[]
        self.realized=D(0);self.baseline=self.cash;self.paused=False

    def _record(self, kind, terms):
        payload=dict(kind=kind,at=self.now,terms=terms,version=self.version,
                     previous_hash=self.events[-1]['hash'] if self.events else '')
        payload['hash']=fingerprint(payload);self.events.append(payload)

    def advance(self, now):
        if type(now) is not int or now<self.now:raise DataError('Ledger cannot travel backwards')
        # Baselines use the last known marks before the new session, not its future close.
        for i,w in enumerate(self.calendar):
            if i>self.session and w['open']<=now:
                self.baseline=self.equity();self.paused=False;self.session=i
        self.now=now
        due=[x for x in self.unsettled if x['settles_at'] is not None and x['settles_at']<=now]
        for x in due:
            self.cash+=x['amount'];self.unsettled.remove(x)
            self._record('settlement',dict(amount=str(x['amount']),source=x['source']))

    def equity(self):
        return self.cash+sum((x['amount'] for x in self.unsettled),D(0))+sum(
            (p['quantity']*p['mark'] for p in self.positions.values()),D(0))

    def risk(self):
        return sum((p['planned_risk'] for p in self.positions.values()),D(0))+sum(
            (number(r['planned_risk']) for r in self.reservations.values()),D(0))

    def available_cash(self):
        return self.cash-sum((number(r['entry_cash']) for r in self.reservations.values()),D(0))

    def snapshot(self, maximum_mark_age_seconds):
        fresh=all(0<=self.now-p['marked_at']<=maximum_mark_age_seconds for p in self.positions.values())
        pause=paper_entry_pause(self.baseline,self.equity(),0,fresh,self.paused,self.mode)
        self.paused=pause['paused_for_session']
        risk_by_symbol={s:str(p['planned_risk']) for s,p in self.positions.items()}
        return dict(mode=self.mode,equity=str(self.equity()),settled_cash=str(self.available_cash()),
            total_open_risk=str(self.risk()),trade_risk_by_symbol=risk_by_symbol,
            observed_at=self.now,open_symbols=sorted(set(self.positions)|{r['symbol'] for r in self.reservations.values()}),
            new_entries_allowed=pause['new_entries_allowed'],pause=pause,
            unsettled_proceeds=str(sum((x['amount'] for x in self.unsettled),D(0))),
            realized_net_pnl=str(self.realized),valuation_fresh=fresh)

    def reserve(self, reservation):
        key=reservation['event_id']
        if key in self.reservations:
            if self.reservations[key]!=reservation:raise DataError('Conflicting duplicate reservation')
            return
        if reservation['state']!='conditional_research_reservation' or reservation['reserved_at']!=self.now:
            raise DataError('Current qualified reservation required')
        symbol=reservation['symbol'];risk=number(reservation['planned_risk']);cash=number(reservation['entry_cash'])
        if symbol in self.positions or any(r['symbol']==symbol for r in self.reservations.values()):
            raise DataError('Addition requires separate cumulative-risk review')
        if min(cash,risk)<=0 or cash>self.available_cash() or risk>self.equity()*D('.01') or self.risk()+risk>self.equity()*D('.05'):
            raise DataError('Reservation exceeds shared cash or risk ceilings')
        if self.paused:raise DataError('Paper session paused')
        self.reservations[key]=deepcopy(reservation);self._record('reserve',deepcopy(reservation))

    def cancel(self, key, reason):
        if key not in self.reservations:raise DataError('Unknown reservation')
        del self.reservations[key];self._record('release_unfilled_reservation',dict(event_id=key,reason=reason))

    def enter(self, key, quantity, price, fee, planned_risk):
        r=self.reservations.get(key)
        if r is None:raise DataError('Unreserved or duplicate entry')
        price,fee,risk=map(number,(price,fee,planned_risk));cost=quantity*price+fee
        if (type(quantity) is not int or not 0<quantity<=r['quantity'] or price<=0 or fee<0 or risk<=0
                or price>number(r['maximum_entry_price']) or cost>number(r['entry_cash'])
                or risk>number(r['planned_risk'])):
            raise DataError('Entry exceeds exact reservation')
        # Equity may have fallen since reservation. Do not enlarge the current ceilings.
        other_risk=self.risk()-number(r['planned_risk'])
        if self.paused or risk>self.equity()*D('.01') or other_risk+risk>self.equity()*D('.05'):
            self.cancel(key,'current_equity_or_pause_invalidates_reservation');return False
        del self.reservations[key];self.cash-=cost
        self.positions[r['symbol']]=dict(event_id=key,quantity=quantity,mark=price,marked_at=self.now,
            entry_cost=cost,planned_risk=risk,stop=number(r['management']['protective_stop']))
        self._record('modeled_entry',dict(event_id=key,symbol=r['symbol'],quantity=quantity,price=str(price),fee=str(fee)))
        return True

    def mark(self, symbol, price, available_at):
        if symbol not in self.positions:return
        price=number(price)
        if price<=0 or type(available_at) is not int or available_at>self.now or available_at<self.positions[symbol]['marked_at']:
            raise DataError('Positive prior-only chronological valuation required')
        self.positions[symbol].update(mark=price,marked_at=available_at)

    def exit(self, symbol, quantity, price, fee, reason):
        p=self.positions.get(symbol);price,fee=map(number,(price,fee))
        if p is None or type(quantity) is not int or not 0<quantity<=p['quantity'] or price<=0 or fee<0:
            raise DataError('Exit cannot create a short position')
        proceeds=quantity*price-fee
        if proceeds<0:raise DataError('Exit costs exceed proceeds')
        trade_session=next((i for i,w in enumerate(self.calendar) if w['open']<=self.now<=w['close']),None)
        if trade_session is None:raise DataError('Exit outside qualified session')
        basis=p['entry_cost']*quantity/p['quantity'];self.realized+=proceeds-basis
        due=trade_session+self.lag
        settles=self.calendar[due]['open'] if due<len(self.calendar) else None
        self.unsettled.append(dict(amount=proceeds,settles_at=settles,source=p['event_id']))
        remaining=p['quantity']-quantity
        p['entry_cost']-=basis;p['planned_risk']*=D(remaining)/p['quantity'];p['quantity']=remaining
        self._record('modeled_exit',dict(symbol=symbol,quantity=quantity,price=str(price),fee=str(fee),reason=reason,
                                       settles_at=settles,net_realized=str(proceeds-basis)))
        if not remaining:del self.positions[symbol]

    def report(self):
        return dict(mode=self.mode,policy_version=self.version,settlement_sessions=self.lag,
            initial_cash=str(self.initial_cash),settled_cash=str(self.cash),available_cash=str(self.available_cash()),
            unsettled_proceeds=str(sum((x['amount'] for x in self.unsettled),D(0))),
            marked_equity=str(self.equity()),realized_net_pnl=str(self.realized),
            total_planned_risk=str(self.risk()),positions=deepcopy(self.positions),
            reservations=deepcopy(self.reservations),events=deepcopy(self.events),
            mode_description='conditional_model_not_broker_account',orders_submitted=0)
