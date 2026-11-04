"""Predeclared decision graph and ordered outcome comparisons for A20-A25/A49.

This records research relationships; it neither authenticates a real person nor
submits, amends or cancels an order. A favorable comparison is not a causal proof
or permission to change a strategy, preference or risk rule.
"""
from dataclasses import dataclass,asdict
from decimal import Decimal as D
import hashlib
import json

from replay import DataError


DECISIONS={
 'discovery':('observe','track_only','reject_evidence'),
 'entry_review':('enter','wait','modify','decline','no_response','expired'),
 'sizing':('retain','reduce','modify'),
 'stop_review':('retain','tighten','propose_widen','no_response'),
 'addition_review':('add','retain','decline','no_response'),
 'partial_exit_review':('take_partial','retain','decline','no_response'),
 'overnight_review':('hold','reduce','exit','no_response'),
 'exit_review':('exit','retain','modify','decline','no_response'),
 'execution':('submitted','acknowledged','partial_fill','filled','rejected','unknown','reconciled'),
 'feedback':('reason_given','other','no_feedback'),
 'preference_change':('propose','modify','approve','deny','no_response'),
 'strategy_change':('propose','test','validate','approve','deny','retire'),
 'portfolio_risk':('allow_entry','pause_new_entries','retain_protection'),
}


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False,default=str)


def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    opportunity_id: str
    parent_ids: tuple
    kind: str
    action: str
    decided_at: int
    evidence_at: int
    terms_json: str
    evidence_json: str
    policy_version: str
    mode: str
    previous_hash: str
    record_hash: str


class DecisionGraph:
    """Immutable records with explicit relationships, no implicit operational authority."""
    def __init__(self):self._records={};self._ordered=[]

    @property
    def records(self):return tuple(self._ordered)

    def record(self,opportunity_id,parent_ids,kind,action,decided_at,evidence_at,terms,evidence,
               policy_version,mode='counterfactual'):
        if not opportunity_id or kind not in DECISIONS or action not in DECISIONS[kind]:
            raise DataError('Known opportunity, decision kind and action required')
        if mode not in ('counterfactual','paper_record','observed_record'):
            raise DataError('Explicit evidence mode required')
        if type(decided_at) is not int or type(evidence_at) is not int or evidence_at>decided_at:
            raise DataError('Decision cannot use future evidence')
        if not policy_version or not isinstance(terms,dict) or not isinstance(evidence,dict):
            raise DataError('Versioned exact terms/evidence required')
        if not evidence.get('source_ids'):
            raise DataError('Decision evidence needs source references')
        parent_ids=tuple(parent_ids)
        for key in parent_ids:
            parent=self._records.get(key)
            if parent is None or parent.opportunity_id!=opportunity_id or parent.decided_at>decided_at:
                raise DataError('Decision parent missing, from another opportunity, or in the future')
        if kind!='discovery' and not parent_ids:
            raise DataError('Non-discovery decision must connect to its preceding evidence')
        payload=dict(opportunity_id=opportunity_id,parent_ids=parent_ids,kind=kind,action=action,
                     decided_at=decided_at,evidence_at=evidence_at,terms=terms,evidence=evidence,
                     policy_version=policy_version,mode=mode)
        identity=digest(payload)
        if identity in self._records:return self._records[identity]
        previous=self._ordered[-1].record_hash if self._ordered else ''
        record=DecisionRecord(identity,opportunity_id,parent_ids,kind,action,decided_at,evidence_at,
                              canonical(terms),canonical(evidence),policy_version,mode,previous,
                              digest([previous,payload]))
        self._records[identity]=record;self._ordered.append(record)
        return record


@dataclass(frozen=True)
class ComparisonPlan:
    opportunity_id: str
    declared_at: int
    first_evaluated_at: int
    currency: str
    common_capital_basis: str
    original_strategy_version: str
    management_strategy_version: str
    declaration_source_sha256: str

    def __post_init__(self):
        if self.declared_at>=self.first_evaluated_at or not all((self.opportunity_id,self.currency,
                self.common_capital_basis,self.original_strategy_version,self.management_strategy_version,
                self.declaration_source_sha256)):
            raise DataError('Comparison assumptions must be declared before evaluated outcomes')


def compare_decision_paths(plan,outcomes,user_choice,graph):
    """Ordered, conditional P&L differences, not independent causal effects.

    Each path must share the opportunity, currency, evaluation interval and stated
    capital convention. Keep modeled comparisons distinct from observed trading.
    Censored results block arithmetic; a skipped recommendation is not a loss.
    """
    paths=('recommendation_baseline','decision_timing_terms','execution_effects','management_effects')
    result=dict(opportunity_id=plan.opportunity_id,user_choice=user_choice,
                status='insufficient_comparison_evidence',components={},
                interpretation='ordered_conditional_differences_not_causal_proof',
                model_update_authorized=False,preference_update_authorized=False)
    if user_choice in ('decline','no_response','expired','track_only'):
        result.update(status='unexecuted_recommendation_separate_hypothetical_tracking',
                      actual_trade_pnl=None,inferred_preference=None)
        return result
    if user_choice not in ('enter','modify_then_enter'):
        raise DataError('Unknown entry decision')
    selected=[]
    records={r.decision_id:r for r in graph.records}
    plan_hash=digest(asdict(plan))
    for path in paths:
        row=outcomes.get(path)
        if row is None or row.get('status')=='censored' or row.get('net_pnl') is None:
            return result
        if (row.get('opportunity_id')!=plan.opportunity_id or row.get('currency')!=plan.currency or
                row.get('capital_basis')!=plan.common_capital_basis or
                row.get('available_at',0)<plan.first_evaluated_at):
            raise DataError('Outcome does not match predeclared comparison')
        decision=records.get(row.get('decision_id'))
        expected_version=plan.management_strategy_version if path=='management_effects' else plan.original_strategy_version
        if (decision is None or decision.opportunity_id!=plan.opportunity_id or
                row.get('comparison_plan_sha256')!=plan_hash or row.get('strategy_version')!=expected_version):
            raise DataError('Outcome is detached from its decision graph or strategy version')
        selected.append(row)
    if len({(r.get('evaluation_start'),r.get('evaluation_end')) for r in selected})!=1:
        raise DataError('Comparison intervals differ')
    if any(type(r.get('evaluation_start')) is not int or type(r.get('evaluation_end')) is not int or
           not plan.first_evaluated_at<=r['evaluation_start']<r['evaluation_end']<=r.get('available_at',0)
           for r in selected):
        raise DataError('Outcome interval or evidence availability invalid')
    if any(r.get('evidence_tier') not in ('modeled','observed') for r in selected):
        return result
    values=[D(str(r['net_pnl'])) for r in selected]
    if not all(v.is_finite() for v in values):raise DataError('Nonfinite P&L')
    result.update(status='conditional_comparison_available',
                  baseline_pnl=str(values[0]),final_path_pnl=str(values[-1]),
                  evidence_tiers={path:row['evidence_tier'] for path,row in zip(paths,selected)},
                  components={path:str(b-a) for path,a,b in zip(paths[1:],values,values[1:])},
                  total_difference=str(values[-1]-values[0]))
    return result
