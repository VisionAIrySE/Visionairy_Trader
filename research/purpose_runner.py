"""Run the joined research path from an explicit, source-pinned data bundle.

No fixed roster, data acquisition, credentials or brokerage operations. A bundle
is not qualified by its filename; the joined coverage/intent gate still applies.
"""
import argparse
from decimal import Decimal as D
import json
from pathlib import Path

from discovery_selection import SelectionPolicy
from setup_detection import MarketBar,SetupPolicy,OpportunityPolicy
from managed_replay import ReplayPolicy
from purpose_pipeline import run_research


def run_bundle(bundle):
    series={}
    for symbol,rows in bundle['series'].items():
        series[symbol]=[MarketBar(timestamp=r['timestamp'],session=r['session'],minute=r['minute'],
            open=D(str(r['open'])),high=D(str(r['high'])),low=D(str(r['low'])),
            close=D(str(r['close'])),volume=D(str(r['volume'])),session_minutes=r['session_minutes']) for r in rows]
    result=run_research(bundle['universe'],series,SelectionPolicy(**bundle['selection_policy']),
                        SetupPolicy(**bundle['setup_policy']),OpportunityPolicy(**bundle['opportunity_policy']),
                        ReplayPolicy(**bundle['replay_policy']),bundle['evaluation_start'],bundle['evaluation_end'],
                        bundle['quotes'],bundle['target_hypotheses'],bundle['scenario_equity'],
                        bundle['scenario_settled_cash'])
    experiment=bundle.get('portfolio_experiment')
    if experiment is not None and result['coverage']['target_study_ready']:
        from portfolio_replay import compare_management
        result['portfolio_comparison']=compare_management(result['setups'],result['assessments'],series,
            bundle['universe']['session_windows'],bundle['universe']['source_sha256'],
            bundle['scenario_equity'],bundle['scenario_settled_cash'],
            OpportunityPolicy(**bundle['opportunity_policy']),ReplayPolicy(**bundle['replay_policy']),
            experiment['settlement_sessions'],experiment['management_variants'])
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Explicit purpose-aligned conditional research, not trading')
    parser.add_argument('--bundle',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    report=run_bundle(json.loads(Path(args.bundle).read_text(encoding='utf-8')))
    Path(args.output).write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('status','evidence_origin','coverage','setup_counts',
                         'outcome_counts','operational_assistant_ready','profitable_strategy_demonstrated')},indent=2))
