const shell = document.querySelector('.urn-shell');
const urnCode = shell.dataset.urn;
const setup = document.getElementById('deviceSetup');
const waiting = document.getElementById('waiting');
const ballot = document.getElementById('ballot');
const done = document.getElementById('done');
const closed = document.getElementById('closed');
const bootCheck = document.getElementById('bootCheck');
const integrityBlocked = document.getElementById('integrityBlocked');
const bootChecks = document.getElementById('bootChecks');
const secretInput = document.getElementById('deviceSecret');
const selectionList = document.getElementById('selectionList');
const selectionReview = document.getElementById('selectionReview');
const reviewContent = document.getElementById('reviewContent');
const numericNotice = document.getElementById('numericNotice');

let deviceAuthenticated = false;
let managedPrint = false;
let sendingVote = false;
let connectionReady = true;
let pendingRecovery = sessionStorage.getItem('urnaPending:' + urnCode);
const connectionBanner = document.createElement('div');
connectionBanner.setAttribute('role', 'alert');
connectionBanner.style.cssText = 'display:none;position:fixed;inset:0;z-index:10000;background:rgba(12,25,42,.96);color:white;padding:25vh 8vw;font:700 28px Atkinson Hyperlegible,Arial;text-align:center';
document.body.append(connectionBanner);
function connectionMessage(message) {
  connectionBanner.textContent = message;
  connectionBanner.style.display = message ? 'block' : 'none';
}
for (const event of ['click', 'keydown']) {
  document.addEventListener(event, e => {
    if (sendingVote || pendingRecovery || !connectionReady) { e.preventDefault(); e.stopImmediatePropagation(); }
  }, true);
}

let currentToken = null;
let selected = null;
let digits = '';
let electionState = shell.dataset.initialState || 'CONFIG';
let editingDevice = false;
let agentUrl = localStorage.getItem('urnaAgentUrl:' + urnCode) || 'http://127.0.0.1:8765';
let printerName = localStorage.getItem('urnaPrinter:' + urnCode) || '';
let printerMode = localStorage.getItem('urnaPrinterMode:' + urnCode) || 'escpos';
let doneUntil = 0;
const agentInput = document.getElementById('printAgentUrl');
const printerSelect = document.getElementById('urnPrinter');
const printerModeSelect = document.getElementById('urnPrinterMode');
const agentStatus = document.getElementById('agentStatus');
if (agentInput) agentInput.value = agentUrl;
if (printerModeSelect) printerModeSelect.value = printerMode;

let keyConfirm = shell.dataset.keyConfirm || 'Enter';
let keyCorrect = shell.dataset.keyCorrect || 'Backspace';
let keyBlank = shell.dataset.keyBlank || 'KeyB';
let votingMode = shell.dataset.mode || 'NUMERIC';
let anonymousMode = shell.dataset.identification === '0';
let startingAnonymous = false;

function show(el) {
  [setup, waiting, ballot, done, closed, bootCheck, integrityBlocked].forEach(x => x && x.classList.add('hidden'));
  if (el) el.classList.remove('hidden');
}

function applyOperationalConfig(d = {}) {
  if (d.keyboard_confirm_key) keyConfirm = d.keyboard_confirm_key;
  if (d.keyboard_correct_key) keyCorrect = d.keyboard_correct_key;
  if (d.keyboard_blank_key) keyBlank = d.keyboard_blank_key;
  if (d.voting_mode) votingMode = d.voting_mode;
  if (typeof d.sound_enabled === 'boolean') shell.dataset.sound = d.sound_enabled ? '1' : '0';
  if (typeof d.anonymous_mode === 'boolean') anonymousMode = d.anonymous_mode;
  const numeric = document.getElementById('numericMode');
  const selection = document.getElementById('selectionMode');
  numeric?.classList.toggle('hidden', votingMode !== 'NUMERIC');
  selection?.classList.toggle('hidden', votingMode !== 'SELECTION');
}


