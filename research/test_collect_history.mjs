import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {collect,networkFailure,retryable} from './collect_history.mjs';

async function fixture(t) {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'trader-collection-'));
  t.after(()=>fs.rm(root,{recursive:true,force:true}));
  const folder=path.join(root,'data','history_collection');await fs.mkdir(folder,{recursive:true});
  await fs.writeFile(path.join(root,'data','dashboard_login.json'),JSON.stringify({username:'test',password:'test-secret'}));
  await fs.writeFile(path.join(folder,'plan.json'),JSON.stringify({plan_sha256:'test-plan',requests:[{
    status:'pending',query:{symbol:'TEST',interval:'5min',start:'2026-10-01 09:30',end:'2026-11-03 16:00'}}]}));
  return {root,folder};
}
function response(status,body) {return {status,text:async()=>JSON.stringify(body)};}

test('diagnostics distinguish DNS and timeouts without echoing private messages',()=>{
  assert.equal(networkFailure({cause:{code:'ENOTFOUND'},message:'secret'}),'dns_failure');
  assert.equal(networkFailure({name:'TimeoutError'}),'timeout');
  assert.equal(networkFailure({cause:{code:'ECONNRESET'}}),'connection_failure');
  assert.equal(networkFailure(Error('secret')),'unclassified_network_failure');
  assert.equal(retryable({http_status:502,response:{retryable:false}}),false);
});

test('permanent upstream errors wrapped as 502 are not retried',async t=>{
  const {root}=await fixture(t);let calls=0;
  const options={sleep:async()=>{},fetchFn:async()=>{calls++;return response(502,
    {status:'unavailable',provider_http_status:400,retryable:false});}};
  await collect(root,6,options);await collect(root,6,options);assert.equal(calls,1);
});

test('temporary failure retries and preserves failed and successful attempts',async t=>{
  const {root,folder}=await fixture(t);let calls=0;const waits=[];
  const opts={sleep:async ms=>waits.push(ms),fetchFn:async(url,options)=>{
    assert.ok(url.startsWith('https://visionairy-trader-research.onrender.com/api/history?'));
    assert.equal(options.redirect,'error');
    return ++calls===1?response(502,{status:'unavailable'}):response(200,{status:'observed',bars:3});}};
  const out=await collect(root,6,opts);assert.equal(out.length,2);assert.equal(calls,2);
  const files=(await fs.readdir(folder)).filter(p=>p!=='plan.json');assert.equal(files.length,2);
  const bytes=await Promise.all(files.map(p=>fs.readFile(path.join(folder,p),'utf8')));
  assert.equal((await collect(root,6,opts)).length,0);assert.equal(calls,2);
  assert.deepEqual(bytes,await Promise.all(files.map(p=>fs.readFile(path.join(folder,p),'utf8'))));
  assert.ok(waits.includes(2000));
});
test('network failures stop at three total attempts across resumes',async t=>{
  const {root}=await fixture(t);let calls=0;
  const opts={sleep:async()=>{},fetchFn:async()=>{calls++;throw Error('private internals');}};
  assert.equal((await collect(root,1,opts)).length,1);
  const rest=await collect(root,6,opts);assert.equal(rest.length,2);assert.equal(rest.at(-1).retry_budget_exhausted,true);
  assert.equal((await collect(root,6,opts)).length,0);assert.equal(calls,3);
});
test('permission rejection is not hammered; throttling waits before retry',async t=>{
  const a=await fixture(t);let calls=0;
  await collect(a.root,6,{sleep:async()=>{},fetchFn:async()=>{calls++;return response(401,{status:'unavailable'});}});
  assert.equal(calls,1);
  const b=await fixture(t);const waits=[];calls=0;
  await collect(b.root,6,{sleep:async ms=>waits.push(ms),fetchFn:async()=>++calls===1?
    response(429,{status:'busy',retry_after_seconds:3}):response(200,{status:'no_bars_returned',bars:0})});
  assert.equal(calls,2);assert.ok(waits.includes(3000));
});
