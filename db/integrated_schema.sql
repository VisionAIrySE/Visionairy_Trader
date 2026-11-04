-- Integrated research + learning schema. Paper only; backend-only access.
create extension if not exists vector with schema extensions;
create schema trader;
revoke all on schema trader from public, anon, authenticated;
grant usage on schema trader to service_role;
alter default privileges in schema trader revoke execute on functions from public;

create table trader.instruments (
 id uuid primary key default gen_random_uuid(), symbol text not null, exchange text not null default 'UNKNOWN',
 asset_type text not null default 'stock' check(asset_type in ('stock','etf')),
 created_at timestamptz not null default now(), unique(symbol,exchange)
);
create table trader.instrument_versions (
 id uuid primary key default gen_random_uuid(), instrument_id uuid not null references trader.instruments,
 valid_from timestamptz not null, valid_until timestamptz, known_at timestamptz not null,
 attributes jsonb not null, check(valid_until is null or valid_until>valid_from)
);
create index instrument_versions_lookup on trader.instrument_versions(instrument_id,known_at,valid_from);
create table trader.sources (
 id uuid primary key default gen_random_uuid(), provider text not null, source_key text not null,
 sha256 text not null check(sha256 ~ '^[0-9a-f]{64}$'), instrument_id uuid references trader.instruments,
 interval_label text not null, available_at timestamptz, received_at timestamptz not null default now(),
 raw_object_key text, row_count bigint not null check(row_count>=0),
 source_metadata jsonb not null default '{}', unique(provider,source_key,sha256)
);
create index sources_instrument on trader.sources(instrument_id,interval_label);
create table trader.observations (
 id uuid primary key default gen_random_uuid(), fingerprint text not null unique,
 instrument_id uuid not null references trader.instruments, interval_label text not null,
 observed_at timestamptz not null, available_at timestamptz not null,
 open numeric, high numeric, low numeric, close numeric, price numeric,
 volume numeric not null check(volume>=0), vwap numeric,
 check(available_at>=observed_at),
 check(num_nonnulls(open,high,low,close)=0 or
       (num_nonnulls(open,high,low,close)=4 and open>0 and high>=greatest(open,close,low) and low>0 and low<=least(open,close,high) and close>0))
);
create index observations_symbol_time on trader.observations(instrument_id,interval_label,observed_at);
create index observations_market_time on trader.observations(interval_label,observed_at,instrument_id);
create table trader.source_observations (
 source_id uuid not null references trader.sources, sequence bigint not null,
 observation_id uuid not null references trader.observations, source_time_text text,
 primary key(source_id,sequence)
);
create index source_observations_record on trader.source_observations(observation_id,source_id);
create table trader.datasets (
 id uuid primary key default gen_random_uuid(), name text not null,
 fingerprint text not null unique, status text not null default 'building' check(status in ('building','frozen')),
 universe_definition jsonb not null, quality_tier text not null,
 created_at timestamptz not null default now(), frozen_at timestamptz,
 check((status='frozen')=(frozen_at is not null))
);
create table trader.dataset_sources (
 dataset_id uuid not null references trader.datasets, source_id uuid not null references trader.sources,
 primary key(dataset_id,source_id)
);
create index dataset_sources_source on trader.dataset_sources(source_id);
create table trader.data_quality_events (
 id uuid primary key default gen_random_uuid(), source_id uuid references trader.sources,
 dataset_id uuid references trader.datasets, instrument_id uuid references trader.instruments,
 occurred_at timestamptz not null, kind text not null, severity text not null,
 details jsonb not null, check(num_nonnulls(source_id,dataset_id,instrument_id)>0)
);
create index quality_source on trader.data_quality_events(source_id,occurred_at);
create index quality_dataset on trader.data_quality_events(dataset_id,occurred_at);
create index quality_instrument on trader.data_quality_events(instrument_id,occurred_at);
create table trader.coverage_windows (
 id uuid primary key default gen_random_uuid(), dataset_id uuid not null references trader.datasets,
 instrument_id uuid not null references trader.instruments, interval_label text not null,
 window_start timestamptz not null, window_end timestamptz not null,
 expected_records bigint, observed_records bigint not null check(observed_records>=0),
 discovery_lag_ms numeric, status text not null, check(window_end>window_start)
);
create index coverage_dataset on trader.coverage_windows(dataset_id,instrument_id,window_start);
create index coverage_instrument on trader.coverage_windows(instrument_id,window_start);

