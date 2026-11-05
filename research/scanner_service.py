"""Hosted broad market-monitor lifecycle. No order methods or implicit paid activation."""
import os
import threading
import time
from broker_readonly import TradierReader
from market_monitor import MarketMonitor,unpack,ScanCancelled
from model_assessment import HostedAssessmentStore
from universe_refresh import UniverseRefresh,current_universe


class ScannerService:
    def __init__(self,env=None,store=None,monitor_factory=MarketMonitor,refresher=None):
        self.env=os.environ if env is None else env
        self.store=store;self.monitor_factory=monitor_factory
        self.refresher=refresher or UniverseRefresh()
        self.lock=threading.Lock();self.thread=None;self.current=None;self.refreshed=0
        self.cancel_event=threading.Event()
        self.stop_event=threading.Event()
        self.autorun_enabled=(self.env.get('SCANNER_AUTORUN','false').lower()=='true'
            and self.env.get('SCANNER_HOSTING_APPROVED','false').lower()=='true')
        if self.autorun_enabled:
            threading.Thread(target=self._loop,daemon=True).start()

    def _store(self):
        if self.store is None:self.store=HostedAssessmentStore(self.env)
        return self.store

    def _loop(self):
        while not self.stop_event.is_set():
            started=time.monotonic()
            self.start(False)
            self.stop_event.wait(max(5,300-(time.monotonic()-started)))

    def latest(self,page=0):
        if not isinstance(page,int) or not 0<=page<=10000:raise ValueError('Bounded page required')
        try:
            record=self._store().call('scan_latest',{})
            checkpoint=record.get('checkpoint',{})
            summary=checkpoint.get('summary',{'status':record.get('status','not_started')})
            if self.current and (record.get('status')=='not_started' or
                    (self.current.get('status')=='running' and summary.get('started_at',0)<self.current.get('started_at',0))):
                summary=dict(self.current)
            events=unpack(checkpoint['packed_events']) if checkpoint.get('packed_events') else []
            issues=unpack(checkpoint['packed_issues']) if checkpoint.get('packed_issues') else []
            return dict(summary=summary,worker_status=self.current,events=events[page*50:(page+1)*50],page=page,total_events=len(events),
                issues_sample=issues[:20],total_issues=len(issues),autorun_enabled=self.autorun_enabled,
                qualified_buy_recommendations_connected=False,orders_submitted=0,
                boundary='Observed quote coverage and coarse changes; strategy-specific entry and notification gates remain open')
        except Exception:
            return dict(summary={'status':'unavailable','stage':'store_unavailable'},events=[],
                autorun_enabled=self.autorun_enabled,qualified_buy_recommendations_connected=False,orders_submitted=0)

    def start(self,coverage_probe=True):
        with self.lock:
            if self.thread and self.thread.is_alive():return {'status':'running','orders_submitted':0}
            if (not self.env.get('TRADIER_PRODUCTION_TOKEN')
                    or self.env.get('TRADIER_DATA_ENVIRONMENT','production')!='production'):
                return {'status':'unavailable','reason':'Production market-data access is not configured','orders_submitted':0}
            try:store=self._store()
            except Exception:return {'status':'unavailable','reason':'Durable scanner storage is not configured','orders_submitted':0}
            self.current={'status':'running','stage':'preparing_universe','started_at':int(time.time()),'orders_submitted':0}
            self.cancel_event=threading.Event()
            def work():
                try:
                    saved=store.call('scan_universe_get',{})
                    universe=unpack(saved['packed_universe'])
                    reader=TradierReader(self.env['TRADIER_PRODUCTION_TOKEN'],'production')
                    clock,_=reader.get('markets/clock')
                    session=clock['clock']
                    if coverage_probe or (session.get('state')=='open' and not current_universe(universe,session['date'],time.time())):
                        with self.lock:self.current.update(stage='refreshing_daily_universe')
                        universe=self.refresher.refresh(store,session['date'],self.cancel_event)
                    value=self.monitor_factory(reader,store,cancel_event=self.cancel_event).run(universe,coverage_probe)
                except ScanCancelled:
                    value={'status':'cancelled','stage':'user_stopped','orders_submitted':0}
                except Exception:
                    value={'status':'failed','stage':'feed_or_universe_unavailable','orders_submitted':0}
                with self.lock:self.current=value
            self.thread=threading.Thread(target=work,daemon=True)
            self.thread.start()
            return dict(self.current)

    def stop(self):
        self.cancel_event.set()
        return {'status':'stopping','scope':'current_scan_only','orders_submitted':0}
