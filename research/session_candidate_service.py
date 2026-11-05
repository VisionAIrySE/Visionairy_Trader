"""Nonblocking authenticated current-session probe lifecycle."""
import os
import threading
import time
from broker_readonly import TradierReader
from model_assessment import HostedAssessmentStore
from market_monitor import unpack,digest,ScanCancelled
from session_candidates import SessionCandidates

class SessionCandidateService:
    def __init__(self,env=None,store=None):
        self.env=os.environ if env is None else env;self.store=store
        self.lock=threading.Lock();self.thread=None;self.worker=None;self.cancel=threading.Event()
    def _store(self):
        if self.store is None:self.store=HostedAssessmentStore(self.env)
        return self.store
    def latest(self,page=0):
        if type(page) is not int or not 0<=page<=10000:raise ValueError('Bounded page required')
        try:
            saved=self._store().call('session_candidate_get',{})
            if not saved.get('packed_report'):return dict(status='not_started',worker=self.worker,orders_submitted=0)
            report=unpack(saved['packed_report'])
            if digest(report)!=saved['sha256']:raise ValueError('Stored session identity mismatch')
            reviews={r['event_id']:r for r in report['review']['allocation']['reviews']}
            return dict(status=report['status'],worker=self.worker,page=page,page_size=25,total=len(report['events']),
                session=report['market_clock'],scope=report['scope'],selection=report['selection'],coverage=report['coverage'],
                started_at=report['started_at'],finished_at=report['finished_at'],setup_counts=report['setup_counts'],
                allocation_summary={k:v for k,v in report['review']['allocation'].items() if k not in ('reviews','comparisons')},
                paper_comparison_config=report.get('paper_comparison_config',{}),cost_assumptions=report.get('cost_assumptions',{}),
                rows=[dict(event=e,review=reviews[e['event_id']],targets=report.get('target_hypotheses',{}).get(e['event_id'],[]),
                    liquidity=report.get('liquidity_reviews',{}).get(e['event_id'])) for e in report['events'][page*25:(page+1)*25]],
                limitations=report['limitations'],recommendation_qualified=False,orders_submitted=0)
        except Exception:return dict(status='unavailable',worker=self.worker,orders_submitted=0)
    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():return dict(self.worker)
            if not self.env.get('TRADIER_PRODUCTION_TOKEN') or self.env.get('TRADIER_DATA_ENVIRONMENT','production')!='production':
                return dict(status='unavailable',reason='Production market-data access required')
            try:store=self._store()
            except Exception:return dict(status='unavailable',reason='Durable research storage required')
            self.cancel=threading.Event();self.worker=dict(status='running',stage='preparing_session_probe',started_at=int(time.time()),completed=0,total=20)
            def progress(value):
                with self.lock:self.worker.update(value)
            def work():
                try:
                    report=SessionCandidates(TradierReader(self.env['TRADIER_PRODUCTION_TOKEN'],'production'),store,
                        progress=progress,cancel=self.cancel).run()
                    progress(dict(status='complete',stage='saved',total=len(report['coverage']),completed=len(report['coverage'])))
                except ScanCancelled:progress(dict(status='cancelled',stage='stopped'))
                except Exception:progress(dict(status='failed',stage='session_feed_or_prerequisite_unavailable'))
            self.thread=threading.Thread(target=work,daemon=True);self.thread.start()
            return dict(self.worker)
    def stop(self):
        self.cancel.set();return dict(status='stopping',scope='current_session_probe_only')
