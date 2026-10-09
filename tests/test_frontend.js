// Executes the shipped scripts in an isolated DOM/network simulation.
// No real browser, election database, printer, or network request is used.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor() {
    this.dataset = {};
    this.value = '';
    this.textContent = '';
    this.innerHTML = '';
    this.style = {};
    this.disabled = false;
    this.listeners = {};
    this.children = [];
    this.classes = new Set(['hidden']);
    this.classList = {
      add: (...names) => names.forEach(name => this.classes.add(name)),
      remove: (...names) => names.forEach(name => this.classes.delete(name)),
      contains: name => this.classes.has(name),
      toggle: (name, force) => {
        const on = force === undefined ? !this.classes.has(name) : force;
        if (on) this.classes.add(name); else this.classes.delete(name);
        return on;
      },
    };
  }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute() {}
  append(...children) { this.children.push(...children); }
  querySelectorAll() { return []; }
  querySelector() { return null; }
  focus() {}
  reset() { this.wasReset = true; }
}

function createUI(script, dataset = {}) {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  };
  const shell = get('shell');
  shell.dataset = {urn: 'URNA01', state: 'OPEN', initialState: 'OPEN', identification: '1', mode: 'SELECTION', ...dataset};
  const storage = () => {
    const data = new Map();
    return {getItem: key => data.get(key) || null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key)};
  };
  const context = vm.createContext({
    document: {
      body: new Element(),
      documentElement: new Element(),
      querySelector: selector => ['.urn-shell', '.station-page'].includes(selector) ? shell : null,
      querySelectorAll: () => [],
      getElementById: get,
      createElement: () => new Element(),
      addEventListener() {},
    },
    window: {URN_CODES: ['URNA01'], SLATE_DATA: [10], SLATE_DETAILS: {'10': {number: 10, name: 'Chapa fictícia', members: []}}},
    sessionStorage: storage(), localStorage: storage(),
    fetch: () => new Promise(() => {}),
    setInterval() {},
    setTimeout(callback, delay) { if (delay === 650) callback(); },
    clearTimeout() {},
    URLSearchParams, AbortSignal, Date, console,
    CSS: {escape: value => value},
    FormData: class {},
    alert() {},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/static', script), 'utf8'), context);
  return {context, get, run: code => vm.runInContext(code, context)};
}

const response = (data, status = 200) => ({ok: status >= 200 && status < 300, status, json: async () => data});

test('failed integrity check keeps authorization polling and voting blocked', async () => {
  const ui = createUI('urna.js');
  ui.run('deviceAuthenticated = true');
  ui.context.fetch = async () => response({ok: false, checks: [{ok: false, detail: 'Arquivo alterado'}]});
  assert.equal(await ui.run('runIntegrityCheck()'), false);
  assert.equal(ui.get('integrityBlocked').classList.contains('hidden'), false);
  let calls = 0;
  ui.context.fetch = async () => { calls++; return response({authorized: true, token: 'fake'}); };
  await ui.run('poll()');
  ui.run("currentToken = 'fake'");
  await ui.run("submitVote('slate', 10)");
  assert.equal(calls, 0);
});

test('authorization response cannot erase a choice made while its request was pending', async () => {
  const ui = createUI('urna.js');
  ui.run('deviceAuthenticated = true; integrityReady = true');
  let finish;
  ui.context.fetch = () => new Promise(resolve => { finish = resolve; });
  const pending = ui.run('poll()');
  ui.run("currentToken = 'anonymous-new'; selected = 10; digits = '10'");
  finish(response({authorized: false, election_state: 'OPEN', anonymous_mode: true}));
  await pending;
  assert.equal(ui.run('selected'), 10);
  assert.equal(ui.run('digits'), '10');
});

test('selection mode shows vote rejection and clears the pending receipt', async () => {
  const ui = createUI('urna.js');
  ui.run("deviceAuthenticated = true; integrityReady = true; managedPrint = true; currentToken = 'fake'");
  ui.context.fetch = async () => response({detail: 'A votação não está aberta.'}, 409);
  await ui.run("submitVote('slate', 10)");
  assert.equal(ui.get('selectionNotice').textContent, 'A votação não está aberta.');
  assert.equal(ui.get('selectionNotice').classList.contains('show'), true);
  assert.equal(ui.context.sessionStorage.getItem('urnaPending:URNA01'), null);
  assert.equal(ui.run('pendingRecovery'), null);
});

test('anonymous network failure is handled and visible in selection mode', async () => {
  const ui = createUI('urna.js', {identification: '0'});
  ui.run('integrityReady = true');
  ui.context.fetch = async () => { throw new Error('offline'); };
  assert.equal(await ui.run('ensureAnonymousSession()'), false);
  assert.match(ui.get('selectionNotice').textContent, /Conexão interrompida/);
  assert.equal(ui.run('startingAnonymous'), false);
});

test('completed vote clears the previous choice from the review DOM', () => {
  const ui = createUI('urna.js');
  ui.run('selectForReview(10)');
  assert.match(ui.get('reviewContent').innerHTML, /Chapa fictícia/);
  ui.run('finishRecordedVote({})');
  assert.equal(ui.get('reviewContent').textContent, '');
  assert.equal(ui.run('selected'), null);
  assert.equal(ui.get('done').classList.contains('hidden'), false);
});

test('station polling cannot reenable authorization while its POST is pending', () => {
  const ui = createUI('mesario.js');
  ui.get('voterConfirmModal').classList.remove('hidden');
  ui.get('confirmVoterBtn').disabled = true;
  ui.run("selectedVoter = {status:'AVAILABLE'}; authorizingVoter = true; stationConnected = true; window.URN_STATE = {URNA01:'AVAILABLE'}; renderPendingVoterConfirmation()");
  assert.equal(ui.get('confirmVoterBtn').disabled, true);
});

test('lost station connection clears stale urn availability and displays an alert', async () => {
  const ui = createUI('mesario.js');
  ui.run("statusRunning = false; stationConnected = true; window.URN_STATE = {URNA01:'AVAILABLE'}");
  ui.context.fetch = async () => { throw new Error('Rede indisponível'); };
  await ui.run('refreshStatus()');
  assert.equal(ui.run('stationConnected'), false);
  assert.equal(ui.run('availableUrns().length'), 0);
  assert.equal(ui.get('stationConnectionStatus').classList.contains('hidden'), false);
});

test('older voter search cannot overwrite a newer search result', async () => {
  const ui = createUI('mesario.js');
  const pending = new Map();
  ui.context.fetch = url => new Promise(resolve => pending.set(url, resolve));
  ui.get('search').value = 'Ana';
  const first = ui.run('doSearch()');
  ui.get('search').value = 'Bia';
  const second = ui.run('doSearch()');
  pending.get('/api/voters/search?q=Bia')(response([{name:'Bia',enrollment:'2',status:'AVAILABLE'}]));
  await second;
  pending.get('/api/voters/search?q=Ana')(response([{name:'Ana',enrollment:'1',status:'AVAILABLE'}]));
  await first;
  assert.match(ui.get('results').innerHTML, /Bia/);
  assert.doesNotMatch(ui.get('results').innerHTML, /Ana/);
});

test('final report print failure remains visible after election closes', async () => {
  const ui = createUI('mesario.js');
  ui.get('closeUserPassword').value = 'fake-test-password';
  ui.get('closeElectionForm').querySelector = () => ({checked:true});
  ui.context.fetch = async url => response(url === '/api/mesario/close' ? {ticket:'fictitious-ticket'} : {failed:true,completed:0,total:1});
  await ui.run('submitCloseElection()');
  assert.equal(ui.run('electionState'), 'CLOSED');
  assert.equal(ui.get('stationClosed').classList.contains('hidden'), false);
  assert.match(ui.get('closedPrintStatus').textContent, /permanece encerrada.*falha de impressão.*reimpressão/);
  assert.equal(ui.get('closeElectionForm').wasReset, true);
});
