"""Reconstruct early observations; outcome labels never enter signal features."""
import json, math, hashlib
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/'data/momentum_study/minutes_v1'
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p,x): p.write_text(json.dumps(x,indent=2),encoding='utf-8')

def qualify(symbol,date,bars,actions):
    offset=5 if date<'2025-03-09' else 4
    start=datetime.fromisoformat(f'{date}T{9+offset}:30:00+00:00').timestamp()
    end=start+390*60
    rows=sorted((dict(b,ts=datetime.fromisoformat(b['t'].replace('Z','+00:00')).timestamp()) for b in bars),key=lambda b:b['ts'])
    rows=[b for b in rows if start<=b['ts']<end]
    base={'symbol':symbol,'date':date,'bars':len(rows)}
    def reject(reason): return dict(base,status=reason)
    if (symbol,date) in actions:return reject('corporate_action_day')
    if not rows:return reject('no_regular_session_data')
    if len({b['ts'] for b in rows})!=len(rows):return reject('duplicate_timestamps')
    if any(not all(math.isfinite(b[k]) for k in ['o','h','l','c','v']) or not (0<b['l']<=min(b['o'],b['c'])<=max(b['o'],b['c'])<=b['h']) or b['v']<0 for b in rows):return reject('invalid_ohlcv')
    if rows[0]['ts']!=start or rows[-1]['ts']!=end-60:return reject('missing_open_or_close_minute')
    opening=rows[0]['o']
    signal=next((i for i,b in enumerate(rows) if b['ts']+60<=start+3600 and b['c']>=opening*1.03),None)
    if signal is None:return reject('no_early_signal')
    b=rows[signal];later=rows[signal+1:]
    if not later:return reject('no_followup')
    extension=max(r['h'] for r in later)/b['c']-1
    label='case' if extension>=.10 else 'control' if rows[-1]['c']<=b['c'] else 'middle'
    return dict(base,status=label,signal_index=signal,signal_at=b['ts']+60,signal_price=b['c'],early_gain=b['c']/opening-1,elapsed_minutes=(b['ts']+60-start)/60,
      prefix_dollar_volume=sum(r['v']*r.get('vw',r['c']) for r in rows[:signal+1]),extension=extension,session_return=rows[-1]['c']/b['c']-1,
      complete_minutes=len(rows)==390,maximum_missing_gap_minutes=max((rows[i]['ts']-rows[i-1]['ts'])/60-1 for i in range(1,len(rows))),rows=rows)

def main():
    plan=read(DIR/'plan.json');state=read(DIR/'progress.json');group=defaultdict(list)
    for p in state['pages']:
        receipt=read(DIR/p['file']);date=plan['jobs'][receipt['job']]['date']
        for symbol,rows in receipt['payload']['bars'].items():group[symbol,date].extend(rows)
    ca=read(ROOT/'data/momentum_study/corporate_actions_probe.json')['payload']['corporate_actions'];actions=set()
    for records in ca.values():
        for a in records:
            for symbol in [a.get('symbol'),a.get('old_symbol'),a.get('new_symbol')]:
                if symbol:actions.add((symbol,a.get('ex_date',a.get('process_date'))))
    available={c['date'] for job in plan['jobs'][:state['job']] for c in [job]}
    completed={(s,j['date']) for j in plan['jobs'][:state['job']] for s in j['symbols']}
    result=[qualify(c['symbol'],c['date'],group[c['symbol'],c['date']],actions) for c in plan['candidates'] if (c['symbol'],c['date']) in completed]
    inventory={a['symbol']:a for a in read(ROOT/'data/momentum_study/alpaca_assets.json')['assets']}
    for r in result:
        a=inventory.get(r['symbol'],{});r['current_exchange']=a.get('exchange');r['current_name']=a.get('name');r['security_type_historical_identity_qualified']=False
    summary={'completed_jobs':state['job'],'total_jobs':len(plan['jobs']),'counts':dict(Counter(r['status'] for r in result)),
      'complete_minute_counts':dict(Counter(r['status'] for r in result if r.get('complete_minutes'))),'final_200_400_selected':False}
    write(DIR/'qualification.json',result);write(DIR/'qualification_summary.json',summary);print(json.dumps(summary))
if __name__=='__main__':main()
