import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { decodeReply, startBenchmark, reviewReport } from './xfms_runner.mjs';

test('a dropped task disqualifies the service winner despite a perfect partial score', () => {
  const report = { order: ['partial', 'complete'],
    dropped: [{ model: 'partial', task: 't4', error: 'empty answer' }],
    each_model_on_each_requirement: {
      partial: { grounding: 'passed 5 of 5 tasks' },
      complete: { grounding: 'passed 6 of 6 tasks' } } };
  assert.deepEqual(reviewReport(report, 6, ['grounding']).eligible, ['complete']);
  assert.equal(reviewReport(report, 6, ['grounding']).recommended, 'complete');
  assert.equal(reviewReport(report, 6, ['missing check']).recommended, null);
});

test('SSE notifications do not hide the final report', () => {
  const raw = 'event: message\r\ndata: {"method":"ping"}\r\n\r\n'
    + 'data: {"result":{"structuredContent":{"spent_usd":0.01}}}\r\n\r\n';
  assert.equal(decodeReply(raw).spent_usd, 0.01);
});

test('detached completion saves the report after the start call returns', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'xfms-runner-'));
  let finish;
  let calls = 0;
  const args = { endpoint: 'https://xfms.xpansion.dev/mcp/?key=test',
    apiKey: 'test-only', request: { session: 'test', tasks: [{ text: 'case' }] },
    offer: { offer: 'test-offer', at_most_usd: 1.1 }, directory,
    reservedUsd: 0.4, combinedLimitUsd: 1.53,
    fetchImpl: () => { calls++; return new Promise(resolve => { finish = resolve; }); } };
  try {
    const run = await startBenchmark(args);
    assert.equal((await run.status()).status, 'running');
    finish(new Response(JSON.stringify({ result: { structuredContent: { spent_usd: 0.1 } } })));
    await run.completion;
    assert.equal((await run.status()).status, 'completed');
    assert.equal((await run.status()).spent_usd, 0.1);
    assert.ok(JSON.parse(await readFile(run.resultFile, 'utf8')).raw);
    assert.equal(calls, 1);
    await assert.rejects(startBenchmark({ ...args, reservedUsd: 1 }), /budget/);
    assert.equal(calls, 1);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test('uncertain transport failure records unknown outcome without retry', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'xfms-failure-'));
  let calls = 0;
  try {
    const run = await startBenchmark({
      endpoint: 'https://xfms.xpansion.dev/mcp/', apiKey: 'test-only',
      request: { session: 'test', tasks: [{ text: 'case' }] },
      offer: { offer: 'test-offer', at_most_usd: 0.1 }, directory,
      reservedUsd: 0, combinedLimitUsd: 0.1,
      fetchImpl: async () => { calls++; throw Error('simulated connection loss'); } });
    await run.completion;
    assert.equal((await run.status()).status, 'outcome_unknown_do_not_retry');
    assert.equal(calls, 1);
  } finally { await rm(directory, { recursive: true, force: true }); }
});
