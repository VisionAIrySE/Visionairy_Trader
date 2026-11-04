begin;
create temporary table integration_checks(name text primary key, passed boolean not null);
do $$
declare d uuid:=gen_random_uuid(); src uuid:=gen_random_uuid(); inst uuid:=gen_random_uuid();
 r uuid:=gen_random_uuid(); h uuid:=gen_random_uuid(); v uuid:=gen_random_uuid();
 op uuid:=gen_random_uuid(); sig uuid:=gen_random_uuid(); scenario uuid:=gen_random_uuid();
 doc uuid:=gen_random_uuid(); oldv uuid:=gen_random_uuid(); futurev uuid:=gen_random_uuid();
 oldc uuid:=gen_random_uuid(); futurec uuid:=gen_random_uuid(); profile uuid:=gen_random_uuid();
 proposal uuid:=gen_random_uuid(); j1 uuid:=gen_random_uuid(); j2 uuid:=gen_random_uuid();
 found uuid; n integer; denied boolean; rec record;
begin
 insert into trader.instruments(id,symbol) values(inst,'TEST_FIXTURE');
 insert into trader.sources(id,provider,source_key,sha256,instrument_id,interval_label,row_count)
 values(src,'test_fixture','fixture',repeat('0',64),inst,'1min',1);
 insert into trader.datasets(id,name,fingerprint,universe_definition,quality_tier)
 values(d,'test_fixture',d::text,'{"scope":"fixture"}','synthetic');
 insert into trader.dataset_sources values(d,src);
 update trader.datasets set status='frozen',frozen_at=now() where id=d;
 denied:=false;
 begin delete from trader.dataset_sources where dataset_id=d; exception when others then denied:=true; end;
 assert denied,'Frozen membership changed';
 insert into integration_checks values('frozen_dataset_membership',true);
 denied:=false;
 begin update trader.sources set row_count=2 where id=src; exception when others then denied:=true; end;
 assert denied,'Source changed';
 insert into integration_checks values('source_immutability',true);
 insert into trader.hypotheses(id,key,family,claim,success_criteria) values(h,h::text,'fixture','test','{}');
 insert into trader.strategy_versions(id,hypothesis_id,version,parameters,spec_sha256,code_sha256)
 values(v,h,'1','{}',repeat('1',64),repeat('2',64));
 insert into trader.runs(id,dataset_id,purpose,status,manifest,code_sha256)
 values(r,d,'exploration','writing','{}',repeat('3',64));
 insert into trader.run_strategies values(r,v);
 insert into trader.opportunities(id,instrument_id,first_observable_at,clustering_version,cluster_key)
 values(op,inst,now(),'fixture',op::text);
 insert into trader.signals(id,run_id,opportunity_id,strategy_version_id,available_at,basis,details)
 values(sig,r,op,v,now(),'fixture','{}');
 insert into trader.execution_scenarios(id,fingerprint,parameters,assumptions)
 values(scenario,scenario::text,'{}','{"modeled":true}');
 insert into trader.outcomes(run_id,signal_id,scenario_id,status,evidence_tier,quantity,net_pnl,details)
 values(r,sig,scenario,'modeled','modeled',1,1,'{}');
 update trader.runs set status='complete',completed_at=now() where id=r;
 denied:=false;
 begin update trader.outcomes set net_pnl=100 where run_id=r; exception when others then denied:=true; end;
 assert denied,'Completed outcomes changed';
 insert into integration_checks values('completed_run_immutability',true);
 denied:=false;
 begin insert into trader.runs(dataset_id,purpose,status,manifest,code_sha256,environment)
 values(d,'exploration','writing','{}','x','live'); exception when check_violation then denied:=true; end;
 assert denied,'Live mode accepted';
 insert into integration_checks values('live_execution_not_enabled',true);
 denied:=false;
 begin insert into trader.evaluation_splits(run_id,development,evaluation,selection_notes)
 values(r,tstzrange('2026-10-01','2026-10-20'),tstzrange('2026-10-15','2026-10-25'),'overlap');
 exception when others then denied:=true; end;
 assert denied,'Overlapping or completed split accepted';
 insert into integration_checks values('frozen_split_write_blocked',true);
 insert into trader.documents(id,source_uri,kind,title,trust_class)
 values(doc,'fixture://test','research','Fixture quiet-stock research','test_fixture');
 insert into trader.document_versions(id,document_id,content_sha256,published_at,first_seen_at,available_at)
 values(oldv,doc,repeat('a',64),'2026-11-01','2026-11-01','2026-11-01'),
       (futurev,doc,repeat('b',64),'2026-11-03','2026-11-03','2026-11-03');
 insert into trader.document_chunks(id,document_version_id,ordinal,content,content_sha256,chunker_version,citation)
 values(oldc,oldv,0,'quiet stock ignition before news',repeat('c',64),'fixture','{"source":"old"}'),
       (futurec,futurev,0,'quiet stock ignition revised after news',repeat('d',64),'fixture','{"source":"future"}');
 select count(*) into n from trader.search_evidence('quiet stock','2026-11-02',10);
 assert n=1,'Historical keyword cutoff failed';
 select chunk_id into found from trader.search_evidence('quiet stock','2026-11-02',10);
 assert found=oldc,'Future text leaked';
 insert into integration_checks values('keyword_as_of_cutoff',true);
 select chunk_id into found from trader.search_evidence('quiet stock','2026-11-04',10);
 assert found=futurec,'Latest available version not selected';
 insert into integration_checks values('versioned_document_retrieval',true);
 insert into trader.embedding_profiles(id,provider,model,model_version,dimensions,available_from,training_cutoff,purpose)
 values(profile,'fixture','synthetic','1',3,'2026-10-01','2026-09-01','test_fixture');
 insert into trader.chunk_embeddings(chunk_id,profile_id,dimensions,embedding,source_content_sha256)
 values(oldc,profile,3,'[1,0,0]',repeat('c',64)),(futurec,profile,3,'[1,0,0]',repeat('d',64));
 select chunk_id into found from trader.search_evidence('quiet stock','2026-11-02',10,'[1,0,0]',profile,true);
 assert found=oldc,'Hybrid cutoff failed';
 insert into integration_checks values('hybrid_as_of_cutoff',true);
 denied:=false;
 begin perform * from trader.search_evidence('quiet stock','2026-11-02',10,'[1,0,0]',profile,false);
 exception when others then denied:=true; end;
 assert denied,'Fixture vectors used without explicit test flag';
 insert into integration_checks values('synthetic_vectors_separated',true);
 denied:=false;
 begin perform * from trader.search_evidence('quiet stock','2026-11-02',10,'[1,0]',profile,true);
 exception when others then denied:=true; end;
 assert denied,'Dimension mismatch accepted';
 insert into integration_checks values('embedding_dimension_guard',true);
 denied:=false;
 begin perform * from trader.search_evidence('quiet stock','2026-09-15',10,'[1,0,0]',profile,true);
 exception when others then denied:=true; end;
 assert denied,'Future model accepted';
 insert into integration_checks values('model_availability_guard',true);
 insert into trader.learning_proposals(id,category,problem,hypothesis,selection_history)
 values(proposal,'signal','fixture','fixture','{}');
 denied:=false;
 begin update trader.learning_proposals set status='validated' where id=proposal;
 exception when others then denied:=true; end;
 assert denied,'Unevaluated proposal validated';
 insert into integration_checks values('learning_requires_evaluation',true);
 denied:=false;
 begin update trader.learning_proposals set status='approved' where id=proposal;
 exception when others then denied:=true; end;
 assert denied,'Proposal approved without evaluation/approval';
 insert into integration_checks values('learning_requires_approval',true);
 denied:=false;
 begin insert into trader.user_feedback(response,context,occurred_at,profitability_label)
 values('decline','{}',now(),false); exception when check_violation then denied:=true; end;
 assert denied,'Preference labeled strategy loss';
 insert into integration_checks values('preference_not_profit_label',true);
 denied:=false;
 begin insert into trader.outcomes(run_id,signal_id,scenario_id,status,evidence_tier,net_pnl,details)
 values(r,sig,scenario,'missing','censored',0,'{}'); exception when others then denied:=true; end;
 assert denied,'Censored outcome assigned zero PnL';
 insert into integration_checks values('missing_outcomes_not_zero_returns',true);
 insert into trader.jobs(id,kind,idempotency_key,payload) values(j1,'fixture',j1::text,'{}'),(j2,'fixture',j2::text,'{}');
 select id into found from trader.claim_job('fixture',60);
 assert found in (j1,j2),'No job claimed';
 select id into found from trader.claim_job('fixture',60);
 assert found in (j1,j2),'Second job unavailable';
 select count(*) into n from trader.jobs where id in(j1,j2) and attempts=1 and status='running';
 assert n=2,'Active lease reclaimed';
 insert into integration_checks values('job_leases_no_immediate_duplicate',true);
 denied:=false;
 begin insert into trader.jobs(kind,idempotency_key,payload) values('fixture',j1::text,'{}');
 exception when unique_violation then denied:=true; end;
 assert denied,'Idempotency failed';
 insert into integration_checks values('job_idempotency',true);
 assert not has_schema_privilege('anon','trader','USAGE'),'Anonymous schema access';
 assert not has_schema_privilege('authenticated','trader','USAGE'),'Unrestricted authenticated schema access';
 insert into integration_checks values('private_schema_access',true);
 select count(*) into n from pg_class c join pg_namespace ns on ns.oid=c.relnamespace
 where ns.nspname='trader' and c.relkind='r' and not c.relrowsecurity;
 assert n=0,'RLS missing';
 insert into integration_checks values('all_tables_rls',true);
 select count(*) into n from pg_proc p join pg_namespace ns on ns.oid=p.pronamespace
 where ns.nspname='trader' and p.prosecdef;
 assert n=0,'Unexpected privilege escalation function';
 insert into integration_checks values('no_security_definer_functions',true);
 select count(*) into n from trader.outcome_scorecard where run_id=r and distinct_opportunities=1;
 assert n=1,'Opportunity counting failed';
 insert into integration_checks values('opportunity_aware_scorecard',true);
end $$;
select jsonb_build_object('checks',count(*),'passed',bool_and(passed),'names',jsonb_agg(name order by name)) as acceptance from integration_checks;
rollback;

