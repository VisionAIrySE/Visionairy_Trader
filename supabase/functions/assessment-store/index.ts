// Render-only assessment persistence. No browser access or generic SQL endpoint.
import postgres from 'npm:postgres@3.4.3';
const sql = postgres(Deno.env.get('SUPABASE_DB_URL')!, { prepare: false, max: 1, connect_timeout: 8 });
const AUTH_DIGEST = 'fbb167188197d3d08c8974a419a5a7ca75f470088c91d2e57cb8b49f6ed24791';
const KIND = 'ghost_model_assessment_v1';
const models = new Set(['inclusionai/ling-3.1-flash', 'nvidia/nemotron-3.5-lightning']);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const digest = async (s: string) => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)))).map(x => x.toString(16).padStart(2, '0')).join('');

Deno.serve(async req => {
  const token = (req.headers.get('authorization') || '').replace(/^Bearer /, '');
  if (req.method !== 'POST' || !token || await digest(token) !== AUTH_DIGEST)
    return Response.json({ error: 'unauthorized' }, { status: 401 });
  try {
    const raw = await req.text();
    if (raw.length > 700000) return Response.json({ error: 'too_large' }, { status: 413 });
    const { operation, payload: p } = JSON.parse(raw);
    if (!p || typeof p !== 'object') throw Error();
    const result = await sql.begin(async tx => {
      if (operation === 'create') {
        if (!/^[0-9a-f]{64}$/.test(p.request_hash) || p.context?.mode !== 'ghost'
            || p.context?.orders_submitted !== 0) throw Error();
        const rows = await tx`insert into trader.jobs(kind,idempotency_key,payload,status,attempts,checkpoint,lease_until)
          values (${KIND},${'ghost_assessment:' + p.request_hash},${tx.json(p)},'running',1,${tx.json({ stage: 'created' })},now()+interval '5 minutes')
          on conflict (idempotency_key) do nothing returning id,status,checkpoint`;
        if (rows.length) return { ...rows[0], created: true };
        const old = await tx`select id,status,checkpoint from trader.jobs where kind=${KIND}
          and idempotency_key=${'ghost_assessment:' + p.request_hash}`;
        return { ...old[0], created: false };
      }
      if (operation === 'latest') {
        await tx`update trader.jobs set status='failed',checkpoint=checkpoint || ${tx.json({
          stage: 'interrupted_needs_review', result: { status: 'unavailable',
            reason: 'Assessment exceeded its lease or was interrupted. Paid attempts remain reserved; no automatic replay.', orders_submitted: 0 }
        })} where kind=${KIND} and status='running' and lease_until<now()`;
        const rows = await tx`select id,status,checkpoint from trader.jobs where kind=${KIND} order by available_at desc limit 1`;
        return rows[0] || { status: 'not_started' };
      }
      const jobId = operation === 'reserve' || operation === 'finish_call' ? p.job_id : p.id;
      if (!uuid.test(jobId || '')) throw Error();
      const jobs = await tx`select id,status,checkpoint from trader.jobs where id=${jobId} and kind=${KIND} for update`;
      if (!jobs.length) throw Error();
      if (operation === 'get') return jobs[0];
      if (operation === 'save') {
        if (!['complete', 'failed'].includes(p.status) || jobs[0].status !== 'running') throw Error();
        await tx`update trader.jobs set status=${p.status},checkpoint=${tx.json({ stage: p.status, result: p.result })}
          where id=${jobId} and kind=${KIND}`;
        return { saved: true };
      }
      if (!uuid.test(p.id || '') || !models.has(p.model) || jobs[0].status !== 'running') throw Error();
      if (operation === 'reserve') {
        const reserve = Number(p.reserved_usd);
        if (!Number.isFinite(reserve) || reserve <= 0 || reserve > .03) throw Error();
        await tx`select pg_advisory_xact_lock(hashtext('visionairy_model_monthly_budget'))`;
        const spent = await tx`select coalesce(sum((a.metrics->>'reserved_usd')::numeric),0) as amount
          from trader.job_attempts a join trader.jobs j on j.id=a.job_id
          where j.kind=${KIND} and (a.metrics->>'cost_usd') is null`;
        const other = await tx`select coalesce(sum(amount),0) as amount from trader.cost_entries
          where incurred_at>=date_trunc('month',now())`;
        const jobSpent = await tx`select coalesce(sum(coalesce((metrics->>'cost_usd')::numeric,
          (metrics->>'reserved_usd')::numeric)),0) as amount from trader.job_attempts where job_id=${jobId}`;
        if (Number(spent[0].amount) + Number(other[0].amount) + reserve > 25
            || Number(jobSpent[0].amount) + reserve > .10) return { error: 'budget_exhausted' };
        await tx`insert into trader.job_attempts(id,job_id,started_at,state,metrics)
          values (${p.id},${jobId},now(),'reserved',${tx.json(p)})`;
        await tx`update trader.jobs set checkpoint=${tx.json({ stage: p.kind + '_running', model: p.model })}
          where id=${jobId}`;
        return { reserved: true };
      }
      if (operation === 'finish_call') {
        if (!['complete', 'failed', 'unknown'].includes(p.status)) throw Error();
        const old = await tx`select state,metrics from trader.job_attempts where id=${p.id} and job_id=${jobId} for update`;
        if (old.length !== 1 || old[0].state !== 'reserved') throw Error();
        // Preserve the original reservation even if a client sends a different value.
        p.reserved_usd = old[0].metrics.reserved_usd;
        if (p.cost_usd !== null && (!Number.isFinite(Number(p.cost_usd)) || Number(p.cost_usd) < 0)) throw Error();
        await tx`update trader.job_attempts set finished_at=now(),state=${p.status},error_code=${p.error_code || null},
          metrics=${tx.json(p)} where id=${p.id} and job_id=${jobId}`;
        if (p.cost_usd !== null) await tx`insert into trader.cost_entries(id,job_id,provider,category,incurred_at,amount,usage)
          values (${p.id},${jobId},${p.provider || 'openrouter'},'model_assessment',now(),${p.cost_usd},${tx.json(p.usage || {})})`;
        return { saved: true };
      }
      throw Error();
    });
    return Response.json(result, { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    return Response.json({ error: 'assessment_store_unavailable' }, { status: 503 });
  }
});
