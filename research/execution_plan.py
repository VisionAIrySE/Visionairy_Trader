"""Dependency/evidence controller for delivery. No trading or arbitrary commands.

The controller checks receipt structure and local artifact identity, not the truth
of an experiment or user authorization. Semantic acceptance remains explicit work.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_PLAN=ROOT/'docs/EXECUTION_PLAN.json'
DEFAULT_STATE=ROOT/'data/execution_state.json'


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def validate(plan):
    tasks=plan['tasks'];by_id={t['id']:t for t in tasks}
    if len(by_id)!=len(tasks):raise ValueError('Duplicate task identity')
    for t in tasks:
        if not t['steps'] or not t['deliverable'] or not t['acceptance']:
            raise ValueError('Task missing executable work or acceptance')
        if any(dep not in by_id for dep in t['depends_on']):raise ValueError('Unknown dependency')
        ids=[c['id'] for c in t['acceptance']]
        if len(set(ids))!=len(ids):raise ValueError('Duplicate acceptance identity')
    visiting=set();visited=set()
    def visit(key):
        if key in visiting:raise ValueError('Dependency cycle')
        if key in visited:return
        visiting.add(key)
        for dep in by_id[key]['depends_on']:visit(dep)
        visiting.remove(key);visited.add(key)
    for key in by_id:visit(key)
    expected={f'A{i:02}' for i in range(1,56)}|{'A06a'}
    if set(plan['requirements'])!=expected:raise ValueError('Accepted requirement omitted')
    from hypothesis_readiness import HYPOTHESES
    if set(plan['hypotheses'])!={h[0] for h in HYPOTHESES}:raise ValueError('Accepted hypothesis family omitted')
    if {d['id'] for d in plan['open_decisions']}!={f'O{i:02}' for i in range(1,12)}:
        raise ValueError('Open decision omitted')
    links=list(plan['requirements'].values())+[h['tasks'] for h in plan['hypotheses'].values()]
    links += [d['tasks'] for d in plan['open_decisions']]+[m['requires'] for m in plan['milestones']]
    if any(not ids or any(i not in by_id for i in ids) for ids in links):raise ValueError('Missing coverage task link')
    return by_id


def empty_state(plan):return dict(plan_sha256=fingerprint(plan),events=[])


def verify_receipt(task,receipt,plan,root=ROOT):
    if task['authority']!='research':
        raise ValueError('Separate authorization workflow required; a delivery receipt grants no order authority')
    if receipt.get('task_id')!=task['id'] or receipt.get('plan_sha256')!=fingerprint(plan):
        raise ValueError('Receipt does not identify this exact plan/task')
    checks=receipt.get('checks',[])
    if {c.get('criterion_id') for c in checks}!={c['id'] for c in task['acceptance']} or len(checks)!=len(task['acceptance']):
        raise ValueError('Every acceptance criterion needs one evidence check')
    root=Path(root).resolve()
    for check in checks:
        if check.get('result')!='pass' or not check.get('finding'):
            raise ValueError('Passing finding required for each criterion')
        path=Path(check['artifact'])
        path=(root/path).resolve() if not path.is_absolute() else path.resolve()
        if not path.is_relative_to(root):raise ValueError('Evidence artifact outside project')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=check.get('sha256'):
            raise ValueError('Evidence content changed')


def status(plan,state,root=ROOT):
    by_id=validate(plan)
    if state.get('plan_sha256')!=fingerprint(plan):raise ValueError('State belongs to a different plan revision; reconcile explicitly')
    done=set();blocked={}
    for event in state['events']:
        key=event['task_id']
        if key not in by_id:raise ValueError('Unknown state task')
        if event['action']=='complete':
            if not set(by_id[key]['depends_on'])<=done:raise ValueError('Task completed before dependencies')
            verify_receipt(by_id[key],event['receipt'],plan,root)
            done.add(key);blocked.pop(key,None)
        elif event['action']=='block':
            if not event.get('reason'):raise ValueError('Blocked task needs a reason')
            if key in done:raise ValueError('Completed task cannot be silently blocked')
            blocked[key]=event['reason']
        elif event['action']=='resume':blocked.pop(key,None)
        else:raise ValueError('Unknown state action')
    ready=[t for t in plan['tasks'] if t['id'] not in done|set(blocked) and
           t['authority']=='research' and set(t['depends_on'])<=done]
    gates=[t['id'] for t in plan['tasks'] if t['authority']!='research']
    return dict(plan_id=plan['plan_id'],revision=plan['revision'],plan_sha256=fingerprint(plan),
        completed=sorted(done),blocked=blocked,next_tasks=ready,
        milestones={m['id']:all(t in done for t in m['requires']) for m in plan['milestones']},
        separate_authorization_tasks=gates,
        operating_platform_ready=all(t in done for t in ('Q01','A01','A02','A03','A04','U04')),
        strategy_profitability_demonstrated=False,live_order_authority=False)


def render(plan):
    lines=['# VisionAIry Trader: executable delivery plan','',
        'This is the current work queue. The accepted private SOT governs intent and authority. Existing status documents remain historical evidence; this plan governs the order of remaining delivery.','',
        '**Target:** '+plan['intent'],'',
        '**Current authority:** research/internal ghost simulation and existing authorized implementation/deployment. No broker orders, funding, purchases, paid upgrades or automatic standing-risk/strategy adoption.','',
        '**First concrete result:** record a real historical exploratory experiment in the hosted database and show its simulated buys, sells, losses/nonfills and net results. Full-market/news/AI completion is not a prerequisite for a supported limited test.','',
        '## How execution proceeds','',
        'The assistant owns implementation and verification. The user is not asked to reconstruct settled decisions or choose routine implementation details. A fresh conversation reads this file, its JSON task graph and the current private receipt state, then continues the next ready task.','',
        '```powershell',
        'python research/execution_plan.py validate',
        'python research/execution_plan.py next --limit 3',
        'python research/execution_plan.py status',
        'python research/execution_plan.py record --task TASK_ID --receipt data/TASK_ID_receipt.json',
        'python research/execution_plan.py block --task TASK_ID --reason "Specific blocker and remedy"',
        'python research/execution_plan.py resume --task TASK_ID',
        '```','',
        'A receipt must name the exact plan hash/task and contain one passing finding and content-hashed local evidence artifact per acceptance criterion. Dependencies must already be complete. Artifacts/receipts remain private under data/. Changed evidence invalidates completion on the next status check. A count of passing software tests alone does not satisfy integration, market-evidence or operating gates. The controller validates identity/structure; the assistant must assess the actual evidence. It does not submit jobs/orders or execute arbitrary command strings. Separate order-authorization tasks cannot be completed by this generic receipt command.','',
        'At each task: intent → listed requirements → implementation → checks and actual evidence → acceptance review → recorded completion → next ready task. If blocked, preserve the reason, retry temporary failures appropriately and continue independent authorized work. Progress updates remain required at least every 60 seconds.','',
        '## Existing groundwork to retain','']
    lines += ['- '+s for s in plan['baseline_completed']]
    lines += ['', '## Delivery milestones','', '| Milestone | Required tasks | Meaning |','|---|---|---|']
    lines += ['| '+m['id']+' | '+', '.join(m['requires'])+' | '+m['claim']+' |' for m in plan['milestones']]
    lines += ['', '## Execution rules','']+['- '+s for s in plan['rules']]
    lines += ['', '## Model assignments must be earned','',
        '| Job | Intended approach | Gate |','|---|---|---|',
        '| Prices, scanning math, sizing, risk, replay, cash and order state | Deterministic validated code | LLM cannot override calculations or grant authority |',
        '| News extraction and classification | Evaluate a suitably small/fast model | Accuracy/schema/source/latency/cost benchmark |',
        '| Ambiguous catalyst/context reasoning | Evaluate a stronger reasoning model where it adds value | Cited evidence and measured improvement justify added cost |',
        '| Search/retrieval | Evaluate embeddings/retrieval independently | Relevant sources, versioning and retrieval quality |',
        '| User explanations | Grounded model output from reconciled records | Numbers supplied by code; no invented forecast or advice authority |','',
        'A bounded synthetic ghost-assessment route now connects the benchmark-selected news/research models with retained hosted receipts. LLM01/LLM02 remain subject to all their evidence gates, including provider/privacy qualification and independent incremental decision-value evaluation; this example does not complete them. No model name, price or superiority is invented here. The total operating budget remains $25/month unless a specific change is approved.','',
        '## Detailed tasks','']
    phase=None
    for t in plan['tasks']:
        if phase!=t['phase']:
            phase=t['phase'];lines += ['### '+phase,'']
        lines += ['#### '+t['id']+' — '+t['title'],'',
            '**Depends on:** '+(', '.join(t['depends_on']) or 'Ready to start')+'. **Authority:** '+t['authority']+'. **Owner:** assistant.','',
            '**Reuse/current boundary:** '+t['reuse'],'',
            '**Steps:**']+['- '+s for s in t['steps']]
        lines += ['', '**Deliverable:** '+t['deliverable'],'', '**Accept only when:**']+['- '+c['id']+': '+c['criterion'] for c in t['acceptance']]+['']
    lines += ['## Accepted-scope coverage','',
        'All 56 accepted/context items A01–A55 plus A06a, all O01–O11 decisions and all 18 current hypothesis families are mapped in EXECUTION_PLAN.json. Validation fails if any mapping is missing or references an unknown task. The catalog preserves the technical subfamilies, catalysts, market context, management, execution, allocation and learning; it does not redefine the platform as only quiet-to-active detection.','',
        '## Meaning of complete','',
        'The delivery plan can be complete while many tasks remain pending. A valid experiment can finish with no edge, negative returns or insufficient evidence. A hosted application can function while a strategy fails. Operating ghost readiness, candidate effectiveness, broker-paper authority and live authority remain separate gates. No execution-plan receipt establishes future ROI.','']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['validate','next','status','record','block','resume','render'])
    p.add_argument('--plan',type=Path,default=DEFAULT_PLAN);p.add_argument('--state',type=Path,default=DEFAULT_STATE)
    p.add_argument('--limit',type=int,default=3);p.add_argument('--task');p.add_argument('--receipt',type=Path);p.add_argument('--reason')
    args=p.parse_args();plan=json.loads(args.plan.read_text(encoding='utf-8'));validate(plan)
    state=json.loads(args.state.read_text(encoding='utf-8')) if args.state.exists() else empty_state(plan)
    report=status(plan,state)
    if args.action=='render':
        target=args.plan.with_suffix('.md');target.write_text(render(plan),encoding='utf-8');print(str(target));return
    if args.action in ('record','block','resume'):
        if args.task not in {t['id'] for t in plan['tasks']}:raise ValueError('Known task required')
        event=dict(task_id=args.task,at=datetime.now(timezone.utc).isoformat(),action={'record':'complete','block':'block','resume':'resume'}[args.action])
        if args.action=='record':
            if not args.receipt:raise ValueError('Evidence receipt required')
            if args.task in report['completed']:raise ValueError('Task already complete')
            event['receipt']=json.loads(args.receipt.read_text(encoding='utf-8'))
        if args.action=='block':event['reason']=args.reason
        state['events'].append(event);report=status(plan,state)
        args.state.parent.mkdir(parents=True,exist_ok=True)
        temp=args.state.with_suffix('.tmp');temp.write_text(json.dumps(state,indent=2),encoding='utf-8');temp.replace(args.state)
    if args.action=='validate':report=dict(valid=True,tasks=len(plan['tasks']),requirements=len(plan['requirements']),hypotheses=len(plan['hypotheses']),plan_sha256=fingerprint(plan))
    if args.action=='next':report=report['next_tasks'][:args.limit]
    elif args.action=='status':report['next_tasks']=[dict(id=t['id'],title=t['title']) for t in report['next_tasks']]
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
