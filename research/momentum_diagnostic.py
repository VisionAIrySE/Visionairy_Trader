"""Post-run signal-strength explanation; never retunes the frozen experiment."""
from decimal import Decimal as D
from statistics import median
from market_monitor import digest

def supplement(report,histories):
    primary=next(s for s in report['scenarios'] if s['name']==report['primary_scenario'])
    selected={r['event_id'] for r in primary['portfolio']['outcomes'] if r['status']=='modeled'}
    rows=[]
    for case in primary['independent_cases']:
        bars=histories[case['symbol']];at=case['setup_at']
        prefix=[b for b in bars if b.timestamp+300<=at]
        if len(prefix)<4:continue
        current=prefix[-1];prior=prefix[-4:-1]
        mean_volume=sum((b.volume for b in prior),D(0))/3
        rows.append(dict(event_id=case['event_id'],symbol=case['symbol'],setup=case['setup'],
            available_at=at,price_change_15min_pct=str((current.close/prior[0].close-1)*100),
            recent_bar_volume_ratio=str(current.volume/mean_volume) if mean_volume else None,
            portfolio_eligible=report['portfolio_eligibility'][case['event_id']],selected=case['event_id'] in selected))
    eligible=[r for r in rows if r['portfolio_eligible']]
    return dict(role='post_outcome_explanation_not_new_selection_rule',original_report_sha256=digest(report),
        measured_patterns=len(rows),portfolio_eligible_patterns=len(eligible),
        eligible_median_15min_change_pct=str(median(D(r['price_change_15min_pct']) for r in eligible)) if eligible else None,
        eligible_count_by_minimum_rise_pct={str(cut):sum(D(r['price_change_15min_pct'])>=cut for r in eligible)
            for cut in (D('.5'),D(1),D(2),D(3),D(5))},rows=rows,
        limitation='Measurement bins explain the inspected run; no threshold is selected or profitability inferred')
