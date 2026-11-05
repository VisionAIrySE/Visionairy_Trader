"""Nonblocking dashboard entry to an explicitly synthetic, persisted ghost review."""
import os
import threading
import time
from model_assessment import AssessmentError, HostedAssessmentStore, ModelAssessment, build_ghost_context


class AssessmentService:
    def __init__(self, env=None, store=None, runner_factory=ModelAssessment, context_factory=build_ghost_context):
        self.env = os.environ if env is None else env
        self.store = store
        self.runner_factory, self.context_factory = runner_factory, context_factory
        self.lock = threading.Lock()
        self.thread = None
        self.current = None
        self.refreshed = 0

    def _store(self):
        if self.store is None:
            self.store = HostedAssessmentStore(self.env)
        return self.store

    def latest(self):
        with self.lock:
            if self.current is not None and time.monotonic() - self.refreshed < 3:
                return self.current
        try:
            record = self._store().call('latest', {})
            result = record.get('checkpoint', {}).get('result')
            value = result or dict(status=record['status'], job_id=record.get('id'),
                stage=record.get('checkpoint', {}).get('stage'), orders_submitted=0)
        except Exception:
            value = dict(status='unavailable', reason='Assessment storage or model access is not configured', orders_submitted=0)
        with self.lock:
            self.current, self.refreshed = value, time.monotonic()
        return value

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                return self.current
            if not self.env.get('OPENROUTER_API_KEY'):
                return dict(status='unavailable', reason='Model access is not configured', orders_submitted=0)
            try:
                store = self._store()
            except AssessmentError:
                return dict(status='unavailable', reason='Authoritative assessment storage is not configured', orders_submitted=0)
            self.current = dict(status='running', stage='preparing_evidence', mode='ghost',
                evidence_origin='synthetic_acceptance_fixture', orders_submitted=0)
            def work():
                try:
                    value = self.runner_factory(store, self.env['OPENROUTER_API_KEY']).run(self.context_factory())
                except Exception:
                    value = dict(status='unavailable', reason='Assessment did not complete; retained audit requires review', orders_submitted=0)
                with self.lock:
                    self.current, self.refreshed = value, time.monotonic()
            self.thread = threading.Thread(target=work, daemon=True)
            self.thread.start()
            return dict(self.current)
