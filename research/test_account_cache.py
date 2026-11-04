"""Concurrency and stale-evidence behavior, without live provider access."""
import threading
import time
import unittest
from account_cache import AccountCache


class AccountCacheTests(unittest.TestCase):
    def test_slow_provider_does_not_block_readers_or_create_duplicate_refreshes(self):
        entered=threading.Event();release=threading.Event();finished=threading.Event();calls=[]
        def provider():
            calls.append(1);entered.set();release.wait(2)
            finished.set();return dict(status='connected',balances={'total_cash':'0'},positions=[])
        cache=AccountCache(provider)
        started=time.monotonic();first=cache.get()
        self.assertLess(time.monotonic()-started,.5)
        self.assertEqual(first['status'],'refreshing');self.assertIsNone(first['balances'])
        self.assertTrue(entered.wait(1))
        for _ in range(10):self.assertTrue(cache.get()['refresh_in_progress'])
        self.assertEqual(len(calls),1)
        release.set();self.assertTrue(finished.wait(1))

    def completed_cache(self,provider,clock=None):
        cache=AccountCache(provider,clock=clock or time.monotonic)
        cache.get()
        deadline=time.monotonic()+1
        while cache.refreshing and time.monotonic()<deadline:time.sleep(.001)
        self.assertFalse(cache.refreshing)
        return cache

    def test_stale_numbers_are_removed_while_refresh_is_pending(self):
        now=[100];calls=[];block=threading.Event()
        def provider():
            calls.append(1)
            if len(calls)>1:block.wait(1)
            return dict(status='connected',balances={'total_cash':'123'},positions=[])
        cache=self.completed_cache(provider,lambda:now[0])
        self.assertEqual(cache.get()['balances']['total_cash'],'123')
        now[0]=116
        stale=cache.get();self.assertEqual(stale['status'],'stale')
        self.assertIsNone(stale['balances']);self.assertIsNone(stale['positions'])
        block.set()

    def test_provider_exception_is_sanitized_and_backed_off(self):
        now=[100];calls=[]
        def provider():calls.append(1);raise RuntimeError('sensitive-token-and-response')
        cache=self.completed_cache(provider,lambda:now[0])
        result=cache.get();self.assertEqual(result['status'],'unavailable')
        self.assertNotIn('sensitive',str(result));self.assertEqual(len(calls),1)

    def test_response_mutation_cannot_change_cached_observations(self):
        cache=self.completed_cache(lambda:dict(status='connected',balances={'total_cash':'123'}))
        result=cache.get();result['balances']['total_cash']='999'
        self.assertEqual(cache.get()['balances']['total_cash'],'123')


if __name__=='__main__':unittest.main()
