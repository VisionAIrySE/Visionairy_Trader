
-- Dataset, result and approval invariants.
create function trader.reject_mutation() returns trigger language plpgsql security invoker set search_path='' as $$
begin raise exception 'Immutable record: append a new version instead'; end $$;

create function trader.guard_dataset() returns trigger language plpgsql security invoker set search_path='' as $$
declare target_id uuid;
begin
 if tg_table_name='datasets' then
  if old.status='frozen' then raise exception 'Frozen dataset cannot change'; end if;
  return case when tg_op='DELETE' then old else new end;
 end if;
 target_id:=case when tg_op='DELETE' then old.dataset_id else new.dataset_id end;
 if exists(select 1 from trader.datasets where id=target_id and status='frozen') then
  raise exception 'Frozen dataset membership cannot change';
 end if;
 if tg_op='UPDATE' and exists(select 1 from trader.datasets where id=old.dataset_id and status='frozen') then
  raise exception 'Frozen dataset membership cannot change';
 end if;
 return case when tg_op='DELETE' then old else new end;
end $$;
create trigger frozen_dataset before update or delete on trader.datasets for each row execute function trader.guard_dataset();
create trigger frozen_membership before insert or update or delete on trader.dataset_sources for each row execute function trader.guard_dataset();

create function trader.guard_run() returns trigger language plpgsql security invoker set search_path='' as $$
declare target_id uuid; dataset_status text;
begin
 if tg_table_name='runs' then
  if tg_op in ('UPDATE','DELETE') and old.status='complete' then raise exception 'Completed run is immutable'; end if;
  if tg_op<>'DELETE' and new.status='complete' then
   select status into dataset_status from trader.datasets where id=new.dataset_id;
   if dataset_status<>'frozen' then raise exception 'Completion requires frozen data'; end if;
  end if;
  return case when tg_op='DELETE' then old else new end;
 end if;
 target_id:=case when tg_op='DELETE' then old.run_id else new.run_id end;
 if not exists(select 1 from trader.runs where id=target_id and status='writing') then
  raise exception 'Run evidence can only change during writing';
 end if;
 if tg_op='UPDATE' and not exists(select 1 from trader.runs where id=old.run_id and status='writing') then
  raise exception 'Run evidence can only change during writing';
 end if;
 return case when tg_op='DELETE' then old else new end;
end $$;
create trigger run_state before insert or update or delete on trader.runs for each row execute function trader.guard_run();
do $$
declare t text;
begin
 foreach t in array array['signals','outcomes','result_summaries','run_strategies','evaluation_splits'] loop
  execute format('create trigger frozen_run before insert or update or delete on trader.%I for each row execute function trader.guard_run()',t);
 end loop;
 foreach t in array array['sources','observations','source_observations','hypotheses','strategy_versions',
                         'execution_scenarios','document_versions','document_chunks','embedding_profiles','chunk_embeddings','audit_events','cash_ledger','simulated_fills','user_feedback','preference_versions'] loop
  execute format('create trigger immutable_record before update or delete on trader.%I for each row execute function trader.reject_mutation()',t);
 end loop;
end $$;

create function trader.guard_approval() returns trigger language plpgsql security invoker set search_path='' as $$
begin
 if tg_op='UPDATE' and old.status<>'pending' then raise exception 'Decisions are immutable; request new terms'; end if;
 new.payload_sha256:=encode(sha256(convert_to(new.payload::text,'UTF8')),'hex');
 if new.status='approved' and new.expires_at<now() then raise exception 'Expired approval'; end if;
 return new;
end $$;
create trigger approval_terms before insert or update on trader.approval_requests for each row execute function trader.guard_approval();

create function trader.guard_learning_transition() returns trigger language plpgsql security invoker set search_path='' as $$
begin
 if new.status='validated' and (tg_op='INSERT' or old.status is distinct from new.status) then
  if not exists(
   select 1 from trader.learning_evaluations e
   join trader.runs b on b.id=e.baseline_run_id
   join trader.runs c on c.id=e.candidate_run_id
   join trader.evaluation_splits s on s.id=e.split_id and s.run_id=c.id
   where e.proposal_id=new.id and e.result='pass' and e.sample_count>0
    and s.independent_data and b.status='complete' and c.status='complete'
    and b.purpose='validation' and c.purpose='validation' and b.dataset_id=c.dataset_id
    and exists(select 1 from trader.run_strategies rb where rb.run_id=b.id and rb.strategy_version_id=new.baseline_strategy_id)
    and exists(select 1 from trader.run_strategies rc where rc.run_id=c.id and rc.strategy_version_id=new.candidate_strategy_id)
  ) then raise exception 'Validation requires completed independent comparison and declared strategies'; end if;
 end if;
 if new.status='approved' and (tg_op='INSERT' or old.status is distinct from new.status) then
  if tg_op='INSERT' or old.status<>'validated' then raise exception 'Validate before approval'; end if;
  if not exists(
   select 1 from trader.approval_requests a join trader.strategy_versions v on v.id=new.candidate_strategy_id
   where a.proposal_id=new.id and a.status='approved' and a.decided_by is not null
    and a.expires_at>=now() and a.payload->>'strategy_version_id'=v.id::text
    and a.payload->>'spec_sha256'=v.spec_sha256
  ) then raise exception 'Approval must match exact candidate terms'; end if;
 end if;
 return new;
end $$;
create trigger learning_transition before insert or update on trader.learning_proposals
 for each row execute function trader.guard_learning_transition();

