from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from execution_plan import DEFAULT_PLAN,empty_state,fingerprint,render,status,validate,verify_receipt


class ExecutionPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan=json.loads(DEFAULT_PLAN.read_text(encoding='utf-8'))
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.artifact=self.root/'evidence.json'
        self.artifact.write_text('{"actual_findings":"test fixture"}',encoding='utf-8')
    def receipt(self,key):
        task=next(t for t in self.plan['tasks'] if t['id']==key)
        return dict(task_id=key,plan_sha256=fingerprint(self.plan),checks=[
            dict(criterion_id=c['id'],result='pass',finding='Synthetic controller acceptance fixture only',
                 artifact='evidence.json',sha256=hashlib.sha256(self.artifact.read_bytes()).hexdigest())
            for c in task['acceptance']])
    def test_scope_dependencies_and_generated_document_agree(self):
        self.assertEqual(49,len(validate(self.plan)))
        self.assertEqual(DEFAULT_PLAN.with_suffix('.md').read_text(encoding='utf-8'),render(self.plan))
        report=status(self.plan,empty_state(self.plan),self.root)
        self.assertEqual('R01',report['next_tasks'][0]['id'])
        self.assertFalse(report['live_order_authority']);self.assertFalse(report['operating_platform_ready'])
    def test_cycle_unknown_dependency_and_missing_scope_rejected(self):
        for kind in ('cycle','unknown','scope','hypothesis'):
            p=deepcopy(self.plan)
            if kind=='cycle':p['tasks'][0]['depends_on']=['R01']
            elif kind=='unknown':p['tasks'][0]['depends_on']=['MISSING']
            elif kind=='scope':p['requirements'].pop('A01')
            else:p['hypotheses'].pop('breakout')
            with self.assertRaises(ValueError):validate(p)
    def test_dependency_and_incomplete_receipt_cannot_complete_task(self):
        state=empty_state(self.plan)
        state['events']=[dict(task_id='T01',action='complete',receipt=self.receipt('T01'))]
        with self.assertRaisesRegex(ValueError,'before dependencies'):status(self.plan,state,self.root)
        receipt=self.receipt('R01');receipt['checks'].pop()
        with self.assertRaisesRegex(ValueError,'Every acceptance'):
            verify_receipt(self.plan['tasks'][0],receipt,self.plan,self.root)
    def test_changed_evidence_invalidates_prior_completion(self):
        state=empty_state(self.plan)
        state['events']=[dict(task_id='R01',action='complete',receipt=self.receipt('R01'))]
        self.assertEqual(['R01'],status(self.plan,state,self.root)['completed'])
        self.artifact.write_text('changed')
        with self.assertRaisesRegex(ValueError,'content changed'):status(self.plan,state,self.root)
    def test_explicit_block_allows_independent_work_and_resume(self):
        state=empty_state(self.plan);state['events']=[dict(task_id='R01',action='block',reason='Specific temporary provider outage')]
        report=status(self.plan,state,self.root)
        self.assertEqual('S01',report['next_tasks'][0]['id']);self.assertIn('R01',report['blocked'])
        state['events'].append(dict(task_id='R01',action='resume'))
        self.assertEqual('R01',status(self.plan,state,self.root)['next_tasks'][0]['id'])
    def test_receipt_cannot_grant_order_authority_or_reuse_other_plan(self):
        task=next(t for t in self.plan['tasks'] if t['id']=='B01')
        with self.assertRaisesRegex(ValueError,'Separate authorization'):
            verify_receipt(task,self.receipt('B01'),self.plan,self.root)
        receipt=self.receipt('R01');receipt['plan_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'exact plan'):
            verify_receipt(self.plan['tasks'][0],receipt,self.plan,self.root)


if __name__=='__main__':unittest.main()