create table trader.hypotheses (
 id uuid primary key default gen_random_uuid(), key text not null unique,
 family text not null, claim text not null, success_criteria jsonb not null,
 created_at timestamptz not null default now()
);
create table trader.strategy_versions (
 id uuid primary key default gen_random_uuid(), hypothesis_id uuid not null references trader.hypotheses,
 version text not null, parameters jsonb not null, spec_sha256 text not null,
 code_sha256 text not null, created_at timestamptz not null default now(),
 unique(hypothesis_id,version)
);
create table trader.runs (
 id uuid primary key default gen_random_uuid(), dataset_id uuid not null references trader.datasets,
 purpose text not null check(purpose in ('exploration','validation','forward_paper')),
 status text not null check(status in ('writing','complete','failed')),
 manifest jsonb not null, code_sha256 text not null,
 environment text not null default 'paper' check(environment='paper'),
 started_at timestamptz not null default now(), completed_at timestamptz,
 check(status<>'complete' or completed_at is not null)
);
create index runs_dataset on trader.runs(dataset_id,started_at);
create table trader.run_strategies (
 run_id uuid not null references trader.runs, strategy_version_id uuid not null references trader.strategy_versions,
 primary key(run_id,strategy_version_id)
);
create index run_strategies_version on trader.run_strategies(strategy_version_id);
create table trader.evaluation_splits (
 id uuid primary key default gen_random_uuid(), run_id uuid not null references trader.runs,
 development tstzrange, evaluation tstzrange not null,
 embargo interval not null default interval '0' check(embargo>=interval '0'),
 independent_data boolean not null default false, selection_notes text not null,
 check(not isempty(evaluation) and not lower_inf(evaluation) and not upper_inf(evaluation)),
 check(development is null or (not isempty(development) and not lower_inf(development) and not upper_inf(development)
       and not development && evaluation and upper(development)+embargo<=lower(evaluation)))
);
create index splits_run on trader.evaluation_splits(run_id);
create table trader.opportunities (
 id uuid primary key default gen_random_uuid(), instrument_id uuid not null references trader.instruments,
 first_observable_at timestamptz not null, clustering_version text not null,
 cluster_key text not null unique, context jsonb not null default '{}'
);
create index opportunities_instrument on trader.opportunities(instrument_id,first_observable_at);
create table trader.signals (
 id uuid primary key default gen_random_uuid(), run_id uuid not null references trader.runs,
 opportunity_id uuid not null references trader.opportunities,
 strategy_version_id uuid not null references trader.strategy_versions,
 available_at timestamptz not null, detected_at timestamptz,
 basis text not null, details jsonb not null, unique(run_id,id)
);
create index signals_opportunity on trader.signals(opportunity_id);
create index signals_strategy on trader.signals(strategy_version_id,available_at);
create index signals_run_time on trader.signals(run_id,available_at);
create table trader.execution_scenarios (
 id uuid primary key default gen_random_uuid(), fingerprint text not null unique,
 parameters jsonb not null, assumptions jsonb not null,
 environment text not null default 'paper' check(environment='paper')
);
create table trader.outcomes (
 id uuid primary key default gen_random_uuid(), run_id uuid not null,
 signal_id uuid not null, scenario_id uuid not null references trader.execution_scenarios,
 status text not null, evidence_tier text not null check(evidence_tier in ('modeled','observed','censored')),
 quantity numeric, net_pnl numeric, entry_at timestamptz, exit_at timestamptz,
 max_adverse_excursion numeric, max_favorable_excursion numeric, details jsonb not null,
 unique(run_id,signal_id,scenario_id),
 foreign key(run_id,signal_id) references trader.signals(run_id,id),
 check(quantity is null or quantity>=0), check(exit_at is null or entry_at is null or exit_at>=entry_at),
 check(evidence_tier<>'censored' or net_pnl is null)
);
create index outcomes_signal on trader.outcomes(signal_id);
create index outcomes_summary on trader.outcomes(run_id,scenario_id,status) include(net_pnl);
create index outcomes_scenario on trader.outcomes(scenario_id);
create table trader.result_summaries (
 id uuid primary key default gen_random_uuid(), run_id uuid not null references trader.runs,
 summary_key text not null, dimensions jsonb not null, statistics jsonb not null,
 opportunity_count integer not null check(opportunity_count>=0),
 independent_sample_count integer, created_at timestamptz not null default now(),
 unique(run_id,summary_key), check(independent_sample_count is null or independent_sample_count>=0)
);
create table trader.regime_labels (
 id uuid primary key default gen_random_uuid(), instrument_id uuid references trader.instruments,
 available_at timestamptz not null, window_start timestamptz not null, window_end timestamptz not null,
 method_version text not null, labels jsonb not null, check(window_end>window_start and available_at>=window_end)
);
create index regimes_time on trader.regime_labels(available_at);
create index regimes_instrument on trader.regime_labels(instrument_id,available_at);

