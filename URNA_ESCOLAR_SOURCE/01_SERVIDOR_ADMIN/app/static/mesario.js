const page=document.querySelector('.station-page');
const stationControls=document.getElementById('stationControls');
const stationClosed=document.getElementById('stationClosed');
const stationPreopen=document.getElementById('stationPreopen');
const preopenConfigState=document.getElementById('preopenConfigState');
const preopenSealedState=document.getElementById('preopenSealedState');
const search=document.getElementById('search');
const results=document.getElementById('results');
const searchBtn=document.getElementById('searchBtn');
const voterList=document.getElementById('voterList');
const visibleVoterCount=document.getElementById('visibleVoterCount');
const identificationEnabled=page?.dataset.identification==='1';
const lookupMode=page?.dataset.lookupMode||'SEARCH_LIST';
const hasListMode=lookupMode==='SEARCH_LIST'||lookupMode==='LIST_ONLY';
const hasSearchMode=lookupMode==='SEARCH'||lookupMode==='SEARCH_LIST';
let electionState=page?.dataset.state||'CONFIG';
let openingTicket=null;
let currentClass='ALL';
let listRefreshTimer=null;
let searchTimer=null;
let selectedVoter=null;
let selectedUrnCode=null;
let activePaperAlert=null;
window.URN_STATE={};