function tone(ms = 90, freq = 760) {
  if (shell.dataset.sound !== '1') return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(freq, ctx.currentTime);
    gain.gain.setValueAtTime(0.14, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + ms / 1000);
    osc.connect(gain); gain.connect(ctx.destination);
    osc.start(ctx.currentTime); osc.stop(ctx.currentTime + ms / 1000);
    osc.onended = () => ctx.close();
  } catch (_) {}
}

function finalTone() {
  if (shell.dataset.sound !== '1') return;
  const url = shell.dataset.soundUrl;
  if (url) {
    try {
      const audio = new Audio(url);
      audio.preload = 'auto';
      audio.volume = 0.9;
      const p = audio.play();
      if (p && typeof p.catch === 'function') p.catch(() => tone(135, 1040));
      return;
    } catch (_) {}
  }
  tone(135, 1040);
}


async function requestUrnFullscreen() {
  try {
    if (!document.fullscreenElement) await document.documentElement.requestFullscreen({navigationUI:'hide'});
    return true;
  } catch (_) { return false; }
}
document.getElementById('enterFullscreenSetup')?.addEventListener('click', requestUrnFullscreen);
const quickSettings=document.getElementById('urnQuickSettings');
document.getElementById('openUrnQuickSettings')?.addEventListener('click',e=>{e.stopPropagation();quickSettings?.classList.toggle('hidden');});
document.getElementById('quickFullscreen')?.addEventListener('click',async()=>{quickSettings?.classList.add('hidden');await requestUrnFullscreen();});
document.getElementById('quickDeviceSettings')?.addEventListener('click',()=>{quickSettings?.classList.add('hidden');openDeviceSettings();});
document.addEventListener('click',e=>{if(quickSettings && !quickSettings.classList.contains('hidden') && !e.target.closest('.urn-settings-wrap')) quickSettings.classList.add('hidden');});

// Em modo quiosque o navegador já remove sua interface. Estas teclas são
// neutralizadas apenas dentro da página para evitar navegação acidental.
document.addEventListener('keydown', e => {
  const blocked = (e.ctrlKey && ['l','t','n','w','r'].includes(String(e.key).toLowerCase())) || (e.altKey && ['ArrowLeft','ArrowRight'].includes(e.key));
  if (blocked) { e.preventDefault(); e.stopPropagation(); }
}, true);
document.addEventListener('contextmenu', e => e.preventDefault());

async function syncDeviceConfig() {
  try {
    const r = await fetch(`/api/urna/${urnCode}/device-config`);
    if (r.status === 401) {
      deviceAuthenticated = false;
      return false;
    }
    if (!r.ok) return false;
    deviceAuthenticated = true;
    const d = await r.json();
    managedPrint = Boolean(d.managed_print);
    agentUrl = d.agent_url || 'http://127.0.0.1:8765';
    printerName = d.printer_name || '';
    printerMode = d.printer_mode || 'escpos';
    electionState = d.election_state || electionState;
    applyOperationalConfig(d);
    // Se a impressora ainda não foi vinculada no servidor, aproveita a
    // seleção feita pelo Assistente de Configuração deste computador.
    if (!managedPrint && !printerName) {
      try {
        const local = await fetch('http://127.0.0.1:8765/device-config', {cache:'no-store'});
        if (local.ok) {
          const ld = await local.json();
          if (ld.printer_name) printerName = ld.printer_name;
          if (ld.printer_mode) printerMode = ld.printer_mode;
        }
      } catch (_) {}
    }
    localStorage.setItem('urnaAgentUrl:' + urnCode, agentUrl);
    localStorage.setItem('urnaPrinter:' + urnCode, printerName);
    localStorage.setItem('urnaPrinterMode:' + urnCode, printerMode);
    if (agentInput) agentInput.value = agentUrl;
    if (printerModeSelect) printerModeSelect.value = printerMode;
    if (printerSelect && printerName) printerSelect.innerHTML = `<option value="${esc(printerName)}">${esc(printerName)}</option>`;
    return true;
  } catch (_) { return false; }
}