create table trader.portfolio_accounts (
 id uuid primary key default gen_random_uuid(), name text not null, run_id uuid not null references trader.runs,
 starting_equity numeric not null check(starting_equity>0), currency text not null default 'USD',
 risk_policy jsonb not null, environment text not null default 'paper' check(environment='paper')
);
create index portfolios_run on trader.portfolio_accounts(run_id);
create table trader.cash_ledger (
 id uuid primary key default gen_random_uuid(), portfolio_id uuid not null references trader.portfolio_accounts,
 event_key text not null, occurred_at timestamptz not null, settles_at timestamptz,
 kind text not null check(kind in ('initial','reserve','release','purchase','sale','fee','settlement','adjustment')),
 amount numeric not null, currency text not null default 'USD', evidence jsonb not null,
 unique(portfolio_id,event_key)
);
create index cash_portfolio_time on trader.cash_ledger(portfolio_id,occurred_at);
create table trader.simulated_orders (
 id uuid primary key default gen_random_uuid(), portfolio_id uuid not null references trader.portfolio_accounts,
 signal_id uuid references trader.signals, instrument_id uuid not null references trader.instruments,
 idempotency_key text not null unique, side text not null check(side in ('buy','sell')),
 quantity numeric not null check(quantity>0), created_at timestamptz not null,
 eligible_at timestamptz not null, order_terms jsonb not null, state text not null,
 environment text not null default 'paper' check(environment='paper'), check(eligible_at>=created_at)
);
create index orders_portfolio on trader.simulated_orders(portfolio_id,created_at);
create index orders_signal on trader.simulated_orders(signal_id);
create index orders_instrument on trader.simulated_orders(instrument_id);
create table trader.simulated_fills (
 id uuid primary key default gen_random_uuid(), order_id uuid not null references trader.simulated_orders,
 fill_key text not null unique, filled_at timestamptz not null, quantity numeric not null check(quantity>0),
 price numeric not null check(price>0), fees numeric not null check(fees>=0),
 evidence_tier text not null, observation_id uuid references trader.observations, assumptions jsonb not null
);
create index fills_order on trader.simulated_fills(order_id,filled_at);
create index fills_observation on trader.simulated_fills(observation_id);
create table trader.position_lots (
 id uuid primary key default gen_random_uuid(), portfolio_id uuid not null references trader.portfolio_accounts,
 instrument_id uuid not null references trader.instruments, opening_fill_id uuid not null unique references trader.simulated_fills,
 opened_quantity numeric not null check(opened_quantity>0), closed_quantity numeric not null default 0,
 check(closed_quantity>=0 and closed_quantity<=opened_quantity)
);
create index lots_portfolio on trader.position_lots(portfolio_id,instrument_id);
create index lots_instrument on trader.position_lots(instrument_id);
create table trader.risk_snapshots (
 id uuid primary key default gen_random_uuid(), portfolio_id uuid not null references trader.portfolio_accounts,
 as_of timestamptz not null, equity numeric not null, reserved_cash numeric not null,
 planned_open_risk numeric not null check(planned_open_risk>=0),
 exposures jsonb not null, warnings jsonb not null, unique(portfolio_id,as_of)
);

