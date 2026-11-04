-- Evidence-backed learning and immutable reviewed candidate identity.
create unique index signals_strategy_opportunity_once
 on trader.signals(run_id,strategy_version_id,opportunity_id);

create function trader.guard_learning_evaluation() returns trigger
language plpgsql security invoker set search_path='' as $$
declare p trader.learning_proposals%rowtype; s trader.evaluation_splits%rowtype;
 b trader.runs%rowtype; c trader.runs%rowtype; criteria jsonb; chosen uuid;
 matched integer; base_n integer; candidate_n integer; improvement numeric;
 minimum_n integer; minimum_gain numeric;
begin
 if new.result<>'pass' then return new; end if;
 select * into p from trader.learning_proposals where id=new.proposal_id;
 select * into s from trader.evaluation_splits where id=new.split_id;
 select * into b from trader.runs where id=new.baseline_run_id;
 select * into c from trader.runs where id=new.candidate_run_id;
 if s.run_id is distinct from c.id or not s.independent_data or b.status<>'complete' or c.status<>'complete'
    or b.purpose<>'validation' or c.purpose<>'validation' or b.dataset_id<>c.dataset_id then
  raise exception 'Passing evaluation needs frozen, independent, comparable validation runs';
 end if;
 if not exists(select 1 from trader.run_strategies where run_id=b.id and strategy_version_id=p.baseline_strategy_id)
    or not exists(select 1 from trader.run_strategies where run_id=c.id and strategy_version_id=p.candidate_strategy_id) then
  raise exception 'Evaluation strategy does not match proposal';
 end if;
 select parameters->'validation_criteria' into criteria from trader.strategy_versions where id=p.candidate_strategy_id;
 if criteria is null or not(criteria ? 'min_matched_opportunities') or not(criteria ? 'min_mean_net_improvement') then
  raise exception 'Predeclared validation criteria required';
 end if;
 minimum_n:=(criteria->>'min_matched_opportunities')::integer;
 minimum_gain:=(criteria->>'min_mean_net_improvement')::numeric;
 if minimum_n is null or minimum_gain is null or minimum_n<2 or minimum_gain<0 then
  raise exception 'Invalid validation criteria';
 end if;
 if criteria->>'scenario_id' is null then raise exception 'Predeclared scenario required'; end if;
 if new.metrics->>'scenario_id' is distinct from criteria->>'scenario_id' then
  raise exception 'Evaluation scenario must match predeclared criteria';
 end if;
 chosen:=(criteria->>'scenario_id')::uuid;
 with baseline as (
  select x.opportunity_id,o.net_pnl
  from trader.outcomes o join trader.signals x on x.id=o.signal_id and x.run_id=o.run_id
  where o.run_id=b.id and x.strategy_version_id=p.baseline_strategy_id and o.scenario_id=chosen
    and s.evaluation @> x.available_at and s.evaluation @> o.entry_at and s.evaluation @> o.exit_at
    and o.status='modeled' and o.evidence_tier='modeled'
 ), candidate as (
  select x.opportunity_id,o.net_pnl
  from trader.outcomes o join trader.signals x on x.id=o.signal_id and x.run_id=o.run_id
  where o.run_id=c.id and x.strategy_version_id=p.candidate_strategy_id and o.scenario_id=chosen
    and s.evaluation @> x.available_at and s.evaluation @> o.entry_at and s.evaluation @> o.exit_at
    and o.status='modeled' and o.evidence_tier='modeled'
 )
 select count(*),avg(candidate.net_pnl-baseline.net_pnl) into matched,improvement
 from baseline join candidate using(opportunity_id);
 select count(distinct x.opportunity_id) into base_n from trader.signals x
  where x.run_id=b.id and x.strategy_version_id=p.baseline_strategy_id and s.evaluation @> x.available_at;
 select count(distinct x.opportunity_id) into candidate_n from trader.signals x
  where x.run_id=c.id and x.strategy_version_id=p.candidate_strategy_id and s.evaluation @> x.available_at;
 if matched<minimum_n or matched<>new.sample_count or matched<>base_n or matched<>candidate_n
    or improvement is null or improvement<minimum_gain then
  raise exception 'Observed matched outcomes do not support declared pass';
 end if;
 new.metrics:=new.metrics||jsonb_build_object('verified_matched_opportunities',matched,
   'verified_mean_net_improvement',improvement,'complete_matching',true);
 return new;
end $$;
create trigger learning_evaluation_proof before insert on trader.learning_evaluations
 for each row execute function trader.guard_learning_evaluation();
revoke all on function trader.guard_learning_evaluation() from public,anon,authenticated;
grant execute on function trader.guard_learning_evaluation() to service_role;

create function trader.guard_reviewed_proposal() returns trigger
language plpgsql security invoker set search_path='' as $$
begin
 if old.status in ('validated','approved','rejected','retired') and
    (new.baseline_strategy_id is distinct from old.baseline_strategy_id or
     new.candidate_strategy_id is distinct from old.candidate_strategy_id or
     new.problem is distinct from old.problem or new.hypothesis is distinct from old.hypothesis or
     new.selection_history is distinct from old.selection_history or new.category is distinct from old.category) then
  raise exception 'Reviewed proposal terms are immutable; create a new proposal';
 end if;
 if old.status in ('approved','rejected','retired') and new.status not in (old.status,'retired') then
  raise exception 'Terminal review state cannot be silently reopened';
 end if;
 return new;
end $$;
create trigger reviewed_proposal before update on trader.learning_proposals
 for each row execute function trader.guard_reviewed_proposal();
revoke all on function trader.guard_reviewed_proposal() from public,anon,authenticated;
grant execute on function trader.guard_reviewed_proposal() to service_role;
do $$
declare t text;
begin
 foreach t in array array['opportunities','documents','instrument_versions','learning_evaluations',
 'learning_evidence','retrieval_traces','retrieval_hits','retrieval_evaluations','drift_observations',
 'risk_snapshots','cost_entries'] loop
  execute format('create trigger immutable_record before update or delete on trader.%I for each row execute function trader.reject_mutation()',t);
 end loop;
end $$;