async function runIntegrityCheck() {
  show(bootCheck);
  if (bootChecks) bootChecks.innerHTML = '<div class="boot-check pending"><span>…</span><b>Iniciando verificação</b></div>';
  try {
    const r = await fetch(`/api/urna/${urnCode}/integrity-check`, {cache:'no-store'});
    if (!r.ok) throw new Error('Não foi possível verificar a integridade.');
    const d = await r.json();
    if (bootChecks) bootChecks.innerHTML = (d.checks||[]).map(c => `<div class="boot-check ${c.ok?'ok':'bad'}"><span>${c.ok?'✓':'×'}</span><div><b>${esc(c.label)}</b><small>${esc(c.detail||'')}</small></div></div>`).join('');
    await new Promise(resolve => setTimeout(resolve, 650));
    if (!d.ok) {
      const bad=(d.checks||[]).find(c=>!c.ok);
      const reason=document.getElementById('integrityBlockedReason'); if(reason) reason.textContent=bad?.detail || 'A integridade do sistema não foi confirmada.';
      show(integrityBlocked);
      return false;
    }
    return true;
  } catch (e) {
    const reason=document.getElementById('integrityBlockedReason'); if(reason) reason.textContent=e.message || 'Falha ao verificar a integridade.';
    show(integrityBlocked);
    return false;
  }
}

async function initialize() {
  const ok = await syncDeviceConfig();
  if (!ok) { show(setup); return; }
  const integrityOk = await runIntegrityCheck();
  if (!integrityOk) return;
  if (electionState === 'CLOSED') show(closed); else if (anonymousMode && electionState === 'OPEN') { resetChoice(); show(ballot); } else show(waiting);
  poll();
}

async function discoverPrinters() {
  agentUrl = (agentInput?.value || 'http://127.0.0.1:8765').replace(/\/$/, '');
  try {
    const health = await fetch(agentUrl + '/health');
    if (!health.ok) throw new Error('Agente indisponível');
    const r = await fetch(agentUrl + '/printers');
    if (!r.ok) throw new Error('Não foi possível listar impressoras');
    const d = await r.json();
    if (!printerName) {
      try {
        const local = await fetch(agentUrl + '/device-config', {cache:'no-store'});
        if (local.ok) {
          const ld = await local.json();
          if (ld.printer_name) printerName = ld.printer_name;
          if (ld.printer_mode) { printerMode = ld.printer_mode; if (printerModeSelect) printerModeSelect.value = printerMode; }
        }
      } catch (_) {}
    }
    printerSelect.innerHTML = '<option value="">Selecione...</option>' + d.printers.map(p => `<option value="${esc(p)}">${esc(p)}</option>`).join('');
    const preferred = printerName || d.default || '';
    if (preferred && d.printers.includes(preferred)) printerSelect.value = preferred;
    agentStatus.textContent = 'Agente conectado'; agentStatus.className = 'agent-status ok';
  } catch (_) {
    agentStatus.textContent = 'Agente não encontrado'; agentStatus.className = 'agent-status error';
  }
}

document.getElementById('discoverPrinters')?.addEventListener('click', discoverPrinters);

document.getElementById('testPrinter')?.addEventListener('click', async () => {
  agentUrl = (agentInput?.value || 'http://127.0.0.1:8765').replace(/\/$/, '');
  printerName = printerSelect?.value || '';
  printerMode = printerModeSelect?.value || 'windows';
  if (!printerName) { agentStatus.textContent='Selecione uma impressora'; agentStatus.className='agent-status error'; return; }
  try {
    const sample={institution:'ESCOLA',election:'ELEIÇÃO GRÊMIO',number:10,slate:'CHAPA DE TESTE',members:[],instruction:'DOBRE E COLOQUE NA URNA'};
    const r = await fetch(agentUrl + '/print', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({printer:printerName,mode:printerMode,text:'URNA ESCOLAR\nTESTE DE IMPRESSÃO',title:'Teste Urna Escolar',cut:true,copies:1,layout:'ballot',paper:sample,paper_width_mm:80})});
    if (!r.ok) throw new Error(await r.text());
    agentStatus.textContent='Teste enviado com sucesso'; agentStatus.className='agent-status ok';
  } catch (_) { agentStatus.textContent='Falha no teste de impressão'; agentStatus.className='agent-status error'; }
});

