import unittest
from market_monitor import pack,digest
from candidate_service import CandidateService

class CandidateServiceTests(unittest.TestCase):
    def test_stored_identity_pagination_and_blocked_reasons_remain_linked(self):
        events=[dict(event_id=str(i),symbol='TEST',setup='initial_breakout',available_at=1000+i,
            entry_reference='10',proposed_stop='9',capture_sha256='a'*64) for i in range(30)]
        report=dict(events=events,reviews=[dict(allocation=dict(reviews=[dict(event_id=e['event_id'],
            state='wait_for_evidence',reasons=['missing_execution_evidence'],rank=None,quantity=0) for e in events]))],
            setup_counts={'initial_breakout':30},decision_states={},coverage=[],spec_sha256='b'*64,limitations=['Historical diagnostic'])
        class Store:
            def call(self,op,p):return dict(packed_report=pack(report),sha256=digest(report))
        service=CandidateService(Store());first=service.latest(0);second=service.latest(1)
        self.assertEqual(len(first['rows']),25);self.assertEqual(len(second['rows']),5)
        self.assertEqual(first['blocking_reasons'],{'missing_execution_evidence':30})
        self.assertFalse(first['recommendation_qualified'])
        class Corrupt:
            def call(self,op,p):return dict(packed_report=pack(report),sha256='c'*64)
        self.assertEqual(CandidateService(Corrupt()).latest()['status'],'unavailable')
        with self.assertRaises(ValueError):service.latest(-1)