create table trader.documents (
 id uuid primary key default gen_random_uuid(), source_uri text not null,
 kind text not null check(kind in ('news','filing','research','lesson','experiment_note')),
 title text not null, trust_class text not null, license_metadata jsonb not null default '{}'
);
create table trader.document_versions (
 id uuid primary key default gen_random_uuid(), document_id uuid not null references trader.documents,
 content_sha256 text not null, published_at timestamptz, first_seen_at timestamptz not null,
 available_at timestamptz not null, original_object_key text, metadata jsonb not null default '{}',
 unique(document_id,content_sha256), check(available_at>=first_seen_at)
);
create index document_version_cutoff on trader.document_versions(available_at,first_seen_at);
create table trader.document_chunks (
 id uuid primary key default gen_random_uuid(), document_version_id uuid not null references trader.document_versions,
 ordinal integer not null check(ordinal>=0), content text not null, content_sha256 text not null,
 chunker_version text not null, citation jsonb not null,
 fts tsvector generated always as (to_tsvector('english'::regconfig,content)) stored,
 unique(document_version_id,chunker_version,ordinal)
);
create index chunks_fts on trader.document_chunks using gin(fts);
create table trader.embedding_profiles (
 id uuid primary key default gen_random_uuid(), provider text not null, model text not null,
 model_version text not null, dimensions integer not null check(dimensions between 1 and 16000),
 available_from timestamptz not null, training_cutoff timestamptz,
 purpose text not null check(purpose in ('research','test_fixture')),
 unique(provider,model,model_version,dimensions), unique(id,dimensions)
);
create table trader.chunk_embeddings (
 chunk_id uuid not null references trader.document_chunks, profile_id uuid not null,
 dimensions integer not null, embedding extensions.vector not null,
 source_content_sha256 text not null, created_at timestamptz not null default now(),
 primary key(chunk_id,profile_id),
 foreign key(profile_id,dimensions) references trader.embedding_profiles(id,dimensions),
 check(extensions.vector_dims(embedding)=dimensions)
);
create index embeddings_profile on trader.chunk_embeddings(profile_id);
create table trader.retrieval_traces (
 id uuid primary key default gen_random_uuid(), query_text text not null, as_of timestamptz not null,
 profile_id uuid references trader.embedding_profiles, retrieval_version text not null,
 elapsed_ms numeric, context_filter jsonb not null, created_at timestamptz not null default now()
);
create index retrieval_profile on trader.retrieval_traces(profile_id);
create table trader.retrieval_hits (
 trace_id uuid not null references trader.retrieval_traces, chunk_id uuid not null references trader.document_chunks,
 rank integer not null check(rank>0), score numeric not null, citation jsonb not null,
 primary key(trace_id,rank), unique(trace_id,chunk_id)
);
create index retrieval_chunk on trader.retrieval_hits(chunk_id);
create table trader.retrieval_evaluations (
 id uuid primary key default gen_random_uuid(), trace_id uuid not null references trader.retrieval_traces,
 evaluator_version text not null, expected_chunk_ids uuid[] not null, metrics jsonb not null,
 cutoff_violations integer not null check(cutoff_violations>=0), evaluated_at timestamptz not null default now()
);
create index retrieval_evaluations_trace on trader.retrieval_evaluations(trace_id);

create table trader.learning_proposals (
 id uuid primary key default gen_random_uuid(), category text not null check(category in
 ('signal','timing','sizing','regime','preference','operations')),
 problem text not null, hypothesis text not null,
 baseline_strategy_id uuid references trader.strategy_versions,
 candidate_strategy_id uuid references trader.strategy_versions,
 status text not null default 'draft' check(status in ('draft','testing','validated','approved','rejected','retired')),
 selection_history jsonb not null, created_at timestamptz not null default now(),
 check(baseline_strategy_id is null or candidate_strategy_id is null or baseline_strategy_id<>candidate_strategy_id)
);
create index proposals_baseline on trader.learning_proposals(baseline_strategy_id);
create index proposals_candidate on trader.learning_proposals(candidate_strategy_id);
create table trader.learning_evaluations (
 id uuid primary key default gen_random_uuid(), proposal_id uuid not null references trader.learning_proposals,
 baseline_run_id uuid not null references trader.runs, candidate_run_id uuid not null references trader.runs,
 split_id uuid not null references trader.evaluation_splits,
 metrics jsonb not null, sample_count integer not null check(sample_count>=0),
 uncertainty jsonb not null, result text not null check(result in ('pass','fail','inconclusive')),
 evaluated_at timestamptz not null default now(), check(baseline_run_id<>candidate_run_id)
);
create index learning_evaluations_proposal on trader.learning_evaluations(proposal_id);
create index learning_evaluations_baseline on trader.learning_evaluations(baseline_run_id);
create index learning_evaluations_candidate on trader.learning_evaluations(candidate_run_id);
create index learning_evaluations_split on trader.learning_evaluations(split_id);
create table trader.learning_evidence (
 id uuid primary key default gen_random_uuid(), proposal_id uuid not null references trader.learning_proposals,
 outcome_id uuid references trader.outcomes, chunk_id uuid references trader.document_chunks,
 run_id uuid references trader.runs, interpretation text not null,
 check(num_nonnulls(outcome_id,chunk_id,run_id)>0)
);
create index evidence_proposal on trader.learning_evidence(proposal_id);
create index evidence_outcome on trader.learning_evidence(outcome_id);
create index evidence_chunk on trader.learning_evidence(chunk_id);
create index evidence_run on trader.learning_evidence(run_id);
create table trader.user_feedback (
 id uuid primary key default gen_random_uuid(), user_id uuid references auth.users,
 signal_id uuid references trader.signals, opportunity_id uuid references trader.opportunities,
 response text not null check(response in ('approve','decline','modify','expire','comment')),
 reason text, context jsonb not null, occurred_at timestamptz not null,
 profitability_label boolean, check(profitability_label is null)
);
create index feedback_user on trader.user_feedback(user_id,occurred_at);
create index feedback_signal on trader.user_feedback(signal_id);
create index feedback_opportunity on trader.user_feedback(opportunity_id);
create table trader.preference_versions (
 id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users,
 version integer not null check(version>0), preferences jsonb not null,
 available_at timestamptz not null, basis_feedback_ids uuid[] not null default '{}',
 unique(user_id,version)
);
create table trader.approval_requests (
 id uuid primary key default gen_random_uuid(), proposal_id uuid references trader.learning_proposals,
 action_kind text not null, payload jsonb not null, payload_sha256 text not null,
 status text not null default 'pending' check(status in ('pending','approved','denied','expired','modified')),
 requested_at timestamptz not null default now(), expires_at timestamptz not null,
 decided_at timestamptz, decided_by uuid references auth.users,
 environment text not null default 'paper' check(environment='paper'),
 check(expires_at>requested_at),
 check(status not in ('approved','denied','modified') or (decided_at is not null and decided_by is not null)),
 check(status<>'approved' or decided_at<=expires_at)
);
create index approval_proposal on trader.approval_requests(proposal_id,status);
create index approval_actor on trader.approval_requests(decided_by);
create table trader.strategy_deployments (
 id uuid primary key default gen_random_uuid(), strategy_version_id uuid not null references trader.strategy_versions,
 approval_id uuid references trader.approval_requests, environment text not null default 'paper' check(environment='paper'),
 activated_at timestamptz not null, retired_at timestamptz, artifact_sha256 text not null,
 check(retired_at is null or retired_at>=activated_at)
);
create index deployments_strategy on trader.strategy_deployments(strategy_version_id,activated_at);
create index deployments_approval on trader.strategy_deployments(approval_id);
create table trader.drift_observations (
 id uuid primary key default gen_random_uuid(), strategy_version_id uuid not null references trader.strategy_versions,
 observed_at timestamptz not null, reference_window tstzrange not null, current_window tstzrange not null,
 metrics jsonb not null, severity text not null, proposal_id uuid references trader.learning_proposals
);
create index drift_strategy on trader.drift_observations(strategy_version_id,observed_at);
create index drift_proposal on trader.drift_observations(proposal_id);

