const $ = s => document.querySelector(s);
let state = null, selected = null, view = 'overview';
const escapeHtml = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let toastTimer;
function toast(message, error=false) {const el=$('#toast');el.textContent=message;el.className='toast show'+(error?' error':'');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('show'),6000);}
async function api(path, data) {
  const response=await fetch(path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':$('meta[name="csrf-token"]').content},body:data===undefined?undefined:JSON.stringify(data)});
  const result=await response.json();if(!response.ok)throw Error(result.error || 'Request failed');return result;
}
function date(text) {if(!text || text==='Never')return 'never';const d=new Date(text.includes('T')?text:text.replace(' ','T')+'Z');return isNaN(d)?text:d.toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});}
function showView(next) {
  view=next;
  document.querySelectorAll('.nav').forEach(el=>el.classList.toggle('active',el.dataset.view===view));
  ['overview','reels','activity','connection'].forEach(id=>$('#'+id+'-view').classList.toggle('hidden',view!=='overview'?id!==view:!['overview','reels','activity'].includes(id)));
  const titles={overview:['Overview','Your growth, on autopilot.','The right reply. The right moment. Every time.'],reels:['Reels & automations','Good content. Great conversations.','Set a personal reply for every reel.'],activity:['Activity','Every conversation counts.','A clear view of what your automations are doing.'],connection:['Connection','Let’s get you connected.','Your Instagram, with a little less busywork.']};
  $('#breadcrumb').textContent=titles[view][0];$('#page-title').textContent=titles[view][1];$('#page-subtitle').textContent=titles[view][2];
}
function render() {
  $('#mode').textContent=state.mode==='demo'?'Demo mode':'Live account';$('#profile-mode').textContent=state.mode==='demo'?'Demo workspace':'API connected';$('#demo-banner').classList.toggle('hidden',state.mode!=='demo');
  $('#stat-reels').textContent=state.reels.length;$('#reel-count').textContent=state.reels.length;$('#nav-count').textContent=state.reels.length;$('#stat-active').textContent=state.reels.filter(r=>r.enabled).length;
  $('#stat-sent').textContent=state.actions.filter(a=>['completed','dm_sent'].includes(a.status)).length;$('#stat-skipped').textContent=state.actions.filter(a=>a.status==='skipped').length;
  $('#background').classList.toggle('on',state.background);$('#background').setAttribute('aria-checked',state.background);$('#bg-label').textContent=state.background?'Background running':'Background paused';$('#last-sync').textContent='Last synced: '+date(state.last_sync);
  const words=['small details,\nbig feelings.','a closer\nlook.','behind\nthe scenes.'];
  $('#reel-grid').innerHTML=state.reels.map((r,i)=>`<article class="reel-card"><div class="reel-art art-${i%3}"><span class="reel-badge ${r.enabled?'active-badge':''}">${r.enabled?'● AUTOMATION ON':'○ NOT CONFIGURED'}</span><span class="art-word">${words[i%3].replace('\n','<br>')}</span><span class="reel-play">▷</span></div><div class="reel-body"><h3>${escapeHtml(r.caption)}</h3><div class="reel-meta"><span>${date(r.timestamp)}</span>${r.url&&/^https:\/\/(www\.)?instagram\.com\//.test(r.url)?`<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">View reel ↗</a>`:'<span>Sample reel</span>'}</div><div class="keyword-tags">${r.keywords.split(',').filter(k=>k.trim()).slice(0,5).map(k=>`<span>${escapeHtml(k.trim())}</span>`).join('')}</div><button class="button secondary configure" data-id="${escapeHtml(r.id)}">${r.enabled?'Edit automation':'＋ Configure automation'} <span>↗</span></button></div></article>`).join('') || '<div class="empty">No reels yet. Connect your account, then sync your reels.</div>';
  const labels={completed:state.mode==='demo'?'Simulated':'Delivered',skipped:'Skipped',review:'Needs review',sending:'Attempt reserved',dm_sent:'DM sent'};
  $('#activity').innerHTML=state.actions.map(a=>`<tr><td><strong>@${escapeHtml(a.username)}</strong><small>${escapeHtml(a.comment)}</small></td><td><span class="status ${escapeHtml(a.status)}">${labels[a.status]||escapeHtml(a.status)}</span></td><td>${escapeHtml(a.detail)}</td><td>${date(a.updated)}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">Your conversations will appear here. Configure a reel and start your first automation.</td></tr>';
  $('#connection-status').textContent=state.mode==='demo'?'○ Demo mode · No credentials configured. All sends are simulated.':'● Live credentials configured · Use Sync reels to verify API access.';
  document.querySelectorAll('.reel-body').forEach((body,i)=>{const button=document.createElement('button');button.className='button secondary analytics-button';button.textContent='▥ View analytics';button.onclick=()=>openAnalytics(state.reels[i]);body.appendChild(button);});
}
let analyticsReel=null, analyticsRequest=0;
async function openAnalytics(reel) {
  analyticsReel=reel;const requestId=++analyticsRequest;
  $('#analytics-caption').textContent=reel.caption;
  if(!$('#analytics-dialog').open)$('#analytics-dialog').showModal();
  $('#analytics-content').textContent='Loading Instagram analytics…';$('#refresh-analytics').disabled=true;
  try {
    const data=await api('/api/reels/'+encodeURIComponent(reel.id)+'/analytics');
    if(requestId!==analyticsRequest)return;
    const labels={views:'Views',reach:'Accounts reached',likes:'Likes',comments:'Comments',saved:'Saves',shares:'Shares'};
    $('#analytics-content').innerHTML=`<p class="analytics-caption">${data.mode==='demo'?'SAMPLE DATA':'INSTAGRAM DATA'} · Updated ${date(data.fetched_at)} · Cached for 60 seconds</p><div class="analytics-grid">${Object.entries(labels).map(([key,label])=>`<div class="analytics-metric"><small>${label}</small><strong>${data.metrics[key]===null?'—':Number(data.metrics[key]).toLocaleString()}</strong>${data.metrics[key]===null?'<small>Unavailable</small>':''}</div>`).join('')}</div><h3>Automation on this reel</h3><p class="analytics-summary">${data.automation.dm_sent} confirmed DMs · ${data.automation.completed} completed flows<br>${data.automation.skipped} skipped comments · ${data.automation.review} needing review<br>Comments readable by app: ${data.readable_comments===null?'Unavailable':data.readable_comments}</p>${data.notes.map(note=>`<p class="analytics-notice">${escapeHtml(note)}</p>`).join('')}`;
  }catch(e){if(requestId===analyticsRequest)$('#analytics-content').textContent=e.message;}
  finally{if(requestId===analyticsRequest)$('#refresh-analytics').disabled=false;}
}
$('#close-analytics').onclick=()=>$('#analytics-dialog').close();
$('#refresh-analytics').onclick=()=>openAnalytics(analyticsReel);
async function refresh(){try{state=await api('/api/state');render();}catch(e){toast(e.message,true);}}
async function action(button,path,data={}) {button.disabled=true;try{const result=await api(path,data);toast(result.message);await refresh();}catch(e){toast(e.message,true);}finally{button.disabled=false;}}
document.querySelectorAll('.nav').forEach(b=>b.onclick=()=>showView(b.dataset.view));document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>showView(b.dataset.go));
$('#sync').onclick=()=>action($('#sync'),'/api/sync');$('#run').onclick=()=>action($('#run'),'/api/run');$('#background').onclick=()=>action($('#background'),'/api/background',{enabled:!state.background});
$('#reel-grid').onclick=e=>{const button=e.target.closest('.configure');if(!button)return;selected=state.reels.find(r=>r.id===button.dataset.id);const form=$('#rule-form');['keywords','reply','dm'].forEach(k=>form.elements[k].value=selected[k]);form.elements.enabled.checked=!!selected.enabled;$('#rule-caption').textContent=selected.caption;$('#rule-dialog').showModal();};
$('#close-dialog').onclick=$('#cancel-dialog').onclick=()=>$('#rule-dialog').close();
$('#rule-form').onsubmit=async e=>{e.preventDefault();const form=e.target;const button=form.querySelector('[type=submit]');button.disabled=true;try{const result=await api('/api/reels/'+encodeURIComponent(selected.id),{keywords:form.elements.keywords.value,reply:form.elements.reply.value,dm:form.elements.dm.value,enabled:form.elements.enabled.checked});$('#rule-dialog').close();toast(result.message);await refresh();}catch(e){toast(e.message,true);}finally{button.disabled=false;}};
refresh();setInterval(()=>{if(!document.hidden&&!$('#rule-dialog').open)refresh();},10000);