function esc(v){return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
function escAttr(v){return esc(v).replace(/`/g,'&#96;');}
function anyModalOpen(){return [...document.querySelectorAll('.station-modal')].some(m=>!m.classList.contains('hidden'));}
function showModal(id){const m=document.getElementById(id);if(!m)return;m.classList.remove('hidden');setTimeout(()=>m.querySelector('button:not([disabled]),input:not([disabled])')?.focus(),60);}
function hideModal(id){document.getElementById(id)?.classList.add('hidden');if(electionState==='OPEN'&&!anyModalOpen())setTimeout(()=>search?.focus(),60);}
document.querySelectorAll('[data-close]').forEach(b=>b.addEventListener('click',()=>hideModal(b.dataset.close)));
document.querySelectorAll('.station-modal').forEach(m=>m.addEventListener('mousedown',e=>{if(e.target===m)hideModal(m.id)}));

function applyState(state){
  const changed=state!==electionState;electionState=state;
  const pill=document.getElementById('stationStatePill');
  pill?.classList.remove('station-state-config','station-state-sealed','station-state-open','station-state-closed');
  if(pill){pill.textContent=state;pill.classList.add('station-state-'+state.toLowerCase());}
  stationPreopen?.classList.toggle('hidden',!['CONFIG','SEALED'].includes(state));
  preopenConfigState?.classList.toggle('hidden',state!=='CONFIG');
  preopenSealedState?.classList.toggle('hidden',state!=='SEALED');
  stationControls?.classList.toggle('hidden',state!=='OPEN');
  stationClosed?.classList.toggle('hidden',state!=='CLOSED');
  if(search)search.disabled=state!=='OPEN';if(searchBtn)searchBtn.disabled=state!=='OPEN';
  if(state==='CLOSED')document.querySelectorAll('.station-modal').forEach(x=>x.classList.add('hidden'));
  if(changed&&state==='OPEN'){if(identificationEnabled&&hasListMode)loadVoterList();if(hasSearchMode)setTimeout(()=>search?.focus(),80);}
}

function renderPreflight(checks){
  const box=document.getElementById('preopenChecks');if(!box||!Array.isArray(checks))return;
  const visible=checks.filter(c=>!['zero','zero_printed'].includes(c.key));
  box.innerHTML=visible.map(c=>`<div class="preopen-check ${c.ok?'ok':(!c.blocking?'warn':'bad')}" data-check="${escAttr(c.key)}"><span>${c.ok?'✓':(!c.blocking?'!':'×')}</span><div><b>${esc(c.label)}</b><small>${esc(c.detail)}</small></div></div>`).join('');
}

function urnVisualStatus(status){if(status==='AVAILABLE')return['status-available','LIVRE'];if(status==='IN_USE')return['status-in_use','EM VOTAÇÃO'];if(status==='PRINTING')return['status-in_use','IMPRIMINDO'];if(status==='PRINT_ERROR')return['status-print_error','ATENÇÃO IMPRESSÃO'];return['status-offline','OFFLINE'];}
function renderUrns(urns=[]){
  window.URN_STATE={};
  urns.forEach(u=>{window.URN_STATE[u.code]=u.status;const row=document.querySelector(`#urnList .station-urn[data-urn="${CSS.escape(u.code)}"]`);const [cls,label]=urnVisualStatus(u.status);if(row){row.className='station-urn '+cls;const s=row.querySelector('.urn-status');if(s)s.textContent=label;}const big=document.querySelector(`[data-anon-urn="${CSS.escape(u.code)}"]`);if(big){big.className='anonymous-urn-card '+(u.status==='AVAILABLE'?'free':u.status==='IN_USE'?'busy':'problem');const strong=big.querySelector('strong');if(strong)strong.textContent=label;}});
}

function voterStatusLabel(v){if(v.status==='VOTED')return'<span class="status-chip red">JÁ VOTOU</span>';if(v.status==='IN_PROGRESS')return`<span class="status-chip amber">EM VOTAÇÃO${v.active_urn_name?' · '+esc(v.active_urn_name):''}</span>`;return'<span class="status-chip green">DISPONÍVEL</span>';}
function voterCard(v,compact=false){
  const cls=v.status==='VOTED'?'voted':v.status==='IN_PROGRESS'?'progress':'ready';
  return `<button type="button" class="voter-list-card ${cls} ${compact?'compact-result':''}" data-enrollment="${escAttr(v.enrollment)}" data-name="${escAttr(v.name)}" data-class="${escAttr(v.class_code)}" data-shift="${escAttr(v.shift)}" data-status="${escAttr(v.status)}"><div><strong>${esc(v.name)}</strong><small>${esc(v.enrollment)} · ${esc(v.class_code)}${v.shift?' · '+esc(v.shift):''}</small></div>${voterStatusLabel(v)}</button>`;
}
function bindVoterCards(scope=document){scope.querySelectorAll('.voter-list-card').forEach(btn=>btn.onclick=()=>openVoterConfirmation({enrollment:btn.dataset.enrollment,name:btn.dataset.name,class_code:btn.dataset.class,shift:btn.dataset.shift,status:btn.dataset.status}));}

async function doSearch(){
  if(!identificationEnabled||!hasSearchMode||electionState!=='OPEN'||!search||!results)return;
  const q=search.value.trim();
  if(!q){results.innerHTML='<div class="idle-message compact"><span>Resultado da pesquisa</span><small>Digite uma matrícula ou parte do nome.</small></div>';return;}
  results.innerHTML='<div class="loading-state">Procurando…</div>';
  try{const r=await fetch('/api/voters/search?q='+encodeURIComponent(q),{cache:'no-store'});const d=await r.json().catch(()=>[]);if(!r.ok)throw new Error(d.detail||'Não foi possível pesquisar.');results.innerHTML=d.length?`<div class="search-result-grid">${d.slice(0,4).map(v=>voterCard(v,true)).join('')}</div>`:'<div class="not-found-state"><b>ELEITOR NÃO ENCONTRADO</b><span>Confira a matrícula ou pesquise pelo nome.</span></div>';bindVoterCards(results);}catch(err){results.innerHTML=`<div class="error-state">${esc(err.message)}</div>`;}
}
searchBtn?.addEventListener('click',doSearch);
search?.addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(doSearch,180)});
search?.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();doSearch();}});

async function loadVoterList(){
  if(!identificationEnabled||!hasListMode||!voterList||electionState!=='OPEN')return;
  try{const r=await fetch('/api/voters/list?class_code='+encodeURIComponent(currentClass),{cache:'no-store'});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Falha ao carregar lista.');visibleVoterCount.textContent=`${d.length} aluno(s)`;voterList.innerHTML=d.length?d.map(v=>voterCard(v,false)).join(''):'<div class="empty-list-state">Nenhum aluno nesta turma.</div>';bindVoterCards(voterList);}catch(err){voterList.innerHTML=`<div class="error-state">${esc(err.message)}</div>`;}
}
document.querySelectorAll('.class-filter').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('.class-filter').forEach(x=>x.classList.remove('active'));btn.classList.add('active');currentClass=btn.dataset.class||'ALL';loadVoterList();}));

function availableUrns(){return (window.URN_CODES||[]).filter(code=>window.URN_STATE[code]==='AVAILABLE');}