async function openDeviceSettings() {
  if (managedPrint) { alert('A configuração fica no aplicativo Urna de Votação. Use Alt+F4 para voltar a ele.'); return; }
  editingDevice = true;
  secretInput.value = '';
  secretInput.placeholder = 'Digite novamente a senha da urna';
  await syncDeviceConfig();
  show(setup);
  discoverPrinters();
}
document.getElementById('openDeviceSettings')?.addEventListener('click', openDeviceSettings);
document.getElementById('openDeviceSettingsClosed')?.addEventListener('click', openDeviceSettings);

document.getElementById('cancelDeviceSettings')?.addEventListener('click', () => {
  editingDevice = false;
  if (deviceAuthenticated && electionState === 'CLOSED') show(closed); else if (deviceAuthenticated && anonymousMode && electionState === 'OPEN') { resetChoice(); show(ballot); } else if (deviceAuthenticated) show(waiting); else show(setup);
});

document.getElementById('saveSecret')?.addEventListener('click', async () => {
  const typed = secretInput.value.trim();
  if (!typed) { agentStatus.textContent='Digite a senha do dispositivo'; agentStatus.className='agent-status error'; return; }
  agentUrl = (agentInput?.value || 'http://127.0.0.1:8765').replace(/\/$/, '');
  printerName = printerSelect?.value || '';
  printerMode = printerModeSelect?.value || 'windows';
  try {
    const login = await fetch(`/api/urna/${urnCode}/login`, {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body:new URLSearchParams({device_secret:typed})});
    if (!login.ok) { const d=await login.json().catch(()=>({})); throw new Error(d.detail || 'Senha da urna inválida'); }
    deviceAuthenticated = true;
    const r = await fetch(`/api/urna/${urnCode}/printer-config`, {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body:new URLSearchParams({printer_name:printerName,agent_url:agentUrl,printer_mode:printerMode})});
    if (!r.ok) { const d=await r.json().catch(()=>({})); throw new Error(d.detail || 'Não foi possível salvar'); }
    localStorage.setItem('urnaAgentUrl:' + urnCode, agentUrl);
    localStorage.setItem('urnaPrinter:' + urnCode, printerName);
    localStorage.setItem('urnaPrinterMode:' + urnCode, printerMode);
    agentStatus.textContent='Configuração salva'; agentStatus.className='agent-status ok';
    editingDevice = false;
    await syncDeviceConfig();
    if (electionState === 'CLOSED') show(closed); else if (anonymousMode && electionState === 'OPEN') { resetChoice(); show(ballot); } else show(waiting);
    poll();
  } catch (e) {
    agentStatus.textContent = e.message || 'Senha ou configuração inválida'; agentStatus.className='agent-status error';
  }
});

async function poll() {
  if (!deviceAuthenticated || currentToken || pendingRecovery || sendingVote || !connectionReady || Date.now() < doneUntil) return;
  try {
    const r = await fetch(`/api/urna/${urnCode}/authorization`);
    if (r.status === 401) {
      deviceAuthenticated = false; show(setup); return;
    }
    if (!r.ok) return;
    const d = await r.json();
    electionState = d.election_state || electionState;
    applyOperationalConfig(d);
    if (electionState === 'CLOSED') { show(closed); return; }
    if (d.authorized) {
      currentToken = d.token;
      resetChoice();
      show(ballot);
      tone(70, 780);
    } else if (!setup.classList.contains('hidden')) {
      // mantém a tela de configuração aberta
    } else if (anonymousMode && electionState === 'OPEN') {
      // Sem identificação nominal a urna fica pronta continuamente. A sessão
      // anônima só é criada no primeiro ato do eleitor (tecla/clique), fazendo
      // a Mesa enxergar LIVRE -> EM VOTAÇÃO sem precisar autorizar pessoa a pessoa.
      resetChoice();
      show(ballot);
    } else {
      show(waiting);
    }
  } catch (_) {}
}

