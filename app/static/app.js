'use strict';
const money=v=>v==null?'Incomplete':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(v));
const stamp=t=>new Date(t*1000).toISOString().replace('T',' ').slice(0,16);
const clean=s=>String(s??'—').replaceAll('_',' ');
function el(tag,text,className){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;}
function cell(row,text){row.append(el('td',text));}
function card(label,value,note){const n=el('article',undefined,'card');n.append(el('div',label,'label'),el('div',value,'value'),el('div',note,'note'));return n;}
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.panel').forEach(p=>p.hidden=p.id!==b.dataset.tab);document.querySelectorAll('[data-tab]').forEach(t=>t.classList.toggle('active',t===b));}));
async function load(){document.getElementById('loading').hidden=false;try{const response=await fetch('/api/research',{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!response.ok)throw Error('Research output is unavailable. Please reload and sign in.');const data=await response.json();const variants=data.portfolio_comparison?.variants??[];if(!variants.length)throw Error('No qualified portfolio comparison is available.');const base=variants[0],l=base.ledger;
document.getElementById('loading').hidden=true;

document.getElementById('demo-cards').append(card('Example starting cash',money(l.initial_cash),'Fabricated scenario - not your balance'),card('Example ending equity',money(l.marked_equity),'Modeled cash + proceeds + positions'),card('Example available cash',money(l.available_cash),'Simulation only'),card('Example net outcome',money(l.realized_net_pnl),'Fabricated result - not your return'));
const tbody=document.getElementById('ledger');let exampleCash=Number(l.initial_cash),exampleUnsettled=0;
l.events.filter(e=>e.kind!=='reserve').forEach(e=>{const row=el('tr'),t=e.terms;const buy=e.kind==='modeled_entry',sell=e.kind==='modeled_exit',settle=e.kind==='settlement';const fee=Number(t.fee??0);const change=buy?-(Number(t.quantity)*Number(t.price)+fee):sell?Number(t.quantity)*Number(t.price)-fee:Number(t.amount??0);if(buy||settle)exampleCash+=change;if(sell)exampleUnsettled+=change;if(settle)exampleUnsettled-=change;cell(row,stamp(e.at));cell(row,buy?'Example buy':sell?'Example sell':clean(e.kind));cell(row,t.symbol??'-');cell(row,t.quantity??'-');cell(row,t.price==null?'-':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:4,maximumFractionDigits:6}).format(Number(t.price)));cell(row,t.fee==null?'-':money(fee));cell(row,money(change));cell(row,money(exampleCash));cell(row,money(exampleUnsettled));cell(row,buy?'Shares purchased; price x quantity plus fee deducted':sell?'Shares sold; proceeds minus fee remain unsettled. '+(t.reason==='time_horizon'?'Experiment holding period ended.':clean(t.reason)):settle?'Previously unsettled sale proceeds become spendable':'Research event');tbody.append(row);});
base.snapshots.forEach(s=>s.reviews.forEach(r=>{const row=el('tr');cell(row,r.symbol);cell(row,stamp(s.assessed_at));const c=el('td');c.append(el('span',r.quantity?'Reserve':'Track / wait',r.quantity?'pill':'pill wait'));row.append(c);cell(row,`${money(r.acquisition_price)} / ${money(r.maximum_entry_price)}`);cell(row,r.quantity);cell(row,money(r.planned_risk));cell(row,r.reasons.map(clean).join(' · '));document.getElementById('opportunities-body').append(row);}));
variants.forEach(v=>{document.getElementById('variants').append(card(v.management.version,money(v.ledger.realized_net_pnl),v.net_account_return==null?'Incomplete account outcome':`${(Number(v.net_account_return)*100).toFixed(3)}% synthetic account outcome`));const row=el('tr');cell(row,v.management.version);cell(row,v.outcome_counts.modeled??0);cell(row,v.outcomes.flatMap(o=>o.fills??[]).filter(f=>f.reason==='partial_profit').length);cell(row,v.outcomes.flatMap(o=>o.stop_changes??[]).length);cell(row,Object.keys(v.ledger.positions).length);document.getElementById('management-body').append(row);});
const vals=base.valuations, nums=vals.map(v=>Number(v.equity)),lo=Math.min(...nums),hi=Math.max(...nums),range=Math.max(hi-lo,.01);const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 1000 160');svg.setAttribute('role','img');svg.setAttribute('aria-label','Synthetic account equity through the declared sessions');const path=document.createElementNS(ns,'polyline');path.setAttribute('points',nums.map((v,i)=>`${20+i*960/Math.max(1,nums.length-1)},${125-(v-lo)/range*100}`).join(' '));path.setAttribute('fill','none');path.setAttribute('stroke','#65dfc0');path.setAttribute('stroke-width','2');svg.append(path);const text=document.createElementNS(ns,'text');text.setAttribute('x','20');text.setAttribute('y','155');text.textContent=`Synthetic marked equity · ${money(lo)} to ${money(hi)} · session gaps compressed`;svg.append(text);document.getElementById('chart').append(svg);
document.getElementById('provenance').textContent=JSON.stringify({notice:data.demo_notice,evidence_origin:data.evidence_origin,input_sha256:base.input_sha256,management_variants:variants.map(v=>({version:v.management.version,sha256:v.management_sha256})),limitations:base.limitations,orders_submitted:0},null,2);
}catch(error){document.getElementById('loading').textContent=error.message;}}
let demoStarted=false;
function ensureDemo(){if(!demoStarted){demoStarted=true;load();}}
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>{if(['opportunities','management','evidence'].includes(b.dataset.tab))ensureDemo();}));
document.getElementById('mechanics-example').addEventListener('toggle',e=>{if(e.target.open)ensureDemo();});

