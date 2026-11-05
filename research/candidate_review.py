"""Connect exact setup terms, evidence and shared paper capital without model authority."""
from acquisition_funnel import plan_acquisitions
from setup_detection import assess_remaining_opportunity,fingerprint
from replay import DataError


def review_candidates(events,quotes,targets,evidence_groups,liquidity,account,
                      opportunity_policy,allocation_policy,now):
    candidates=[];seen=set()
    for event in events:
        identity=event['event_id']
        if identity in seen:raise DataError('Duplicate setup identity')
        seen.add(identity)
        assessment=assess_remaining_opportunity(event,quotes.get(identity),targets.get(identity),now,opportunity_policy)
        cap=liquidity.get(identity,{})
        candidates.append(dict(event=event,assessment=assessment,
            evidence_groups=evidence_groups.get(identity,{}),
            maximum_quantity_from_liquidity=cap.get('maximum_quantity'),
            liquidity_available_at=cap.get('available_at')))
    if account is None:
        reviews=[dict(event_id=c['event']['event_id'],symbol=c['event']['symbol'],
            setup=c['event']['setup'],assessment=c['assessment'],rank=None,quantity=0,
            state='wait_for_evidence',reasons=list(c['assessment']['reasons'])+['reconciled_paper_capital_required'])
            for c in candidates]
        allocation=dict(status='paper_capital_unavailable',reviews=reviews,comparisons=[],orders_submitted=0)
    else:allocation=plan_acquisitions(candidates,account,allocation_policy,now)
    return dict(version='candidate-review-v1',assessed_at=now,input_sha256=fingerprint(dict(
        events=events,quotes=quotes,targets=targets,evidence_groups=evidence_groups,liquidity=liquidity,account=account)),
        assessments=[c['assessment'] for c in candidates],allocation=allocation,
        qualification='conditional_research_only',recommendation_qualified=False,orders_submitted=0)