function renderPendingVoterConfirmation(){
  const modal=document.getElementById('voterConfirmModal');
  if(!selectedVoter||!modal||modal.classList.contains('hidden'))return;

  const box=document.getElementById('confirmUrnChoices');
  const btn=document.getElementById('confirmVoterBtn');
  const status=document.getElementById('confirmVoterStatus');
  if(!box||!btn||!status)return;

  if(selectedVoter.status==='IN_PROGRESS'){
    selectedUrnCode=null;
    box.innerHTML='';
    box.classList.add('hidden');
    status.textContent='Aguardando urna livre…';
    status.className='station-operation-status waiting';
    btn.disabled=true;
    return;
  }

  const urns=availableUrns();

  if(!urns.length){
    selectedUrnCode=null;
    box.innerHTML='';
    box.classList.add('hidden');
    status.textContent='Aguardando urna livre…';
    status.className='station-operation-status waiting';
    btn.disabled=true;
    return;
  }

  /* Com uma única urna, não mostra seletor nem mensagem extra. */
  if((window.URN_CODES||[]).length<=1){
    selectedUrnCode=urns[0];
    box.innerHTML='';
    box.classList.add('hidden');
    status.textContent='Pronto para liberar.';
    status.className='station-operation-status ok';
    btn.disabled=false;
    return;
  }

  /* Com duas ou mais urnas, mostra somente as urnas livres para escolha. */
  box.classList.remove('hidden');
  if(!selectedUrnCode||!urns.includes(selectedUrnCode))selectedUrnCode=urns[0];
  box.innerHTML='<span class="confirm-urn-label">Selecione a urna</span><div class="confirm-urn-grid">'+urns.map(code=>`<button type="button" class="confirm-urn-option ${code===selectedUrnCode?'active':''}" data-code="${escAttr(code)}">${esc(code)}</button>`).join('')+'</div>';
  box.querySelectorAll('.confirm-urn-option').forEach(b=>b.onclick=()=>{
    box.querySelectorAll('.confirm-urn-option').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    selectedUrnCode=b.dataset.code;
  });

  status.textContent='Pronto para liberar.';
  status.className='station-operation-status ok';
  btn.disabled=false;
}

function openVoterConfirmation(v){
  if(!v||v.status==='VOTED')return;
  selectedVoter=v;
  selectedUrnCode=null;
  document.getElementById('confirmVoterName').textContent=v.name;
  document.getElementById('confirmVoterMeta').textContent=`${v.enrollment} · Turma ${v.class_code}${v.shift?' · '+v.shift:''}`;
  showModal('voterConfirmModal');
  renderPendingVoterConfirmation();
}

document.getElementById('confirmVoterBtn')?.addEventListener('click',async()=>{
  const btn=document.getElementById('confirmVoterBtn'),status=document.getElementById('confirmVoterStatus');if(!selectedVoter||!selectedUrnCode)return;btn.disabled=true;status.textContent='Liberando urna…';
  try{const r=await fetch('/api/mesario/authorize',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({enrollment:selectedVoter.enrollment,urn_code:selectedUrnCode})});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||'Não foi possível liberar.');hideModal('voterConfirmModal');if(search)search.value='';if(results)results.innerHTML='<div class="released-state compact-release"><div class="released-icon">✓</div><div><h2>URNA LIBERADA</h2><p>'+esc(selectedVoter.name)+' pode se dirigir à '+esc(selectedUrnCode)+'.</p></div></div>';selectedVoter=null;selectedUrnCode=null;await refreshStatus();await loadVoterList();setTimeout(()=>{if(results)results.innerHTML='<div class="idle-message compact"><span>Resultado da pesquisa</span><small>Digite uma matrícula ou parte do nome.</small></div>';},1800);}catch(err){status.className='station-operation-status bad';status.textContent=err.message;btn.disabled=true;await refreshStatus();renderPendingVoterConfirmation();}
});