create table trader.jobs (
 id uuid primary key default gen_random_uuid(), kind text not null, idempotency_key text not null unique,
 payload jsonb not null, status text not null default 'queued' check(status in ('queued','running','complete','failed','cancelled')),
 available_at timestamptz not null default now(), lease_until timestamptz,
 attempts integer not null default 0 check(attempts>=0), checkpoint jsonb not null default '{}'
);
create index jobs_queue on trader.jobs(status,available_at) where status in ('queued','running');
create table trader.job_attempts (
 id uuid primary key default gen_random_uuid(), job_id uuid not null references trader.jobs,
 started_at timestamptz not null, finished_at timestamptz, state text not null,
 error_code text, metrics jsonb not null, check(finished_at is null or finished_at>=started_at)
);
create index attempts_job on trader.job_attempts(job_id,started_at);
create table trader.operational_metrics (
 id bigint generated always as identity primary key, job_id uuid references trader.jobs,
 run_id uuid references trader.runs, observed_at timestamptz not null, name text not null,
 value numeric not null, unit text not null, labels jsonb not null
);
create index metrics_time on trader.operational_metrics(name,observed_at);
create index metrics_job on trader.operational_metrics(job_id);
create index metrics_run on trader.operational_metrics(run_id);
create table trader.cost_entries (
 id uuid primary key default gen_random_uuid(), run_id uuid references trader.runs,
 job_id uuid references trader.jobs, provider text not null, category text not null,
 incurred_at timestamptz not null, amount numeric not null check(amount>=0),
 currency text not null default 'USD', usage jsonb not null
);
create index costs_run on trader.cost_entries(run_id);
create index costs_job on trader.cost_entries(job_id);
create index costs_time on trader.cost_entries(incurred_at,category);
create table trader.retention_policies (
 key text primary key, policy jsonb not null, enabled boolean not null default false,
 archive_verification_required boolean not null default true check(archive_verification_required),
 created_at timestamptz not null default now()
);
create table trader.audit_events (
 id bigint generated always as identity primary key, occurred_at timestamptz not null default now(),
 actor_type text not null, action text not null, entity_type text not null, entity_id text not null,
 details jsonb not null, previous_event_hash text, event_hash text not null unique
);
create index audit_entity on trader.audit_events(entity_type,entity_id,occurred_at);