async function pollReprint() {
  if (!deviceAuthenticated || managedPrint) return;
  try {
    const r = await fetch(`/api/urna/${urnCode}/reprint`);
    if (!r.ok) return;
    const d = await r.json();
    if (d.requested) {
      let success = false;
      try { const rr = await fetch(agentUrl + '/reprint-last', {method:'POST'}); success = rr.ok; } catch (_) {}
      await fetch(`/api/urna/${urnCode}/reprint-complete`, {method:'POST', headers: {'Content-Type':'application/x-www-form-urlencoded'}, body:new URLSearchParams({success:success?'true':'false'})});
    }
  } catch (_) {}
}

async function pollPrintCommand() {
  if (!deviceAuthenticated || managedPrint) return;
  try {
    if (!printerName) await syncDeviceConfig();
    if (!printerName) return;
    const r = await fetch(`/api/urna/${urnCode}/print-command`, {headers:{}});
    if (!r.ok) return;
    const d = await r.json();
    if (!d.pending) return;
    const payload = {...d.payload, printer: printerName, mode: d.payload.mode || printerMode || 'windows'};
    let success=false;
    try { const pr = await fetch(agentUrl + '/print', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); success=pr.ok; } catch (_) {}
    await fetch(`/api/urna/${urnCode}/print-command/${d.id}/complete`, {method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({success:success?'true':'false'})});
  } catch (_) {}
}

setInterval(poll, 700);
setInterval(pollReprint, 1200);
setInterval(pollPrintCommand, 1200);
initialize(); pollReprint(); pollPrintCommand();

function resetChoice() {
  selected = null; digits = '';
  const display = document.getElementById('numberDisplay');
  if (display) display.innerHTML = '<span>_</span><span>_</span>';
  const preview = document.getElementById('candidatePreview');
  if (preview) preview.innerHTML = '<div class="candidate-empty"><b>AGUARDANDO DIGITAÇÃO</b><span>Digite os dois números da chapa.</span></div>';
  numericNotice?.classList.remove('show');
  selectionReview?.classList.add('hidden');
  selectionList?.classList.remove('hidden');
}

async function ensureAnonymousSession() {
  if (!anonymousMode) return Boolean(currentToken);
  if (currentToken) return true;
  if (startingAnonymous || electionState !== 'OPEN') return false;
  startingAnonymous = true;
  try {
    const r = await fetch(`/api/urna/${urnCode}/anonymous/start`, {method:'POST'});
    if (!r.ok) {
      const d = await r.json().catch(()=>({}));
      showInlineError(d.detail || 'Não foi possível iniciar este voto.');
      return false;
    }
    const d = await r.json();
    currentToken = d.token;
    return Boolean(currentToken);
  } finally {
    startingAnonymous = false;
  }
}

function finishRecordedVote(data) {
  sessionStorage.removeItem('urnaPending:' + urnCode);
  pendingRecovery = null;
  sendingVote = false;
  connectionMessage('');
  currentToken = null;
  finalTone();
  doneUntil = Date.now() + 5000;
  show(done);
  if (!managedPrint && data.paper?.enabled) directPrintVote(data.paper, data.ballot_id);
  setTimeout(() => {
    doneUntil = 0;
    if (electionState === 'CLOSED') show(closed); else show(waiting);
    poll();
  }, 5000);
}

