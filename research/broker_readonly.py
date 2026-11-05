"""Tradier observations only. Pinned GET routes; no orders, funding or writes."""
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from replay import DataError, NoRedirect


class ProviderReadError(DataError):
    """Sanitized failure category; never includes upstream body or credentials."""
    def __init__(self,message,category,http_status=None):
        super().__init__(message)
        self.category=category;self.http_status=http_status


def validate_history_params(path,params):
    if path=='markets/timesales':
        if set(params)!={'symbol','start','end','interval','session_filter'}:
            raise DataError('Explicit bounded historical parameters required')
        if not re.fullmatch(r'[A-Z][A-Z0-9./^\-]{0,14}',params['symbol']):
            raise DataError('Unqualified historical symbol')
        if params['interval'] not in ('1min','5min') or params['session_filter']!='open':
            raise DataError('Regular-session minute bars only')
        try:
            start=datetime.strptime(params['start'],'%Y-%m-%d %H:%M')
            end=datetime.strptime(params['end'],'%Y-%m-%d %H:%M')
        except (ValueError,TypeError):raise DataError('Explicit provider-local historical dates required') from None
        if not 0<(end-start).total_seconds()<=40*86400:
            raise DataError('Historical request must span at most 40 calendar days')
    elif path=='markets/lookup':
        if (set(params)!={'q'} or not isinstance(params['q'],str)
                or not re.fullmatch(r'[A-Za-z0-9 ./^\-]{1,60}',params['q'])):
            raise DataError('Bounded security lookup required')
    elif path=='markets/calendar':
        if (set(params)!={'month','year'} or not re.fullmatch(r'20\d{2}',params['year'])
                or not re.fullmatch(r'0?[1-9]|1[0-2]',params['month'])):
            raise DataError('Explicit calendar month and year required')
    else:raise DataError('Unsupported historical endpoint')


def decimal_text(value):
    if value is None:return None
    if isinstance(value,bool):raise DataError('Invalid numeric provider field')
    try:
        number=Decimal(str(value))
        if not number.is_finite():raise InvalidOperation()
        return str(number)
    except (InvalidOperation,ValueError):raise DataError('Invalid numeric provider field') from None


def as_rows(value):
    if value is None or value=='null':return []
    if isinstance(value,dict):return [value]
    if isinstance(value,list) and all(isinstance(x,dict) for x in value):return value
    raise DataError('Unsupported provider collection')


