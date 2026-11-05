// Read-only private collection through the existing authenticated service.
// Broker credentials never leave the server. Generated data stays under data/.
import * as fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {randomUUID} from 'node:crypto';

const service = 'https://visionairy-trader-research.onrender.com';
const hash = text => createHash('sha256').update(text).digest('hex');

export function retryable(capture) {
  if (typeof capture.response?.retryable === 'boolean') return capture.response.retryable;
  return capture.http_status === null || capture.http_status === 429 ||
    capture.http_status >= 500 || capture.response?.status === 'invalid_service_response';
}

export function networkFailure(error) {
  const code = error?.cause?.code ?? error?.code;
  if (['ENOTFOUND','EAI_AGAIN'].includes(code)) return 'dns_failure';
  if (['TimeoutError','AbortError'].includes(error?.name) ||
      ['ETIMEDOUT','UND_ERR_CONNECT_TIMEOUT'].includes(code)) return 'timeout';
  if (['ECONNRESET','ECONNREFUSED'].includes(code)) return 'connection_failure';
  return 'unclassified_network_failure';
}

export async function collect(root, limit = 6, {fetchFn = fetch,
  sleep = ms => new Promise(resolve => setTimeout(resolve, ms))} = {}) {
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
    const files = (await fs.readdir(folder)).filter(p => p === identity + '.json' ||
      p.startsWith(identity + '.attempt-') && p.endsWith('.json')).sort();
    const previous = await Promise.all(files.map(async p => JSON.parse(await fs.readFile(path.join(folder,p),'utf8'))));
    if (previous.some(p => p.http_status === 200 &&
        ['observed','no_bars_returned'].includes(p.response?.status))) continue;
    if (previous.length >= 3 || previous.some(p => !retryable(p))) continue;
    let attempts = previous.length;
    while (attempts < 3 && results.length < limit) {
    if (attempts) await sleep(Math.min(8000, 2000 * 2 ** (attempts - 1)));
    const retrievedAt = new Date().toISOString();
    let capture;
    try {
      const response = await fetchFn(service + '/api/history?' + new URLSearchParams(query), {
        headers: {Authorization: authorization}, redirect: 'error', signal: AbortSignal.timeout(8000)
      });
      const text = await response.text();
      if (Buffer.byteLength(text) > 4 * 1024 * 1024) throw Error('Oversized capture');
      let body;
      try { body = JSON.parse(text); } catch { body = {status: 'invalid_service_response'}; }
      capture = {plan_sha256: plan.plan_sha256, query, retrieved_at: retrievedAt,
        http_status: response.status, response_sha256: hash(text), response: body};
    } catch (error) {
      capture = {plan_sha256: plan.plan_sha256, query, retrieved_at: retrievedAt,
        http_status: null, response: {status: 'collection_network_failure',
          failure_category: networkFailure(error)}};
    }
    attempts += 1;
    capture.attempt_number = attempts;
    capture.retryable = retryable(capture);
    capture.retry_budget_exhausted = capture.retryable && attempts >= 3;
    const retryAfter = Number(capture.response?.retry_after_seconds);
    const output = previous.length === 0 && attempts === 1 ? target :
      target.replace('.json', '.attempt-' + String(attempts).padStart(4,'0') + '-' + randomUUID() + '.json');
    await fs.writeFile(output, JSON.stringify(capture, null, 2), {flag: 'wx'});
    results.push({symbol: query.symbol, http_status: capture.http_status,
      status: capture.response.status, bars: capture.response.bars ?? null,
      attempt: attempts, retry_budget_exhausted: capture.retry_budget_exhausted});
    if ([401,403].includes(capture.http_status)) return results;
    if (!capture.retryable) break;
    if (attempts < 3 && results.length < limit && Number.isFinite(retryAfter) && retryAfter > 0)
      await sleep(Math.min(30000,retryAfter*1000));
    }
    if (results.length >= limit) break;
    await sleep(2200);
  }
  return results;
}