async function submitVote(type, number = null) {
  if (sendingVote || pendingRecovery || !connectionReady) return;
  if (anonymousMode && !currentToken && !(await ensureAnonymousSession())) return;
  if (!currentToken) return;
  sendingVote = true;
  const body = new URLSearchParams({token: currentToken, choice_type: type});
  if (number !== null) body.set('slate_number', String(number));
  if (managedPrint) sessionStorage.setItem('urnaPending:' + urnCode, currentToken);
  try {
    const r = await fetch(`/api/urna/${urnCode}/vote`, {method:'POST', body, signal:AbortSignal.timeout(10000)});
    const data = await r.json();
    if (!r.ok) {
      // Resolve through the receipt even after a 5xx or an interrupted response.
      if (managedPrint) throw new Error(data.detail || 'Confirmação pendente');
      showInlineError(data.detail || 'Não foi possível registrar o voto.'); return;
    }
    finishRecordedVote(data);
  } catch (_) {
    if (managedPrint) {
      pendingRecovery = currentToken;
      connectionMessage('Verificando se o voto foi registrado. Aguarde a conexão com a Central.');
    } else showInlineError('Conexão interrompida. Chame o mesário antes de tentar novamente.');
  } finally { sendingVote = false; }
}

let nativeCheckRunning = false;
async function checkNativeConnection() {
  if (!deviceAuthenticated || !managedPrint || nativeCheckRunning || sendingVote) return;
  nativeCheckRunning = true;
  try {
    const r = await fetch(`/api/urna/${urnCode}/device-config`, {cache:'no-store', signal:AbortSignal.timeout(4000)});
    if (!r.ok) throw new Error('Reabra a urna pelo aplicativo para renovar a conexão.');
    const d = await r.json();
    if (pendingRecovery) {
      const result = await fetch(`/api/urna/${urnCode}/vote-status`, {method:'POST',body:new URLSearchParams({token:pendingRecovery}),signal:AbortSignal.timeout(4000)});
      if (!result.ok) throw new Error('Aguarde a confirmação do voto pela Central.');
      const receipt = await result.json();
      if (receipt.recorded) finishRecordedVote(receipt);
      else {
        currentToken = pendingRecovery;
        pendingRecovery = null;
        sessionStorage.removeItem('urnaPending:' + urnCode);
        show(ballot);
        showInlineError('O voto ainda não foi registrado. Confira a escolha e confirme novamente.');
      }
    }
    connectionReady = Boolean(d.native_online) && (!d.print_enabled || d.printer_ready) && !['PRINTING','PRINT_ERROR'].includes(d.urn_status);
    connectionMessage(connectionReady ? '' : !d.native_online ? 'Aplicativo da urna desconectado. Chame o mesário.' : d.urn_status === 'PRINTING' ? 'Voto registrado. Aguarde a impressão.' : 'Confira a impressora. O mesário precisa resolver a pendência antes do próximo voto.');
  } catch (e) {
    connectionReady = false;
    connectionMessage(pendingRecovery ? 'Verificando se o voto foi registrado. Aguarde; não inicie outro voto.' : (e.name === 'TimeoutError' || e instanceof TypeError) ? 'Servidor desconectado. Confira a Central e os cabos de rede.' : e.message);
  } finally { nativeCheckRunning = false; }
}
setInterval(checkNativeConnection, 2000);

function showInlineError(message) { if (numericNotice) { numericNotice.textContent = message; numericNotice.classList.add('show'); } }

async function directPrintVote(p, ballotId) {
  if (!printerName) await syncDeviceConfig();
  if (!printerName) { await markPrintFailed(ballotId); return false; }
  const text = paperToText(p);
  try {
    const r = await fetch(agentUrl + '/print', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({printer:printerName,mode:printerMode || 'windows',text,title:'Voto - '+urnCode,cut:true,copies:1,layout:'ballot',paper:p,paper_width_mm:80})});
    if (!r.ok) throw new Error('Falha de impressão');
    await fetch(`/api/urna/${urnCode}/print-complete`, {method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({ballot_id:ballotId})});
    return true;
  } catch (_) { await markPrintFailed(ballotId); return false; }
}

async function markPrintFailed(ballotId) {
  try { await fetch(`/api/urna/${urnCode}/print-failed`, {method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({ballot_id:ballotId})}); } catch (_) {}
}

