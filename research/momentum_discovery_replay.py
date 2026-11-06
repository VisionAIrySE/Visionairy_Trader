"""Exploratory, pessimistic bar replay; not executable quotes or market win rates."""
import json, math, random, statistics, hashlib
from collections import defaultdict, Counter
from momentum_cohort import ROOT, DIR, read, write

POLICIES=['initial_only','trail_8pct','ratchet_10_20_30','half_at_10_trail_8']
SCENARIOS=[('base',1,.0025),('slower',2,.005),('stress',5,.01)]

def match(records):
    cases=sorted((r for r in records if r['status']=='case'),key=lambda r:hashlib.sha256(('visionairy_momentum_200_400_v1'+r['symbol']+r['date']).encode()).hexdigest())
    controls=[r for r in records if r['status']=='control'];chosen=[];pairs=[]
    def distance(a,b):
        return abs(math.log(a['signal_price']/b['signal_price']))+abs(a['early_gain']-b['early_gain'])/.03+abs(a['elapsed_minutes']-b['elapsed_minutes'])/60+abs(math.log(max(1,a['prefix_dollar_volume'])/max(1,b['prefix_dollar_volume'])))
    for case in cases[:200]:
        if len(controls)<2:break
        matches=sorted(controls,key=lambda c:(c['current_exchange']!=case['current_exchange'],distance(case,c),c['symbol'],c['date']))[:2]
        chosen.append(case)
        for control in matches:
            controls.remove(control);chosen.append(control)
            pairs.append({'case':case['symbol']+' '+case['date'],'control':control['symbol']+' '+control['date'],'distance':distance(case,control),'same_current_exchange':case['current_exchange']==control['current_exchange']})
    return chosen,pairs

def replay(r,policy,delay,slip):
    rows=r['rows'];target=r['signal_at']+delay*60
    candidates=[i for i,b in enumerate(rows) if b['ts']>=target]
    if not candidates:return {'status':'no_entry'}
    i=candidates[0];b=rows[i]
    if b['ts']>target+60:return {'status':'entry_data_gap'}
    entry=b['o']*(1+slip)
    prefix=[x for x in rows if x['ts']+60<=target][-5:]
    if not prefix:return {'status':'no_prefix'}
    stop=min(min(x['l'] for x in prefix),entry*.98)
    risk=(entry-stop)/entry
    if risk>.08:return {'status':'initial_risk_above_8pct'}
    remaining=1.;proceeds=0.;peak=entry;partial=False;exit_at=None;why='session_end';ambiguous=False
    for bar in rows[i:]:
        # Old stop has precedence over any same-bar favorable extreme.
        if bar['l']<=stop:
            proceeds+=remaining*min(stop,bar['o'])*(1-slip);exit_at=bar['ts']+60;remaining=0;why='stop';break
        if policy=='half_at_10_trail_8' and not partial and bar['h']>=entry*1.10:
            proceeds+=.5*entry*1.10*(1-slip);remaining=.5;partial=True
        peak=max(peak,bar['h'])
        if policy in ['trail_8pct','half_at_10_trail_8']:stop=max(stop,peak*.92)
        if policy=='ratchet_10_20_30':
            for threshold,floor in [(1.10,1.03),(1.20,1.10),(1.30,1.20)]:
                if peak>=entry*threshold:stop=max(stop,entry*floor)
        # New stop only becomes active next minute; cannot assume intrabar path.
    if remaining:proceeds+=remaining*rows[-1]['c']*(1-slip);exit_at=rows[-1]['ts']+60
    return {'status':'modeled','return':proceeds/entry-1,'entry_price':entry,'initial_risk':risk,'entry_at':b['ts'],'exit_at':exit_at,'exit_reason':why,'partial':partial,'peak_seen_pct':(peak/entry-1)*100,'missing_minutes':not r['complete_minutes']}

def describe(values):
    if not values:return {'n':0}
    v=sorted(values)
    return {'n':len(v),'mean_pct':statistics.mean(v)*100,'median_pct':statistics.median(v)*100,'positive_fraction_descriptive_only':sum(x>0 for x in v)/len(v),'worst_pct':v[0]*100,'p10_pct':v[int((len(v)-1)*.1)]*100,'best_pct':v[-1]*100}

def main():
    state=read(DIR/'progress.json');plan=read(DIR/'plan.json')
    if state['job']!=len(plan['jobs']):raise RuntimeError('Acquisition incomplete')
    records=read(DIR/'qualification.json');cohort,pairs=match(records)
    config={'policies':POLICIES,'scenarios':SCENARIOS,'initial_stop':'lower of preceding five observed minute lows and 2% below delayed modeled entry; skip risk above8%','scope':'intraday exploratory; final minute close is terminal valuation, not forced live close rule','fills':'assumed adverse per-side slippage, stop gaps worse of open and stop; new stops next minute; partial assumed target touch; no depth/quote proof','fees':'not included beyond slippage; not net executable profit','selection':'200 seeded cases; two greedy matched controls each; no calipers, distances disclosed'}
    frozen=DIR/'replay_plan.json'
    if frozen.exists() and read(frozen)!=config:raise RuntimeError('Replay plan changed')
    write(frozen,config)
    results=[]
    for scenario,delay,slip in SCENARIOS:
        for policy in POLICIES:
            for r in cohort:results.append(dict(symbol=r['symbol'],date=r['date'],label=r['status'],scenario=scenario,policy=policy,**replay(r,policy,delay,slip)))
    aggregates=[]
    for scenario,_,_ in SCENARIOS:
        for policy in POLICIES:
            for label in ['case','control']:
                rows=[r for r in results if r['scenario']==scenario and r['policy']==policy and r['label']==label]
                aggregates.append(dict(scenario=scenario,policy=policy,label=label,exclusions=dict(Counter(r['status'] for r in rows if r['status']!='modeled')),**describe([r['return'] for r in rows if r['status']=='modeled'])))
    report={'status':'exploratory_not_live_validated','cohort_counts':dict(Counter(r['status'] for r in cohort)),'unique_symbols':len({r['symbol'] for r in cohort}),'unique_dates':len({r['date'] for r in cohort}),'complete_minute_counts':dict(Counter(r['status'] for r in cohort if r['complete_minutes'])),'match_distance':describe([p['distance']/100 for p in pairs]),'aggregates':aggregates,'limitations':['Outcome-enriched sample; pooled mean and class ratio are not market performance.','Current inventory, security type and historical identities remain unqualified.','Missing minutes, stale prices, spreads, depth, halts, actual fill latency and fees are not resolved.','Matching without calipers may pair materially different opportunities.','No shared-cash portfolio or untouched-date evaluation; no deployment inference.']}
    write(DIR/'cohort.json',cohort);write(DIR/'matches.json',pairs);write(DIR/'replay_results.json',results);write(DIR/'report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='aggregates'}));print(json.dumps(aggregates[:8]))
if __name__=='__main__':main()
