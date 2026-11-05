"""Authenticated research-data reads using the existing server credential.

No credential export, order transport, disk writes or implicit study qualification.
"""
import os
import threading
import time
import re
from datetime import datetime,timezone

from broker_readonly import TradierReader,validate_history_params,ProviderReadError
from replay import DataError,parse_bars


class HistoryGateway:
    def __init__(self,env=None,opener=None,clock=time.monotonic):
        self.env=os.environ if env is None else env
        self.opener=opener;self.clock=clock;self.lock=threading.Lock();self.next_read=0

    def read(self,kind,params):
        path={'history':'markets/timesales','calendar':'markets/calendar','lookup':'markets/lookup',
              'quotes':'markets/quotes','clock':'markets/clock'}.get(kind)
        query=dict(params)
        if kind=='history':query['session_filter']='open'
        try:
            if kind=='quotes':
                if (set(query)!={'symbols'} or not isinstance(query['symbols'],str)
                        or not re.fullmatch(r'[A-Z0-9./^-]+(?:,[A-Z0-9./^-]+){0,499}',query['symbols'])):
                    raise DataError('Bounded explicit quote symbols required')
            elif kind=='clock':
                if query:raise DataError('Market clock takes no query parameters')
            else:validate_history_params(path,query)
        except (DataError,TypeError):return 400,dict(status='invalid_request',error='Invalid or unbounded research-data request')
        if not self.lock.acquire(blocking=False):return 429,dict(status='busy',retry_after_seconds=2)
        try:
            if self.clock()<self.next_read:return 429,dict(status='rate_limited',retry_after_seconds=2)
            self.next_read=self.clock()+2
            if self.env.get('TRADIER_DATA_ENVIRONMENT','production')!='production':
                return 503,dict(status='unavailable',error='Production historical observations required')
            token=self.env.get('TRADIER_PRODUCTION_TOKEN','')
            if not token:return 503,dict(status='unavailable',error='Server market-data credential is not configured')
            try:
                reader=TradierReader(token,'production',self.opener)
                payload,source=(reader.get_many_quotes(query['symbols'])
                    if kind=='quotes' and len(query['symbols'].split(','))>50 else reader.get(path,query))
                source.update(request=query)
                result=dict(status='observed',source=source,payload=payload,
                            representative_strategy_study_ready=False,orders_submitted=0)
                if kind=='history':
                    series=payload.get('series')
                    if series is None or (isinstance(series,dict) and not series.get('data')):
                        result.update(status='no_bars_returned',bars=0)
                    else:
                        bars=parse_bars(payload)
                        start=datetime.strptime(query['start'],'%Y-%m-%d %H:%M')
                        end=datetime.strptime(query['end'],'%Y-%m-%d %H:%M')
                        rows=series['data'] if isinstance(series['data'],list) else [series['data']]
                        for row,bar in zip(rows,bars):
                            label=datetime.fromisoformat(row['time'])
                            utc=datetime.fromtimestamp(bar.timestamp,timezone.utc).replace(tzinfo=None)
                            if (label.tzinfo is not None or not start<=label<=end
                                    or (utc-label).total_seconds() not in (14400,18000)):
                                raise DataError('Historical response clock or requested range disagrees')
                        result.update(bars=len(bars),first_epoch=bars[0].timestamp,last_epoch=bars[-1].timestamp)
                elif kind=='lookup':
                    securities=payload.get('securities')
                    if not (securities is None or isinstance(securities,dict)):
                        raise DataError('Invalid security lookup evidence')
                    if 'securities' not in payload:
                        raise DataError('Missing security lookup evidence')
                    result['mapping_confirmed']=False
                elif kind=='quotes':
                    if 'quotes' not in payload:raise DataError('Missing quote collection')
                    result['recommendation_qualified']=False
                elif kind=='clock':
                    if not isinstance(payload.get('clock'),dict):raise DataError('Missing market clock')
                elif not isinstance(payload.get('calendar'),dict):
                    raise DataError('Missing calendar evidence')
                return 200,result
            except ProviderReadError as exc:
                return 502,dict(status='unavailable',error=str(exc),provider_http_status=exc.http_status,
                    failure_category=exc.category,retryable=exc.http_status==429 or exc.http_status>=500,
                    orders_submitted=0)
            except DataError as exc:return 502,dict(status='unavailable',error=str(exc),orders_submitted=0)
            except Exception:return 502,dict(status='unavailable',error='Historical provider read failed',orders_submitted=0)
        finally:self.lock.release()