function paperToText(p) {
  const lines=[];
  if (p.institution) lines.push(p.institution);
  if (p.election) lines.push(p.election);
  lines.push('--------------------------------');
  if (p.number !== null && p.number !== undefined) lines.push('CHAPA ' + String(p.number).padStart(2,'0'));
  if (p.slate) lines.push(p.slate);
  (p.members || []).forEach(m => lines.push(`${m.role}: ${m.name}`));
  if (p.instruction) { lines.push('--------------------------------'); lines.push(p.instruction); }
  return lines.join('\n');
}

function esc(v) { return String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }

function selectForReview(number) {
  selected = number;
  const d = window.SLATE_DETAILS[String(number)]; if (!d) return;
  let members = '';
  if (d.members?.length) members = `<div class="review-members">${d.members.map(m => `<div><b>${esc(m.role)}</b><span>${esc(m.name)}</span></div>`).join('')}</div>`;
  reviewContent.innerHTML = `<div class="review-choice"><div class="review-photo-slot">${d.logo ? `<img src="${esc(d.logo)}" alt="Logo da chapa">` : `<span>FOTO</span>`}</div><div class="review-choice-text"><span class="review-number">${String(d.number).padStart(2,'0')}</span><h2>${esc(d.name)}</h2>${members}</div></div>`;
  selectionList.classList.add('hidden'); selectionReview.classList.remove('hidden');
}

function selectBlankForReview() {
  selected = 'blank';
  reviewContent.innerHTML = `<div class="review-blank"><span>VOTO EM</span><h2>BRANCO</h2><p>Confira e pressione CONFIRMAR.</p></div>`;
  selectionList.classList.add('hidden'); selectionReview.classList.remove('hidden');
}


const slateButtons=[...document.querySelectorAll('.slate-option')];
let slatePage=0; const slatePageSize=9;
function renderSlatePage(){
  const pages=Math.max(1,Math.ceil(slateButtons.length/slatePageSize)); slatePage=Math.max(0,Math.min(slatePage,pages-1));
  slateButtons.forEach((b,i)=>b.classList.toggle('page-hidden',i<slatePage*slatePageSize||i>=(slatePage+1)*slatePageSize));
  const controls=document.getElementById('slatePageControls');
  controls?.classList.toggle('hidden',pages<=1);
  const label=document.getElementById('slatePageLabel'); if(label)label.textContent=`Página ${slatePage+1} de ${pages}`;
  const prev=document.getElementById('slatePrev'),next=document.getElementById('slateNext'); if(prev)prev.disabled=slatePage===0;if(next)next.disabled=slatePage>=pages-1;
}
document.getElementById('slatePrev')?.addEventListener('click',()=>{slatePage--;renderSlatePage();});
document.getElementById('slateNext')?.addEventListener('click',()=>{slatePage++;renderSlatePage();});
renderSlatePage();
document.querySelectorAll('.slate-option').forEach(btn => btn.onclick = async () => { if (anonymousMode && !currentToken && !(await ensureAnonymousSession())) return; selectForReview(Number(btn.dataset.number)); });
document.getElementById('blankChoice')?.addEventListener('click', async () => { if (anonymousMode && !currentToken && !(await ensureAnonymousSession())) return; selectBlankForReview(); });
document.getElementById('selectionCorrect')?.addEventListener('click', resetChoice);
document.getElementById('selectionConfirm')?.addEventListener('click', () => selected === 'blank' ? submitVote('blank') : submitVote('slate', selected));

function keyMatches(e, configured) {
  if (!configured) return false;
  const want = configured.trim().toLowerCase();
  return String(e.key).toLowerCase() === want || String(e.code).toLowerCase() === want;
}

