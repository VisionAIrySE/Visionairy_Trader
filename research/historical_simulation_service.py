"""Private bounded historical trade/portfolio results, separate from live candidates."""
from market_monitor import unpack,digest
from model_assessment import HostedAssessmentStore

class HistoricalSimulationService:
    def __init__(self,store=None):self.store=store
    def latest(self,page=0,scenario=None,view='trades'):
        if type(page) is not int or not 0<=page<=10000 or view not in ('trades','reviews'):raise ValueError('Bounded historical view required')
        try:
            if self.store is None:self.store=HostedAssessmentStore()
            saved=self.store.call('historical_simulation_get',{})
            if not saved.get('packed_report'):return {'status':'not_started'}
            report=unpack(saved['packed_report'])
            if digest(report)!=saved['sha256']:raise ValueError('Historical report identity mismatch')
            scenarios=report['scenarios'];selected=scenario or report['primary_scenario']
            if selected not in {s['name'] for s in scenarios}:return {'status':'invalid_scenario'}
            summaries=[]
            for case in scenarios:
                portfolio=case['portfolio'];ledger=portfolio['ledger']
                summaries.append(dict(name=case['name'],status=portfolio['status'],summary=case['portfolio_summary'],
                    initial_cash=ledger['initial_cash'],ending_equity=ledger['marked_equity'],realized_net_pnl=ledger['realized_net_pnl'],
                    return_fraction=portfolio['net_account_return'],assumptions=case['assumptions'],
                    eligible_patterns=case['portfolio_eligible_patterns'],excluded_patterns=case['portfolio_excluded_patterns'],
                    independent_summary=case['independent_summary']))
            case=next(s for s in scenarios if s['name']==selected)
            rows=[r for r in case['portfolio']['outcomes'] if (r.get('quantity',0)>0 if view=='trades' else r['status']!='modeled')]
            return dict(status='historical_trade_simulation',scenario=selected,view=view,page=page,page_size=25,total=len(rows),
                rows=rows[page*25:(page+1)*25],scenarios=summaries,source_coverage=report['source_manifest']['coverage'],
                period=dict(start=report['source_manifest']['calendar'][0]['open'],end=report['source_manifest']['calendar'][-1]['close']),
                spec=report['spec'],spec_sha256=report['spec_sha256'],limitations=report['limitations'],
                evidence=report['evidence'],orders_submitted=0)
        except Exception:return {'status':'unavailable','orders_submitted':0}
