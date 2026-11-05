// Start from a persistent Node host, then poll status() in separate short calls.
// An open connection is not evidence of server-side progress.
import { mkdir, readFile, writeFile, rename } from 'node:fs/promises';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';

export function decodeReply(raw) {
  const messages = raw.trimStart().startsWith('{')
    ? [JSON.parse(raw)]
    : raw.split(/\r?\n\r?\n/).flatMap(event => {
      const data = event.split(/\r?\n/).filter(line => line.startsWith('data:'))
        .map(line => line.slice(5).trimStart()).join('\n');
      return data && data !== '[DONE]' ? [JSON.parse(data)] : [];
    });
  const reply = messages.findLast(message => message.result || message.error);
  if (!reply) throw new Error('No completed RPC response');
  if (reply.error) throw new Error('XFMS returned an RPC error');
  if (reply.result.isError) throw new Error('XFMS returned a tool error');
  return reply.result.structuredContent ?? JSON.parse(
    reply.result.content?.find(block => block.type === 'text')?.text ?? '{}');
}

async function atomicJson(path, value) {
  const temp = `${path}.${randomUUID()}.tmp`;
  await writeFile(temp, JSON.stringify(value, null, 2));
  await rename(temp, path);
}

export async function startBenchmark({ endpoint, apiKey, request, offer,
  directory, reservedUsd, combinedLimitUsd, timeoutMs = 1500000,
  fetchImpl = fetch }) {
  const url = new URL(endpoint);
  if (url.origin !== 'https://xfms.xpansion.dev' || url.pathname !== '/mcp/')
    throw new Error('Unapproved XFMS origin');
  if (!apiKey || !offer.offer || !request.session || !request.tasks?.length)
    throw new Error('Missing benchmark authorization inputs');
  if (![reservedUsd, combinedLimitUsd, offer.at_most_usd].every(Number.isFinite)
      || reservedUsd < 0 || offer.at_most_usd < 0
      || reservedUsd + offer.at_most_usd > combinedLimitUsd)
    throw new Error('Offer exceeds remaining approved budget');
  await mkdir(directory, { recursive: true });
  const id = `xfms_${randomUUID()}`;
  const stateFile = join(directory, `${id}_state.json`);
  const resultFile = join(directory, `${id}_result.json`);
  const state = { id, status: 'running', started_at: new Date().toISOString(),
    approved_max_usd: offer.at_most_usd, reserved_usd: reservedUsd,
    combined_limit_usd: combinedLimitUsd };
  await atomicJson(stateFile, state);
  // Return the handle immediately; never await this completion inside a long tool call.
  const completion = (async () => {
    try {
      const response = await fetchImpl(endpoint, { method: 'POST', redirect: 'error',
        headers: { 'Content-Type': 'application/json',
          Accept: 'application/json, text/event-stream', 'X-OpenRouter-Key': apiKey },
        body: JSON.stringify({ jsonrpc: '2.0', id, method: 'tools/call',
          params: { name: 'benchmark', arguments: { ...request, offer: offer.offer, go: true } } }),
        signal: AbortSignal.timeout(timeoutMs) });
      const raw = await response.text();
      // Save the raw reply before decoding, so malformed reports remain recoverable.
      await atomicJson(resultFile, { http_status: response.status, raw });
      if (!response.ok) throw new Error('XFMS HTTP error');
      const report = decodeReply(raw);
      state.status = report.error ? 'service_error_review_receipt' : 'completed';
      state.spent_usd = report.spent_usd ?? null;
      state.completed_at = new Date().toISOString();
    } catch {
      // Never retry automatically: network failure does not mean zero spend.
      state.status = 'outcome_unknown_do_not_retry';
    }
    await atomicJson(stateFile, state);
    return state;
  })();
  return { id, stateFile, resultFile, completion,
    async status() {
      const saved = JSON.parse(await readFile(stateFile, 'utf8'));
      return { ...saved, elapsed_seconds: Math.floor(
        (Date.now() - Date.parse(saved.started_at)) / 1000),
        server_progress: 'not exposed by XFMS' };
    } };
}