function setOpeningCheck(id,state,text){const el=document.getElementById(id);if(!el)return;el.className='opening-check '+state;el.querySelector('span').textContent=state==='ok'?'✓':state==='bad'?'×':'…';el.querySelector('small').textContent=text;}
function renderOpeningUrns(urns=[]){const box=document.getElementById('openingUrns');if(!box)return;box.innerHTML=urns.map(u=>`<div class="opening-urn-row" data-opening-urn="${escAttr(u.code)}"><span>…</span><div><b>${esc(u.name)}</b><small>${esc(u.code)} · aguardando impressão</small></div></div>`).join('');}
async function waitOpenReady(ticket,statusEl){for(let i=0;i<120;i++){const r=await fetch('/api/mesario/open/ready?ticket='+encodeURIComponent(ticket),{cache:'no-store'});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||'Falha ao verificar a Zerésima.');statusEl.textContent=`Zerésimas impressas: ${d.completed}/${d.total}`;(d.urns||[]).forEach(u=>{const row=document.querySelector(`[data-opening-urn="${CSS.escape(u.code)}"]`);if(row){row.className='opening-urn-row '+u.state;row.querySelector('span').textContent=u.state==='ok'?'✓':u.state==='failed'?'×':'…';row.querySelector('small').textContent=`${u.code} · ${u.state==='ok'?'impressão confirmada':u.state==='failed'?'falha de impressão':'aguardando impressão'}`;}});if(d.failed)throw new Error('Uma das urnas informou falha de impressão da Zerésima.');if(d.ready)return d;await new Promise(res=>setTimeout(res,900));}throw new Error('Tempo excedido aguardando a impressão da Zerésima.');}
async function waitCloseReady(ticket,statusEl){for(let i=0;i<120;i++){const r=await fetch('/api/mesario/close/ready?ticket='+encodeURIComponent(ticket),{cache:'no-store'});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||'Falha ao verificar a impressão do boletim.');statusEl.textContent=`Boletins impressos: ${d.completed}/${d.total}`;if(d.failed)throw new Error('Uma das urnas informou falha de impressão do boletim.');if(d.ready)return d;await new Promise(res=>setTimeout(res,900));}throw new Error('Tempo excedido aguardando a impressão do boletim final.');}
function resetOpening(){openingTicket=null;document.getElementById('openingProgress')?.classList.add('hidden');const commit=document.getElementById('commitOpeningBtn');if(commit){commit.disabled=true;commit.textContent='INICIAR VOTAÇÃO';}const form=document.getElementById('openElectionForm');if(form){form.classList.remove('hidden');form.reset();}setOpeningCheck('openingIntegrity','pending','Aguardando verificação');const u=document.getElementById('openingUrns');if(u)u.innerHTML='';const s=document.getElementById('openElectionStatus');if(s)s.textContent='';}
document.getElementById('openElectionBtn')?.addEventListener('click',()=>{resetOpening();showModal('openElectionModal');setTimeout(()=>document.querySelector('#openElectionForm input[name="password"]')?.focus(),60)});
document.getElementById('openElectionForm')?.addEventListener('submit',async e=>{e.preventDefault();const form=e.target,btn=document.getElementById('prepareOpeningBtn'),status=document.getElementById('openElectionStatus');btn.disabled=true;status.className='station-operation-status';status.textContent='Validando Mesário e integridade…';document.getElementById('openingProgress').classList.remove('hidden');try{const r=await fetch('/api/mesario/open/prepare',{method:'POST',body:new FormData(form)});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||'Não foi possível preparar a abertura.');openingTicket=d.ticket;setOpeningCheck('openingIntegrity','ok','Configuração, software, chave interna e auditoria conferidos');renderOpeningUrns(d.urns);status.textContent=`Zerésima enviada para ${d.urns.length} urna(s). Aguardando confirmação de impressão…`;await waitOpenReady(openingTicket,status);form.classList.add('hidden');status.className='station-operation-status ok';status.textContent='Zerésima impressa e confirmada. A votação pode ser iniciada.';document.getElementById('commitOpeningBtn').disabled=false;}catch(err){status.className='station-operation-status bad';status.textContent=err.message||'Falha na preparação.';btn.disabled=false;}});
document.getElementById('commitOpeningBtn')?.addEventListener('click',async()=>{if(!openingTicket)return;const btn=document.getElementById('commitOpeningBtn'),status=document.getElementById('openElectionStatus');btn.disabled=true;btn.textContent='INICIANDO…';try{const r=await fetch('/api/mesario/open/commit',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({ticket:openingTicket})});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||'Não foi possível abrir a votação.');status.className='station-operation-status ok';status.textContent='VOTAÇÃO ABERTA COM SUCESSO.';setTimeout(()=>{hideModal('openElectionModal');applyState('OPEN');refreshStatus();if(identificationEnabled&&hasListMode)loadVoterList();},600);}catch(err){status.className='station-operation-status bad';status.textContent=err.message;btn.disabled=false;btn.textContent='INICIAR VOTAÇÃO';}});

