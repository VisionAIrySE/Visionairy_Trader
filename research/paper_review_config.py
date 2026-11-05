"""Owner-selected comparison budget; no funding, fills or persistent trade ledger."""
from decimal import Decimal as D
import re
import time
from market_monitor import digest
from model_assessment import HostedAssessmentStore
from replay import DataError


def validate_config(payload):
    if (not isinstance(payload,dict) or set(payload)!={'cash','target_multiple'}
            or not isinstance(payload['cash'],str) or not re.fullmatch(r'[0-9]{1,7}(?:\.[0-9]{1,2})?',payload['cash'])
            or payload['target_multiple'] not in ('2','3')):
        raise DataError('Explicit positive comparison cash and a supported target scenario required')
    cash=D(payload['cash'])
    if not D('.01')<=cash<=D('1000000'):raise DataError('Comparison cash must be between 0.01 and 1000000 USD')
    return dict(cash=format(cash,'.2f'),target_multiple=payload['target_multiple'])


class PaperReviewConfig:
    def __init__(self,store=None,now=time.time):self.store=store;self.now=now
    def _store(self):
        if self.store is None:self.store=HostedAssessmentStore()
        return self.store
    def read(self):
        try:
            config=self._store().call('paper_review_config_get',{})
            if config.get('version')=='paper-review-v1':comparison_account(config,int(self.now()))
            return config
        except Exception:return dict(status='unavailable',orders_submitted=0)
    def save(self,payload):
        values=validate_config(payload)
        config=dict(values,version='paper-review-v1',mode='comparison_only',updated_at=int(self.now()),
            target_support='unvalidated_geometry_not_forecast',orders_submitted=0)
        config['sha256']=digest(config)
        saved=self._store().call('paper_review_config_put',config)
        if saved.get('saved') is not True:raise DataError('Comparison setting was not confirmed saved')
        return config


def comparison_account(config,now):
    if not config or config.get('version')!='paper-review-v1' or config.get('mode')!='comparison_only':return None
    expected={k:v for k,v in config.items() if k!='sha256'}
    if digest(expected)!=config.get('sha256'):raise DataError('Comparison configuration identity mismatch')
    checked=validate_config({k:config[k] for k in ('cash','target_multiple')})
    if type(config.get('updated_at')) is not int or config['updated_at']>now:raise DataError('Future comparison configuration')
    return dict(mode='counterfactual',equity=checked['cash'],settled_cash=checked['cash'],total_open_risk='0',
        trade_risk_by_symbol={},open_symbols=[],new_entries_allowed=True,observed_at=now,
        capital_basis='owner_selected_empty_comparison_scenario_not_broker_or_active_ledger',
        config_sha256=config['sha256'])
