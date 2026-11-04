-- Synthetic transaction fixtures only. Every row is rolled back.
begin;
create temporary table learning_checks(name text primary key,passed boolean not null);
do $$
declare d uuid:=gen_random_uuid(); inst uuid:=gen_random_uuid(); h uuid:=gen_random_uuid();
 bv uuid:=gen_random_uuid(); cv uuid:=gen_random_uuid(); br uuid:=gen_random_uuid(); cr uuid:=gen_random_uuid();
 scenario uuid:=gen_random_uuid(); split uuid:=gen_random_uuid(); badsplit uuid:=gen_random_uuid();
 proposal uuid:=gen_random_uuid(); evaluation uuid:=gen_random_uuid(); op uuid; bs uuid; cs uuid;
 denied boolean; i integer; measured numeric;
begin
 insert into trader.instruments(id,symbol) values(inst,'LEARNING_FIXTURE');
 insert into trader.datasets(id,name,fingerprint,universe_definition,quality_tier)
 values(d,'Synthetic validation fixture',d::text,'{}','synthetic');
 update trader.datasets set status='frozen',frozen_at=now() where id=d;
 insert into trader.hypotheses(id,key,family,claim,success_criteria) values(h,h::text,'fixture','fixture','{}');
 insert into trader.execution_scenarios(id,fingerprint,parameters,assumptions)
 values(scenario,scenario::text,'{}','{"synthetic":true}');
 insert into trader.strategy_versions(id,hypothesis_id,version,parameters,spec_sha256,code_sha256)
 values(bv,h,'baseline','{}','baseline','fixture'),
 (cv,h,'candidate',jsonb_build_object('validation_criteria',jsonb_build_object(
 'min_matched_opportunities',2,'min_mean_net_improvement',0.5,'scenario_id',scenario)), 'candidate','fixture');
 insert into trader.runs(id,dataset_id,purpose,status,manifest,code_sha256)
 values(br,d,'validation','writing','{}','fixture'),(cr,d,'validation','writing','{}','fixture');
 insert into trader.run_strategies values(br,bv),(cr,cv);
 denied:=false;
 begin insert into trader.evaluation_splits(run_id,development,evaluation,selection_notes)
 values(cr,tstzrange('2026-10-01','2026-10-20'),tstzrange('2026-10-15','2026-10-25'),'overlap');
 exception when check_violation then denied:=true; end;
 assert denied,'Overlapping windows accepted by writable run';
 insert into learning_checks values('overlap_rejected_by_range_constraint',true);
 denied:=false;
 begin insert into trader.evaluation_splits(run_id,development,evaluation,embargo,selection_notes)
 values(cr,tstzrange('2026-10-01','2026-10-20'),tstzrange('2026-10-21','2026-10-25'),interval '2 days','embargo');
 exception when check_violation then denied:=true; end;
 assert denied,'Insufficient embargo accepted';
 insert into learning_checks values('embargo_enforced',true);
 insert into trader.evaluation_splits(id,run_id,development,evaluation,independent_data,selection_notes)
 values(split,cr,tstzrange('2026-10-01','2026-10-20'),tstzrange('2026-11-01','2026-11-03'),true,'synthetic independent fixture'),
 (badsplit,cr,null,tstzrange('2026-11-01','2026-11-03'),false,'not independent');
 for i in 1..2 loop
  op:=gen_random_uuid();bs:=gen_random_uuid();cs:=gen_random_uuid();
  insert into trader.opportunities(id,instrument_id,first_observable_at,clustering_version,cluster_key)
  values(op,inst,'2026-11-02 14:30+00','fixture',op::text);
  insert into trader.signals(id,run_id,opportunity_id,strategy_version_id,available_at,basis,details)
  values(bs,br,op,bv,'2026-11-02 14:30+00','fixture','{}'),(cs,cr,op,cv,'2026-11-02 14:30+00','fixture','{}');
  denied:=false;
  begin insert into trader.outcomes(run_id,signal_id,scenario_id,status,evidence_tier,net_pnl,details)
  values(br,bs,scenario,'missing','censored',0,'{}');
  exception when check_violation then denied:=true; end;
  assert denied,'Censored PnL accepted on writable run';
  insert into trader.outcomes(run_id,signal_id,scenario_id,status,evidence_tier,quantity,net_pnl,entry_at,exit_at,details)
  values(br,bs,scenario,'modeled','modeled',1,1,'2026-11-02 14:31+00','2026-11-02 14:45+00','{}'),
  (cr,cs,scenario,'modeled','modeled',1,2,'2026-11-02 14:31+00','2026-11-02 14:45+00','{}');
 end loop;
 insert into learning_checks values('censored_pnl_rejected_by_constraint',true);
 update trader.runs set status='complete',completed_at=now() where id in(br,cr);
 insert into trader.learning_proposals(id,category,problem,hypothesis,baseline_strategy_id,candidate_strategy_id,selection_history)
 values(proposal,'signal','fixture','fixture',bv,cv,'{}');
 denied:=false;
 begin insert into trader.learning_evaluations(proposal_id,baseline_run_id,candidate_run_id,split_id,metrics,sample_count,uncertainty,result)
 values(proposal,br,cr,split,jsonb_build_object('scenario_id',scenario),200,'{}','pass');
 exception when raise_exception then denied:=true; end;
 assert denied,'Fabricated sample count accepted';
 insert into learning_checks values('forged_sample_count_rejected',true);
 denied:=false;
 begin insert into trader.learning_evaluations(proposal_id,baseline_run_id,candidate_run_id,split_id,metrics,sample_count,uncertainty,result)
 values(proposal,br,cr,badsplit,jsonb_build_object('scenario_id',scenario),2,'{}','pass');
 exception when raise_exception then denied:=true; end;
 assert denied,'Nonindependent comparison accepted';
 insert into learning_checks values('nonindependent_validation_rejected',true);
 denied:=false;
 begin insert into trader.learning_evaluations(proposal_id,baseline_run_id,candidate_run_id,split_id,metrics,sample_count,uncertainty,result)
 values(proposal,br,cr,split,jsonb_build_object('scenario_id',gen_random_uuid()),2,'{}','pass');
 exception when raise_exception then denied:=true; end;
 assert denied,'Undeclared scenario accepted';
 insert into learning_checks values('scenario_cherry_picking_rejected',true);
 insert into trader.learning_evaluations(id,proposal_id,baseline_run_id,candidate_run_id,split_id,metrics,sample_count,uncertainty,result)
 values(evaluation,proposal,br,cr,split,jsonb_build_object('scenario_id',scenario),2,'{"synthetic":true}','pass');
 select (metrics->>'verified_mean_net_improvement')::numeric into measured
 from trader.learning_evaluations where id=evaluation;
 assert measured=1,'Matched improvement not recomputed';
 insert into learning_checks values('supported_comparison_recomputed',true);
 update trader.learning_proposals set status='validated' where id=proposal;
 insert into learning_checks values('supported_candidate_validates',true);
 denied:=false;
 begin update trader.learning_proposals set hypothesis='switch after review' where id=proposal;
 exception when raise_exception then denied:=true; end;
 assert denied,'Reviewed terms changed';
 insert into learning_checks values('reviewed_candidate_frozen',true);
 denied:=false;
 begin update trader.learning_evaluations set sample_count=200 where id=evaluation;
 exception when raise_exception then denied:=true; end;
 assert denied,'Evaluation changed after review';
 insert into learning_checks values('evaluation_audit_immutable',true);
 denied:=false;
 begin update trader.learning_proposals set status='approved' where id=proposal;
 exception when raise_exception then denied:=true; end;
 assert denied,'Supported candidate activated without approval';
 insert into learning_checks values('validated_still_requires_human_approval',true);
end $$;
select jsonb_build_object('checks',count(*),'passed',bool_and(passed),'names',jsonb_agg(name order by name)) as learning_acceptance from learning_checks;
rollback;
