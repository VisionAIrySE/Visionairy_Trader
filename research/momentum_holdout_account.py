"""Conservative cash diagnostic, not broker settlement or intraday equity simulation."""
import math
from collections import Counter
from momentum_cohort import ROOT,read,write
from momentum_discovery_replay import POLICIES,SCENARIOS

def simulate(rows):
    cash=1000.;pending=0.;positions={};trades=[];skips=Counter();day=None;peak=1000.;worst=0.
    events=[]
    for i,r in enumerate(rows):
        events.extend([(r['entry_at'],1,i,r),(r['exit_at'],0,i,r)])
    for at,kind,i,r in sorted(events,key=lambda x:(x[0],x[1],x[3]['symbol'],x[2])):
        if day!=r['date']:
            cash+=pending;pending=0.;day=r['date']
        if kind==0:
            if i not in positions:continue
            cost,risk=positions.pop(i);profit=cost*r['return'];pending+=cost+profit
            trades.append(dict(symbol=r['symbol'],date=r['date'],cost=cost,pnl=profit,return_pct=r['return']*100))
            equity=cash+pending+sum(p[0] for p in positions.values());peak=max(peak,equity);worst=min(worst,equity/peak-1)
            continue
        equity=cash+pending+sum(p[0] for p in positions.values())
        existing_risk=sum(p[1] for p in positions.values());remaining_risk=max(0,equity*.05-existing_risk)
        price=r['entry_price'];risk_per_share=price*r['initial_risk']
        qty=math.floor(min(cash,100)/price)
        if risk_per_share>0:qty=min(qty,math.floor(min(equity*.01,remaining_risk)/risk_per_share))
        if qty<1:skips['cash_position_or_risk_limit']+=1;continue
        if any(rows[j]['symbol']==r['symbol'] for j in positions):skips['already_holding_symbol']+=1;continue
        cost=qty*price;cash-=cost;positions[i]=(cost,qty*risk_per_share)
    if positions:raise ValueError('Unclosed modeled positions')
    return {'initial_cash':1000,'final_value':cash+pending,'net_pnl':cash+pending-1000,'trades':len(trades),'skips':dict(skips),'closed_event_drawdown_pct':worst*100,'trade_records':trades}

def main():
    d=ROOT/'data/momentum_study/holdout_v1';plan={'version':1,'initial_cash':1000,'position_cap':100,'risk_per_trade':.01,'aggregate_planned_risk':.05,'allocation':'first entry time, symbol tie-break; whole shares','settlement':'sale proceeds unavailable until next observed study date; conservative approximation, not verified broker settlement','partials':'all proceeds held until final modeled exit','scope':'activity-only, quotes not qualified; no real orders; drawdown at realized exit events, not intraday marked equity'}
    path=d/'account_diagnostic_plan.json'
    if path.exists() and read(path)!=plan:raise ValueError('Plan changed')
    write(path,plan)
    records=read(d/'holdout_replay_results.json');reports=[]
    for scenario,_,_ in SCENARIOS:
        for policy in POLICIES:
            rows=[r for r in records if r['status']=='modeled' and r['activity_pass'] and r['scenario']==scenario and r['policy']==policy]
            reports.append(dict(scenario=scenario,policy=policy,**simulate(rows)))
    write(d/'account_diagnostic_results.json',reports)
    print([{k:v for k,v in r.items() if k!='trade_records'} for r in reports])
if __name__=='__main__':main()
