"""Private bounded view of retained detection diagnostics, never current buy alerts."""
from collections import Counter
from market_monitor import unpack,digest
from model_assessment import HostedAssessmentStore

class CandidateService:
    def __init__(self,store=None):self.store=store
    def latest(self,page=0):
        if type(page) is not int or not 0<=page<=10000:raise ValueError('Bounded candidate page required')
        try:
            if self.store is None:self.store=HostedAssessmentStore()
            saved=self.store.call('candidate_snapshot_get',{})
            if not saved.get('packed_report'):return {'status':'not_started','orders_submitted':0}
            report=unpack(saved['packed_report'])
            if digest(report)!=saved.get('sha256'):raise ValueError('Stored candidate report identity mismatch')
            events=report['events'];reviews={r['event_id']:r for group in report['reviews'] for r in group['allocation']['reviews']}
            rows=[]
            for event in events[page*25:(page+1)*25]:
                review=reviews[event['event_id']]
                rows.append(dict(symbol=event['symbol'],setup=event['setup'],available_at=event['available_at'],
                    entry_reference=event['entry_reference'],proposed_stop=event['proposed_stop'],
                    state=review['state'],reasons=review['reasons'],rank=review['rank'],quantity=review['quantity'],
                    event_id=event['event_id'],source_sha256=event['capture_sha256']))
            return dict(status='historical_detection_diagnostic',page=page,page_size=25,total=len(events),
                setup_counts=report['setup_counts'],decision_states=report['decision_states'],
                coverage=report['coverage'],rows=rows,spec_sha256=report['spec_sha256'],
                blocking_reasons=dict(Counter(reason for r in reviews.values() for reason in r['reasons'])),
                limitations=report['limitations'],recommendation_qualified=False,orders_submitted=0,
                source_range=dict(first=min((e['available_at'] for e in events),default=None),
                    last=max((e['available_at'] for e in events),default=None)))
        except Exception:return {'status':'unavailable','orders_submitted':0,'recommendation_qualified':False}