let accountRequestActive=false;
let accountRetryTimer=null;
async function loadAccount(){
 if(accountRequestActive)return;accountRequestActive=true;clearTimeout(accountRetryTimer);
 const cards=document.getElementById('cards'),rows=document.getElementById('account-positions');
 try{
  const response=await fetch('/api/account',{cache:'no-store',signal:AbortSignal.timeout(8000)});if(!response.ok)throw Error('Account data is unavailable');
  const account=await response.json(),connected=account.status==='connected'||account.status==='partial';
  const b=account.balances,positions=account.positions,paper=account.environment==='sandbox';
  const refreshing=account.status==='refreshing'||account.status==='stale';
  if(account.refresh_in_progress)accountRetryTimer=setTimeout(loadAccount,2000);
  cards.replaceChildren(card(paper?'Paper account equity':'Broker-reported equity',b?.total_equity==null?'Unavailable':money(b.total_equity),'Provider balance, not a measured return'),card(paper?'Paper account cash':'Broker-reported cash',b?.total_cash==null?'Unavailable':money(b.total_cash),'Not assumed to equal spendable settled cash'),card('Open positions',Array.isArray(positions)?String(positions.length):'Unavailable',Array.isArray(positions)?'Reported position records':'Account holdings not yet verified'),card('Measured account return','Not measured','Needs a reconciled baseline and cash-flow history'));
  document.getElementById('account-headline').textContent=refreshing?'Refreshing your account - no unverified numbers shown':connected?(paper?'Paper account data connected - not your real-money balance':'Read-only account observations - no real return measured'):'No account data connected. No real returns measured.';
  document.getElementById('account-note').textContent=connected?'These are broker observations. The opportunity scanner is not connected. Synthetic examples remain separate.':(account.reason??Object.values(account.errors??{}).join(' / ')??'Account data unavailable');
  const source=account.sources?.balances;
  document.getElementById('account-source').textContent=source?`Source: Tradier ${account.environment} / balances. Retrieved ${new Date(source.retrieved_at*1000).toISOString()}. Provider valuation timestamp not supplied. Read only.`:(account.reason||Object.values(account.errors??{}).join(' / ')||'Account observations unavailable. No balance assumed.');
  rows.replaceChildren();if(Array.isArray(positions)){if(!positions.length){const row=el('tr');cell(row,'No open positions reported');rows.append(row);}positions.forEach(p=>{const row=el('tr'),q=(account.quotes??[]).find(q=>q.symbol===p.symbol);cell(row,p.symbol);cell(row,p.quantity);cell(row,p.cost_basis==null?'Unavailable':money(p.cost_basis));cell(row,q?.last==null?'Unavailable':money(q.last));cell(row,q?(paper?'Delayed sandbox data':q.trade_date&&Date.now()-q.trade_date<=60000&&Date.now()-q.trade_date>=0?'Recent last trade; check bid/ask before entry':'Last trade is stale or its timestamp is missing'):'Quote unavailable');rows.append(row);});}
 }catch(error){cards.replaceChildren(card('Account connection','Unavailable','Could not retrieve account observations'),card('Account equity','Unavailable','No balance assumed'),card('Positions','Unavailable','No holdings assumed'),card('Measured return','Not measured','No performance claim'));rows.replaceChildren();document.getElementById('account-headline').textContent='Account data unavailable. No real returns measured.';document.getElementById('account-source').textContent=error.name==='TimeoutError'?'The service is slow or waking from idle. The next refresh will retry; no balance is assumed.':error.message;}finally{accountRequestActive=false;}
}
loadAccount();
setInterval(()=>{if(!document.hidden)loadAccount();},30000);