-- Bounded, point-in-time hybrid retrieval; exact vectors until a model-specific ANN index is qualified.
create function trader.search_evidence(
 p_query text, p_as_of timestamptz, p_limit integer default 10,
 p_embedding extensions.vector default null, p_profile uuid default null, p_allow_test boolean default false
) returns table(chunk_id uuid, document_version_id uuid, title text, content text,
                score double precision, source_uri text, available_at timestamptz, citation jsonb)
language plpgsql stable security invoker set search_path='' as $$
declare dim integer; model_from timestamptz; cutoff timestamptz; profile_purpose text;
begin
 if p_as_of is null or p_limit not between 1 and 50 or char_length(coalesce(p_query,''))>4000 then
  raise exception 'Invalid bounded retrieval request';
 end if;
 if (p_embedding is null)<>(p_profile is null) then raise exception 'Provide both embedding and profile'; end if;
 if p_profile is not null then
  select dimensions,available_from,training_cutoff,purpose into dim,model_from,cutoff,profile_purpose
    from trader.embedding_profiles where id=p_profile;
  if dim is null or dim<>extensions.vector_dims(p_embedding) then raise exception 'Embedding profile/dimension mismatch'; end if;
  if cutoff is null or cutoff>p_as_of or model_from>p_as_of then raise exception 'Model not qualified at requested cutoff'; end if;
  if profile_purpose='test_fixture' and not p_allow_test then raise exception 'Fixture vectors are not production evidence'; end if;
 end if;
 return query
 with eligible_versions as (
  select distinct on (v.document_id) v.*
  from trader.document_versions v
  where v.available_at<=p_as_of and v.first_seen_at<=p_as_of
    and (v.published_at is null or v.published_at<=p_as_of)
  order by v.document_id,v.available_at desc,v.first_seen_at desc,v.id
 ), eligible as not materialized (
  select c.*,v.available_at as version_available,d.title,d.source_uri
  from trader.document_chunks c
  join eligible_versions v on v.id=c.document_version_id
  join trader.documents d on d.id=v.document_id
 ), kw as (
  select c.id,row_number() over(order by ts_rank_cd(c.fts,websearch_to_tsquery('english',coalesce(p_query,''))) desc,c.id) as r
  from eligible c where c.fts@@websearch_to_tsquery('english',coalesce(p_query,''))
  order by r limit 100
 ), sem as (
  select c.id,row_number() over(order by e.embedding operator(extensions.<=>) p_embedding,c.id) as r
  from eligible c join trader.chunk_embeddings e on e.chunk_id=c.id
  where p_embedding is not null and e.profile_id=p_profile and e.source_content_sha256=c.content_sha256
  order by r limit 100
 ), fused as (
  select coalesce(kw.id,sem.id) as id,
   (coalesce(1.0/(60+kw.r),0)+coalesce(1.0/(60+sem.r),0))::double precision as rank_score
  from kw full join sem on kw.id=sem.id
 )
 select c.id,c.document_version_id,c.title,c.content,f.rank_score,c.source_uri,c.version_available,c.citation
 from fused f join eligible c on c.id=f.id order by f.rank_score desc,c.id limit p_limit;
end $$;

create function trader.claim_job(p_worker text,p_lease_seconds integer default 60)
returns setof trader.jobs language plpgsql security invoker set search_path='' as $$
begin
 if p_lease_seconds not between 10 and 600 or char_length(p_worker) not between 1 and 100 then
  raise exception 'Invalid lease';
 end if;
 return query
 with candidate as (
  select id from trader.jobs where
   (status='queued' and available_at<=now()) or (status='running' and lease_until<now())
  order by available_at,id for update skip locked limit 1
 )
 update trader.jobs j set status='running',lease_until=now()+make_interval(secs=>p_lease_seconds),
 attempts=j.attempts+1,checkpoint=j.checkpoint||jsonb_build_object('worker',p_worker)
 from candidate c where j.id=c.id returning j.*;
end $$;

create view trader.outcome_scorecard with (security_invoker=true) as
select o.run_id,o.scenario_id,
 count(*) as scenario_outcomes,count(distinct s.opportunity_id) as distinct_opportunities,
 count(*) filter(where o.status='modeled') as modeled_count,
 count(*) filter(where o.evidence_tier='censored') as censored_count,
 avg(o.net_pnl) filter(where o.status='modeled') as modeled_mean_net_pnl
from trader.outcomes o join trader.signals s on s.id=o.signal_id and s.run_id=o.run_id
group by o.run_id,o.scenario_id;

-- No anon/authenticated access to the private backend schema.
do $$
declare t record;
begin
 for t in select tablename from pg_tables where schemaname='trader' loop
  execute format('alter table trader.%I enable row level security',t.tablename);
  execute format('create policy backend_only on trader.%I to service_role using (true) with check (true)',t.tablename);
 end loop;
end $$;
revoke all on all tables in schema trader from public,anon,authenticated;
revoke all on all sequences in schema trader from public,anon,authenticated;
revoke all on all functions in schema trader from public,anon,authenticated;
grant select,insert,update,delete on all tables in schema trader to service_role;
grant usage,select on all sequences in schema trader to service_role;
grant execute on all functions in schema trader to service_role;
revoke update,delete on trader.audit_events from service_role;
alter default privileges in schema trader revoke all on tables from public,anon,authenticated;
alter default privileges in schema trader revoke all on sequences from public,anon,authenticated;

