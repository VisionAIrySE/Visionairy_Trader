"""Nonblocking account snapshots. Old observations never masquerade as current."""
from copy import deepcopy
import threading
import time


class AccountCache:
    def __init__(self, provider, ttl=15, retry_seconds=5, clock=time.monotonic):
        self.provider=provider;self.ttl=ttl;self.retry_seconds=retry_seconds;self.clock=clock
        self.lock=threading.Lock();self.data=None;self.completed=None
        self.attempted=None;self.refreshing=False;self.duration_ms=None;self.failed=False

    def _refresh(self):
        started=self.clock()
        try:
            data=self.provider()
            if not isinstance(data,dict):raise ValueError('Invalid account snapshot')
            failed=False
        except Exception:
            # Never return arbitrary exceptions, URLs, provider bodies or secrets.
            data=dict(status='unavailable',balances=None,positions=None,quotes=[],measured_net_return=None,
                reason='Account provider unavailable; no balance assumed',read_only=True,orders_submitted=0,
                scanner_connected=False)
            failed=True
        with self.lock:
            self.data=deepcopy(data);self.completed=self.clock();self.failed=failed
            self.duration_ms=round((self.completed-started)*1000,2);self.refreshing=False

    def get(self):
        with self.lock:
            now=self.clock();age=None if self.completed is None else now-self.completed
            due=self.data is None or age>=self.ttl or self.failed
            if due and not self.refreshing and (self.attempted is None or now-self.attempted>=self.retry_seconds):
                self.attempted=now;self.refreshing=True
                threading.Thread(target=self._refresh,daemon=True).start()
            if self.data is None:
                result=dict(status='refreshing',balances=None,positions=None,quotes=[],measured_net_return=None,
                    reason='Reading your broker account; numbers remain unavailable until verified',
                    read_only=True,orders_submitted=0,scanner_connected=False)
            elif age>=self.ttl:
                result=dict(status='stale',provider=self.data.get('provider'),environment=self.data.get('environment'),
                    balances=None,positions=None,quotes=[],measured_net_return=None,
                    reason='Previous account read is stale; refreshing before displaying numbers',
                    read_only=True,orders_submitted=0,scanner_connected=False)
            else:result=deepcopy(self.data)
            result.update(cache_age_seconds=None if age is None else round(age,2),
                refresh_in_progress=self.refreshing,refresh_duration_ms=self.duration_ms)
            return result
