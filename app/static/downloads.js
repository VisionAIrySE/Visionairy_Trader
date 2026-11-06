'use strict';
let busy=false;
async function refresh(){
 if(busy)return;busy=true;
 const state=document.getElementById('state'),details=document.getElementById('details');
 try{
  const response=await fetch('/api/download-status',{cache:'no-store',signal:AbortSignal.timeout(20000)});
  if(!response.ok)throw Error();const data=await response.json();
  const groups=data.groups,total=groups.reduce((n,g)=>n+g.batches,0);
  const count=s=>groups.find(g=>g.status===s)?.batches??0;
  state.textContent=!total?'No download batches have been queued.':count('complete')===total?'Download complete. Trading analysis is a separate step.':count('failed')?'Some batches stopped and need attention.':count('running')?'Download batches are being processed.':'Batches are waiting for the worker or their next retry.';
  details.replaceChildren();
  for(const text of [`Completed: ${count('complete')} of ${total} batches`,`Waiting: ${count('queued')} · Processing: ${count('running')} · Stopped: ${count('failed')}`,`Saved pages: ${groups.reduce((n,g)=>n+g.pages,0)}`,`Expired worker leases awaiting recovery: ${groups.reduce((n,g)=>n+g.expired_leases,0)}`]){const p=document.createElement('p');p.textContent=text;details.append(p);}
  const success=Math.max(0,...groups.map(g=>g.last_success??0));
  const p=document.createElement('p');p.textContent=success?'Last successful save: '+new Date(success*1000).toLocaleString():'No successful save reported yet.';details.append(p);
  for(const error of data.errors){const p=document.createElement('p');p.textContent=`${error.batches} batches: ${error.category}`;details.append(p);}
  document.getElementById('checked').textContent='Status checked: '+new Date(data.checked_at).toLocaleString();
 }catch{state.textContent='Cannot read current status. Previously displayed numbers may be stale; completion is unknown.';}
 finally{busy=false;}
}
document.getElementById('refresh').addEventListener('click',refresh);refresh();setInterval(refresh,15000);