document.getElementById('closeElectionBtn')?.addEventListener('click',()=>{const s=document.getElementById('closeElectionStatus');if(s){s.textContent='';s.className='station-operation-status';}showModal('closeElectionModal');setTimeout(()=>document.getElementById('closeUserPassword')?.focus(),60)});
async function submitCloseElection(){const form=document.getElementById('closeElectionForm'),btn=document.getElementById('closeSubmitBtn'),status=document.getElementById('closeElectionStatus');if(!form||!btn||!status)return;const pwd=document.getElementById('closeUserPassword')?.value||'',confirmed=form.querySelector('input[name="confirm_close"]')?.checked;if(!pwd){status.className='station-operation-status bad';status.textContent='Digite a senha do Mesário.';return;}if(!confirmed){status.className='station-operation-status bad';status.textContent='Marque a confirmação de encerramento.';return;}btn.disabled=true;btn.textContent='ENCERRANDO…';status.className='station-operation-status';status.textContent='Encerrando e apurando com a chave interna…';try{const r=await fetch('/api/mesario/close',{method:'POST',body:new FormData(form),credentials:'same-origin',cache:'no-store'});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||`Falha no encerramento (HTTP ${r.status}).`);applyState('CLOSED');status.textContent='Votação encerrada. Aguardando impressão do boletim final…';await waitCloseReady(d.ticket,status);status.className='station-operation-status ok';status.textContent='ENCERRAMENTO CONCLUÍDO. Boletim final impresso.';const box=document.getElementById('closedPrintStatus');if(box){box.textContent='Boletim final impresso com sucesso.';box.className='station-operation-status ok';}form.reset();setTimeout(()=>{hideModal('closeElectionModal');refreshStatus();},900);}catch(err){status.className='station-operation-status bad';status.textContent=err.message||'Não foi possível encerrar.';}finally{btn.disabled=false;btn.textContent='ENCERRAR E APURAR';}}
document.getElementById('closeSubmitBtn')?.addEventListener('click',e=>{e.preventDefault();submitCloseElection()});
document.getElementById('closeElectionForm')?.addEventListener('submit',e=>{e.preventDefault();submitCloseElection()});

function renderPaperAlert(paper){const box=document.getElementById('paperChangeAlert');if(!box)return;const alerts=paper?.alerts||[];activePaperAlert=alerts[0]||null;box.classList.toggle('hidden',!activePaperAlert);if(activePaperAlert){document.getElementById('paperChangeTitle').textContent=`Troca de papel · ${activePaperAlert.urn_name}`;document.getElementById('paperChangeText').textContent=`${activePaperAlert.votes_since_change} votos desde a última confirmação de troca.`;}}
document.getElementById('paperChangeConfirm')?.addEventListener('click',async()=>{if(!activePaperAlert)return;const r=await fetch('/api/mesario/paper-change/confirm',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({urn_code:activePaperAlert.urn_code})});if(r.ok)refreshStatus();});

async function refreshStatus(){
  try{const r=await fetch('/api/mesario/status',{cache:'no-store'});if(!r.ok)return;const d=await r.json();applyState(d.state);renderPreflight(d.preflight);renderUrns(d.urns||[]);renderPaperAlert(d.paper_change);const es=document.getElementById('electionState');if(es)es.textContent=d.state;const voted=document.getElementById('countVoted');if(voted)voted.textContent=d.voted??0;if(identificationEnabled){const total=document.getElementById('countTotal'),remaining=document.getElementById('countRemaining');if(total)total.textContent=d.total??0;if(remaining)remaining.textContent=d.remaining??0;}if(identificationEnabled&&hasListMode&&electionState==='OPEN'){clearTimeout(listRefreshTimer);listRefreshTimer=setTimeout(loadVoterList,120);}renderPendingVoterConfirmation(); }
  catch(_){}
}

setInterval(refreshStatus,1200);refreshStatus();applyState(electionState);if(identificationEnabled&&hasListMode&&electionState==='OPEN')loadVoterList();
