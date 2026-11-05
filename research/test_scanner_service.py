from unittest.mock import patch
import unittest
from market_monitor import pack
from scanner_service import ScannerService

NOW=1793914683

class ServiceTests(unittest.TestCase):
    def make(self,state='open',fail=False):
        calls=[]
        universe={'available_at':NOW,'symbols':['TEST'],'sources':[
            {'directory':kind,'provider_creation_label':'File Creation Time: 1105202615:41'}
            for kind in ('nasdaq','other')]}
        class Store:
            def call(self,op,p):
                if op=='scan_universe_get':return {'packed_universe':pack(universe)}
                return {'status':'complete','checkpoint':{'summary':{'status':'complete','started_at':NOW-100}}}
        class Reader:
            def __init__(self,*args):pass
            def get(self,*args):return {'clock':{'state':state,'date':'2026-11-05'}},{}
        class Refresh:
            def refresh(self,store,session,cancel):
                calls.append(('refresh',session))
                if fail:raise ValueError('source unavailable')
                return dict(universe,refreshed=True)
        class Monitor:
            def __init__(self,*args,**kwargs):pass
            def run(self,u,probe):calls.append(('run',u.get('refreshed',False),probe));return {'status':'complete'}
        service=ScannerService(env={'TRADIER_PRODUCTION_TOKEN':'fixture'},store=Store(),
            monitor_factory=Monitor,refresher=Refresh())
        return service,Reader,calls,universe

    def test_manual_coverage_test_verifies_refresh_even_with_a_current_saved_list(self):
        service,reader,calls,_=self.make()
        with patch('scanner_service.TradierReader',reader),patch('scanner_service.time.time',return_value=NOW):
            self.assertEqual(service.start(True)['status'],'running');service.thread.join(2)
        self.assertFalse(service.thread.is_alive())
        self.assertEqual(calls,[('refresh','2026-11-05'),('run',True,True)])

    def test_closed_scheduled_scan_does_not_download_a_directory(self):
        service,reader,calls,u=self.make(state='closed');u['available_at']=NOW-172800
        with patch('scanner_service.TradierReader',reader),patch('scanner_service.time.time',return_value=NOW):
            service.start(False);service.thread.join(2)
        self.assertEqual(calls,[('run',False,False)])

    def test_stale_open_list_refreshes_and_preparation_failure_remains_visible(self):
        service,reader,calls,u=self.make(fail=True);u['available_at']=NOW-172800
        with patch('scanner_service.TradierReader',reader),patch('scanner_service.time.time',return_value=NOW):
            service.start(False);service.thread.join(2)
        self.assertEqual(calls,[('refresh','2026-11-05')])
        latest=service.latest()
        self.assertEqual(latest['worker_status']['status'],'failed')
        self.assertEqual(latest['summary']['status'],'complete')
