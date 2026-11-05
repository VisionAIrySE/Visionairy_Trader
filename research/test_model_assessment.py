import copy
import json
import unittest
from model_assessment import ModelAssessment, AssessmentError, validate_claims, digest, VERSION


class Store:
    def __init__(self):self.jobs={};self.calls={};self.operations=[]
    def call(self, op, p):
        self.operations.append(op)
        if op=='create':
            key=p['request_hash']
            if key in self.jobs:return dict(self.jobs[key],created=False)
            self.jobs[key]={'id':key,'status':'running','checkpoint':{}}
            return dict(self.jobs[key],created=True)
        if op=='reserve':self.calls[p['id']]=dict(p,status='reserved');return {'reserved':True}
        if op=='finish_call':self.calls[p['id']]=copy.deepcopy(p);return {'saved':True}
        if op=='save':
            self.jobs[p['id']].update(status=p['status'],checkpoint={'result':p['result']})
            return {'saved':True}
        raise AssertionError(op)


def context():
    return dict(mode='ghost',evidence_origin='synthetic_acceptance_fixture',as_of=100,
        options=[{'id':'paper-a','entry_cash':'20','planned_risk':'1'}],
        baseline={'choice':'paper-a'},orders_submitted=0,sources=[
            dict(id='s1',text='A fictional issuer says approval is pending.',available_at=90,document_version='v1'),
            dict(id='future',text='FUTURE SECRET: approval confirmed',available_at=110,document_version='v2')])


def reply(payload, text=None, choice=None):
    body=json.loads(payload['messages'][1]['content'])
    claim=dict(kind='fact',text=text or 'The supplied notice says approval is pending.',support='limited',
        citations=[{'source_id':'s1','quote':'approval is pending'}])
    result={'claims':[claim],'missing_information':['No independent evidence of profitable trading.']}
    if 'options' in body:result['choice']=choice or 'paper-a'
    return dict(id='generation-test',model=payload['model'],provider='fixture-provider',
        choices=[{'finish_reason':'stop','message':{'content':json.dumps(result)}}],usage={'cost':0.0001})


class AssessmentTests(unittest.TestCase):
    def test_joined_flow_preserves_engine_numbers_filters_future_and_reuses_persisted_result(self):
        store=Store();requests=[];original=context()
        def transport(url,headers,payload,**kwargs):
            requests.append(payload)
            self.assertNotIn('FUTURE SECRET',json.dumps(payload))
            return reply(payload)
        report=ModelAssessment(store,'private-test-key',transport).run(original)
        self.assertEqual(report['selected_option'],original['options'][0])
        self.assertEqual(report['orders_submitted'],0)
        self.assertEqual(len(requests),2)
        self.assertTrue(report['baseline_agreement'])
        self.assertEqual(report['incremental_decision_value'],'not_established_by_this_fixture')
        self.assertEqual(report['reported_cost_usd'],'0.0002')
        self.assertEqual(len(store.calls),2)
        self.assertEqual(original,context())
        cached=ModelAssessment(store,'private-test-key',transport).run(context())
        self.assertEqual(cached,report);self.assertEqual(len(requests),2)

    def test_unqualified_primary_substitution_falls_back_only_to_qualified_model_and_retains_cost(self):
        store=Store()
        def transport(url,headers,payload,**kwargs):
            result=reply(payload)
            if payload['model'].startswith('nvidia/'):
                result['model']='unqualified/model'
            return result
        report=ModelAssessment(store,'test',transport).run(context())
        self.assertEqual(len(report['model_calls']),3)
        self.assertEqual(report['model_calls'][-1]['model'],'inclusionai/ling-3.1-flash')
        self.assertIsNotNone(report['model_calls'][-1]['fallback_reason'])
        self.assertEqual(report['reported_cost_usd'],'0.0003')
        self.assertEqual(report['model_calls'][1]['status'],'failed')

    def test_unknown_transport_outcome_is_reserved_retained_and_not_replayed(self):
        store=Store();calls=[]
        def transport(*args,**kwargs):calls.append(1);raise TimeoutError('secret must not appear in output')
        with self.assertRaises(AssessmentError):ModelAssessment(store,'test',transport).run(context())
        receipt=next(iter(store.calls.values()))
        self.assertEqual(receipt['status'],'unknown');self.assertIsNone(receipt['cost_usd'])
        with self.assertRaises(AssessmentError):ModelAssessment(store,'test',transport).run(context())
        self.assertEqual(len(calls),1)
        self.assertNotIn('secret',json.dumps(store.calls))

    def test_truncated_paid_news_answer_cannot_advance_to_research(self):
        store=Store();calls=[]
        def transport(url,headers,payload,**kwargs):
            calls.append(payload)
            result=reply(payload)
            result['choices'][0]['finish_reason']='length'
            return result
        with self.assertRaises(AssessmentError):ModelAssessment(store,'test',transport).run(context())
        self.assertEqual(len(calls),1)
        receipt=next(iter(store.calls.values()))
        self.assertEqual(receipt['error_code'],'Incomplete model response')
        self.assertEqual(receipt['cost_usd'],'0.0001')
        self.assertEqual(receipt['runtime_profile']['reasoning'],{'enabled':False})

    def test_invented_citations_unknown_options_and_monetary_overrides_fail(self):
        good=reply({'messages':[{}, {'content':json.dumps(context())}],'model':'test'})
        result=json.loads(good['choices'][0]['message']['content'])
        for change in ('citation','choice','override','fact_without_source'):
            bad=copy.deepcopy(result)
            if change=='citation':bad['claims'][0]['citations'][0]['quote']='approval confirmed'
            if change=='choice':bad['choice']='unauthorized-order'
            if change=='override':bad['quantity']=999
            if change=='fact_without_source':bad['claims'][0]['citations']=[]
            with self.assertRaises(AssessmentError):validate_claims(bad,context()['sources'][:1],choices=['cash','paper-a'])


if __name__=='__main__':unittest.main()
