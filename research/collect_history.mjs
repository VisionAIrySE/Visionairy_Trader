// Read-only private collection through the existing authenticated service.
// Broker credentials never leave the server. Generated data stays under data/.
import * as fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';

const service = 'https://visionairy-trader-research.onrender.com';
const hash = text => createHash('sha256').update(text).digest('hex');

export async function collect(root, limit = 6) {
  if (!Number.isInteger(limit) || limit < 1 || limit > 8) throw Error('Bounded batch required');
  const folder = path.join(root, 'data', 'history_collection');
  const plan = JSON.parse(await fs.readFile(path.join(folder, 'plan.json'), 'utf8'));
  const login = JSON.parse(await fs.readFile(path.join(root, 'data', 'dashboard_login.json'), 'utf8'));
  const authorization = 'Basic ' + Buffer.from(login.username + ':' + login.password).toString('base64');
  const results = [];
  for (const request of plan.requests) {
    if (request.status !== 'pending') continue;
    const query = request.query;
    const identity = hash(JSON.stringify({plan: plan.plan_sha256, query}));
    const target = path.join(folder, identity + '.json');
    try { await fs.access(target); continue; } catch (e) { if (e.code !== 'ENOENT') throw e; }
    const retrievedAt = new Date().toISOString();
    let capture;
    try {
      const response = await fetch(service + '/api/history?' + new URLSearchParams(query), {
        headers: {Authorization: authorization}, redirect: 'error', signal: AbortSignal.timeout(8000)
      });
      const text = await response.text();
      if (Buffer.byteLength(text) > 4 * 1024 * 1024) throw Error('Oversized capture');
      let body;
      try { body = JSON.parse(text); } catch { body = {status: 'invalid_service_response'}; }
      capture = {plan_sha256: plan.plan_sha256, query, retrieved_at: retrievedAt,
        http_status: response.status, response_sha256: hash(text), response: body};
    } catch {
      capture = {plan_sha256: plan.plan_sha256, query, retrieved_at: retrievedAt,
        http_status: null, response: {status: 'collection_network_failure'}};
    }
    // Transient failures remain distinct attempts; no silent retry in this batch.
    const transient = capture.http_status === 429 || capture.http_status === null;
    const output = transient ? target.replace('.json', '.attempt-' + Date.now() + '.json') : target;
    await fs.writeFile(output, JSON.stringify(capture, null, 2), {flag: 'wx'});
    results.push({symbol: query.symbol, http_status: capture.http_status,
      status: capture.response.status, bars: capture.response.bars ?? null});
    if (transient || [401, 403].includes(capture.http_status) || results.length >= limit) break;
    await new Promise(resolve => setTimeout(resolve, 2200));
  }
  return results;
}