document.addEventListener('keydown', async e => {
  if (ballot.classList.contains('hidden') || votingMode !== 'NUMERIC') return;
  if (anonymousMode && !currentToken) {
    const isVoteKey = keyMatches(e, keyCorrect) || keyMatches(e, keyConfirm) || (shell.dataset.blank === '1' && keyMatches(e, keyBlank)) || /^\d$/.test(e.key);
    if (!isVoteKey) return;
    e.preventDefault();
    if (!(await ensureAnonymousSession())) return;
  }
  if (e.repeat) { e.preventDefault(); return; }
  // As teclas especiais têm prioridade: assim até uma tecla numérica pode ser
  // atribuída por macro a CONFIRMA/CORRIGE/BRANCO sem virar dígito do voto.
  if (keyMatches(e, keyCorrect)) { e.preventDefault(); correct(); return; }
  if (keyMatches(e, keyConfirm)) { e.preventDefault(); confirmNumeric(); return; }
  if (shell.dataset.blank === '1' && keyMatches(e, keyBlank)) { e.preventDefault(); selectBlankNumeric(); return; }
  if (/^\d$/.test(e.key)) { e.preventDefault(); inputDigit(e.key); return; }
});

function inputDigit(digit) {
  selected = null;
  if (digits.length >= 2) return;
  digits += digit; tone(45, 610); updateNumeric();
}

function updateNumeric() {
  const display = document.getElementById('numberDisplay');
  const chars = [digits[0] || '_', digits[1] || '_'];
  if (display) display.innerHTML = `<span>${chars[0]}</span><span>${chars[1]}</span>`;
  const preview = document.getElementById('candidatePreview'); if (!preview) return;
  numericNotice?.classList.remove('show');
  if (digits.length < 2) { preview.innerHTML = '<div class="candidate-empty"><b>CONTINUE DIGITANDO</b><span>Informe os dois números da chapa.</span></div>'; return; }
  const n = Number(digits); const d = window.SLATE_DETAILS[String(n)];
  if (!d) { preview.innerHTML = '<div class="invalid-preview"><b>Número Inválido</b><span>Use CORRIGE e digite uma chapa cadastrada.</span></div>'; numericNotice?.classList.remove('show'); tone(110,250); return; }
  const members = d.members?.length ? d.members.slice(0,4).map(m => `<small><b>${esc(m.role)}</b> ${esc(m.name)}</small>`).join('') : '';
  const nameClass = d.name.length > 34 ? 'name-long' : (d.name.length > 22 ? 'name-medium' : '');
  preview.innerHTML = `<div class="candidate-card"><div class="candidate-photo-slot">${d.logo ? `<img src="${esc(d.logo)}" alt="Logo da chapa">` : `<span>FOTO</span>`}</div><div class="candidate-text"><span>CHAPA ${String(d.number).padStart(2,'0')}</span><h2 class="${nameClass}">${esc(d.name)}</h2>${members}</div></div>`;
}

function selectBlankNumeric() {
  selected = 'blank'; digits = '';
  const display = document.getElementById('numberDisplay');
  if (display) display.innerHTML = '<span class="blank-display">BRANCO</span>';
  const preview = document.getElementById('candidatePreview');
  if (preview) preview.innerHTML = '<div class="blank-numeric"><span>VOTO EM</span><h2>BRANCO</h2><p>Confira e pressione CONFIRMA para concluir.</p></div>';
  numericNotice?.classList.remove('show'); tone(60,520);
}

function correct() { resetChoice(); tone(60,450); }
function confirmNumeric() {
  if (selected === 'blank') { submitVote('blank'); return; }
  if (digits.length !== 2) { tone(100,250); return; }
  const n = Number(digits);
  if (!window.SLATE_DATA.includes(n)) { tone(130,240); return; }
  submitVote('slate', n);
}

async function reportDeviceHealth() {
  if (!deviceAuthenticated || managedPrint) return;
  let agentOnline=false, printerReady=false;
  try {
    const h=await fetch(agentUrl+'/health'); agentOnline=h.ok;
    if (agentOnline && printerName) { const r=await fetch(agentUrl+'/printers'); if(r.ok){const d=await r.json();printerReady=(d.printers||[]).includes(printerName);} }
  } catch (_) {}
  try { await fetch(`/api/urna/${urnCode}/device-health`,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({agent_online:agentOnline?'true':'false',printer_ready:printerReady?'true':'false'})}); } catch (_) {}
}
setInterval(reportDeviceHealth,5000); reportDeviceHealth();