let assessmentTimer=null;
function renderAssessment(data){
 const status=document.getElementById('assessment-status'),root=document.getElementById('assessment-result');
 root.replaceChildren();clearTimeout(assessmentTimer);
 const running=['running','queued'].includes(data.status);
 document.getElementById('assessment-start').disabled=running;
 if(running){status.textContent=`Example assessment in progress: ${clean(data.stage??'preparing evidence')}. No trade will be submitted.`;assessmentTimer=setTimeout(loadAssessment,3000);return;}
 if(data.status!=='complete'){status.textContent=data.reason??(data.status==='not_started'?'Ready to run a synthetic example.':'Saved assessment is unavailable.');return;}
 status.textContent='Saved synthetic assessment - not a current market recommendation.';
 const assessment=data.assessment,chosen=data.selected_option;
 root.append(el('h3',chosen?`Paper review: ${chosen.symbol}`:'Retain cash'));
 const options=el('div');
 (data.options??[]).forEach(o=>options.append(el('p',`${o.symbol}: ${o.quantity} modeled shares; capital ${money(o.entry_cash)}; planned risk ${money(o.planned_risk)}. Target geometry is experimental.`)));
 root.append(options);
 (assessment.claims??[]).forEach(c=>{const article=el('article');article.append(el('strong',`${clean(c.kind)} - ${clean(c.support)} support`),el('p',c.text));(c.citations??[]).forEach(s=>article.append(el('p',`${s.source_id}: ${s.quote}`,'muted')));root.append(article);});
 root.append(el('h3','What remains unknown'));
 (assessment.missing_information??[]).forEach(t=>root.append(el('p',t)));
 root.append(el('p',`Engine baseline comparison: ${data.baseline_agreement?'same paper option':'different choice'}. Incremental trading value has not been established.`));
 const cost=data.cost_complete?`$${Number(data.reported_cost_usd).toFixed(6)}`:'Not fully reconciled';
 root.append(el('p',`Assessment time: ${(data.elapsed_ms/1000).toFixed(1)} seconds. Reported API cost: ${cost}. Same evidence reuses this saved result.`,'muted'));
 root.append(el('p','Sources and model responses are retained for evaluation. No learning change or strategy adoption occurred. Citations show stored evidence; conclusions still require evaluation.','muted'));
}
async function loadAssessment(){try{const r=await fetch('/api/assessment',{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error();renderAssessment(await r.json());}catch{document.getElementById('assessment-status').textContent='Assessment status could not be loaded. No automatic paid retry will run.';document.getElementById('assessment-start').disabled=false;}}
document.getElementById('assessment-start').addEventListener('click',async()=>{
 document.getElementById('assessment-start').disabled=true;
 document.getElementById('assessment-status').textContent='Preparing the synthetic evidence bundle...';
 try{const r=await fetch('/api/assessment/start',{method:'POST',headers:{'Content-Type':'application/json','X-Ghost-Review':'1'},body:JSON.stringify({kind:'synthetic_ghost_review'}),signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error();renderAssessment(await r.json());}
 catch{document.getElementById('assessment-status').textContent='The start response was lost. Checking the saved status before any retry.';await loadAssessment();}
});
loadAssessment();