class TradierReader:
    def __init__(self,token,environment,opener=None,clock=time.time):
        if environment not in ('production','sandbox') or not token or any(c.isspace() for c in token):
            raise DataError('Explicit environment and valid server credential required')
        self.environment=environment;self._token=token;self._clock=clock
        self._base='https://'+('api' if environment=='production' else 'sandbox')+'.tradier.com/v1/'
        self._opener=opener or urllib.request.build_opener(NoRedirect())

    def get(self,path,params=None):
        if not (path in ('user/profile','markets/quotes','markets/clock','markets/timesales','markets/calendar','markets/lookup') or
                re.fullmatch(r'accounts/[A-Za-z0-9_-]{1,40}/(balances|positions)',path)):
            raise DataError('Endpoint outside read-only allowlist')
        params=params or {}
        if path in ('markets/timesales','markets/calendar','markets/lookup'):
            validate_history_params(path,params)
        elif path=='markets/quotes':
            if set(params)!={'symbols'} or not re.fullmatch(r'[A-Z0-9./^-]+(?:,[A-Z0-9./^-]+){0,49}',params['symbols']):
                raise DataError('Bounded explicit symbol list required')
        elif params:raise DataError('Unexpected endpoint parameters')
        url=self._base+path+('?' + urllib.parse.urlencode(params) if params else '')
        req=urllib.request.Request(url,method='GET',headers={'Authorization':'Bearer '+self._token,'Accept':'application/json'})
        try:
            with self._opener.open(req,timeout=5) as response:raw=response.read(2*1024*1024+1)
        except urllib.error.HTTPError as exc:
            body=exc.read(4096)
            if exc.code==429 or b'Quota Violation' in body:
                raise ProviderReadError('Tradier rate limit reached','rate_limit',exc.code) from None
            if exc.code in (401,403):
                raise ProviderReadError('Tradier credentials or permissions rejected','permissions',exc.code) from None
            raise ProviderReadError('Tradier request failed','provider_http',exc.code) from None
        except (urllib.error.URLError,TimeoutError,OSError):raise DataError('Tradier connection unavailable') from None
        if len(raw)>2*1024*1024:raise DataError('Tradier response exceeds bounded size')
        if b'Quota Violation' in raw:raise DataError('Tradier rate limit reached')
        try:payload=json.loads(raw,parse_float=Decimal)
        except (ValueError,UnicodeError):raise DataError('Invalid Tradier response') from None
        if not isinstance(payload,dict) or payload.get('errors'):raise DataError('Tradier returned an error')
        return payload,dict(provider='Tradier',endpoint=path.split('/')[-1],retrieved_at=int(self._clock()),
            payload_sha256=hashlib.sha256(raw).hexdigest(),environment=self.environment,
            provider_as_of=None,timestamp_note='Retrieval time is not a provider valuation timestamp')

    def snapshot(self,account_id=None):
        result=dict(status='unavailable',provider='Tradier',environment=self.environment,
            evidence_mode='broker_observed' if self.environment=='production' else 'broker_paper_account',
            balances=None,positions=None,quotes=[],market_clock=None,sources={},errors={},
            measured_net_return=None,return_reason='No reconciled performance baseline or cash-flow history',
            planned_risk=None,risk_reason='Protective orders and cumulative exposure not yet reconciled',
            read_only=True,orders_submitted=0,scanner_connected=False)
        try:
            profile,source=self.get('user/profile');result['sources']['profile']=source
            profile_body=profile.get('profile')
            if not isinstance(profile_body,dict):raise DataError('Missing account profile evidence')
            accounts=as_rows(profile_body.get('account'))
            identifiers=[str(a['account_number']) for a in accounts if a.get('account_number')]
            if account_id is None:
                if len(identifiers)!=1:raise DataError('Choose an account in secure server configuration')
                account_id=identifiers[0]
            if account_id not in identifiers or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',account_id):
                raise DataError('Configured account is not in the authenticated profile')
            result['account_label']='Account ending '+account_id[-4:]
        except DataError as exc:
            result['errors']['account']=str(exc);return result
        for component in ('balances','positions'):
            try:
                payload,source=self.get('accounts/'+account_id+'/'+component)
                result['sources'][component]=source
                if component=='balances':
                    b=payload.get('balances')
                    if not isinstance(b,dict):raise DataError('Missing balance evidence')
                    cash=b.get('cash') or {}
                    if not isinstance(cash,dict):raise DataError('Invalid cash evidence')
                    result['balances']=dict(total_equity=decimal_text(b.get('total_equity')),
                        total_cash=decimal_text(b.get('total_cash')),cash_available=decimal_text(cash.get('cash_available')),
                        unsettled_funds=decimal_text(cash.get('unsettled_funds')),account_type=b.get('account_type'),
                        source_fields={'total_equity':'balances.total_equity','total_cash':'balances.total_cash',
                                       'cash_available':'balances.cash.cash_available'})
                else:
                    if 'positions' not in payload:raise DataError('Missing position evidence')
                    container=payload['positions']
                    if container is None or container=='null':rows=[]
                    elif isinstance(container,dict) and 'position' in container:rows=as_rows(container['position'])
                    else:raise DataError('Invalid position evidence')
                    positions=[]
                    for row in rows:
                        if not row.get('symbol') or row.get('quantity') is None:raise DataError('Incomplete position evidence')
                        positions.append(dict(symbol=str(row['symbol']),quantity=decimal_text(row['quantity']),
                            cost_basis=decimal_text(row.get('cost_basis')),date_acquired=row.get('date_acquired')))
                    result['positions']=positions
            except DataError as exc:result['errors'][component]=str(exc)
        symbols=sorted({p['symbol'] for p in result['positions'] or [] if re.fullmatch(r'[A-Z][A-Z0-9./^-]{0,19}',p['symbol'])})
        if symbols:
            try:
                if len(symbols)>50:raise DataError('Held-symbol quote batch exceeds current adapter limit')
                payload,source=self.get('markets/quotes',dict(symbols=','.join(symbols)))
                result['sources']['quotes']=source
                container=payload.get('quotes')
                if not isinstance(container,dict) or 'quote' not in container:raise DataError('Missing quote evidence')
                for q in as_rows(container['quote']):
                    if q.get('symbol') not in symbols:raise DataError('Unexpected quote identity')
                    item=dict(symbol=q['symbol'],last=decimal_text(q.get('last')),bid=decimal_text(q.get('bid')),ask=decimal_text(q.get('ask')))
                    for key in ('trade_date','bid_date','ask_date'):
                        stamp=q.get(key)
                        if stamp is not None and (type(stamp) is not int or stamp<946684800000 or stamp>int(self._clock()*1000)+1000):
                            raise DataError('Invalid or future quote timestamp')
                        item[key]=stamp
                    ages=[int(self._clock())-item[k]//1000 for k in ('bid_date','ask_date') if item[k] is not None]
                    item['fresh_for_entry']=self.environment=='production' and len(ages)==2 and all(0<=a<=60 for a in ages) and item['bid'] is not None and item['ask'] is not None and Decimal(item['ask'])>=Decimal(item['bid'])>0
                    item['data_label']='Delayed paper quote' if self.environment=='sandbox' else 'Provider quote; check individual timestamps'
                    result['quotes'].append(item)
            except DataError as exc:result['quotes']=[];result['errors']['quotes']=str(exc)
        result['status']='connected' if result['balances'] is not None and result['positions'] is not None else 'partial'
        if result['balances'] is not None and any(result['balances'][k] is None for k in ('total_equity','total_cash')):
            result['status']='partial'
        return result


def configured_snapshot(environment=None,opener=None,clock=time.time):
    env=environment if environment is not None else os.environ
    mode=env.get('TRADIER_DATA_ENVIRONMENT')
    token=env.get('TRADIER_PRODUCTION_TOKEN') if mode=='production' else env.get('TRADIER_SANDBOX_TOKEN') if mode=='sandbox' else None
    if not mode or not token:
        return dict(status='not_connected',provider='Tradier',environment=mode,balances=None,positions=None,quotes=[],
            measured_net_return=None,read_only=True,orders_submitted=0,scanner_connected=False,
            reason='Tradier server credential and data environment have not been configured')
    try:return TradierReader(token,mode,opener,clock).snapshot(env.get('TRADIER_ACCOUNT_ID') or None)
    except DataError:
        return dict(status='unavailable',provider='Tradier',environment=mode,balances=None,positions=None,quotes=[],
            measured_net_return=None,read_only=True,orders_submitted=0,scanner_connected=False,
            reason='Tradier secure configuration is invalid')
