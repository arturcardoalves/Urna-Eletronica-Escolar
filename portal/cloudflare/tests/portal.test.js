import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync,mkdtempSync,openSync,existsSync} from 'node:fs';
import {spawn,spawnSync} from 'node:child_process';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {verify,files} from '../src/protocol.js';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {parseQR,verifyScanned}=require('../../static/verify.js');
const jsQR=require('jsqr');
import {esc} from '../src/views.js';
const root=resolve(fileURLToPath(new URL('../../..',import.meta.url)));
let fixture,server,origin,workdir;
const bytes=raw=>Uint8Array.from(Buffer.from(raw,'base64'));
const post=raw=>fetch(origin+'/api/transmissions',{method:'POST',headers:{Authorization:'Bearer test-only-token','Content-Type':'application/octet-stream'},body:bytes(raw)});
before(async()=>{
  mkdirSync(join(root,'test-results'),{recursive:true});
  workdir=mkdtempSync(join(root,'test-results','cloudflare-'));
  const py=process.env.PYTHON_EXE||(existsSync(join(root,'.build-venv/Scripts/python.exe'))?join(root,'.build-venv/Scripts/python.exe'):'python');
  const exported=spawnSync(py,[join(root,'tests/export_cloudflare_fixtures.py'),join(workdir,'packets.json')],{encoding:'utf8'});
  assert.equal(exported.status,0,exported.stderr);
  fixture=JSON.parse(readFileSync(join(workdir,'packets.json'),'utf8'));
  const config=join(workdir,'wrangler.json');
  writeFileSync(config,JSON.stringify({name:'urna-portal-test',main:join(root,'portal/cloudflare/src/worker.js'),compatibility_date:'2026-10-13',
    assets:{directory:join(root,'portal/static'),binding:'ASSETS',run_worker_first:true},
    vars:{TRUST_REGISTRY:JSON.stringify(fixture.trust)},
    d1_databases:[{binding:'DB',database_name:'test-publications',database_id:fixture.eid,migrations_dir:join(root,'portal/cloudflare/migrations')}]}));
  const wrangler=join(root,'portal/cloudflare/node_modules/wrangler/bin/wrangler.js'),state=join(workdir,'state');
  const migrated=spawnSync(process.execPath,[wrangler,'d1','migrations','apply','test-publications','--local','--config',config,'--persist-to',state],{encoding:'utf8',env:{...process.env,WRANGLER_SEND_METRICS:'false'}});
  assert.equal(migrated.status,0,migrated.stderr);
  const port=Number(process.env.CF_TEST_PORT||18769);origin=`http://127.0.0.1:${port}`;
  server=spawn(process.execPath,[wrangler,'dev','--config',config,'--persist-to',state,'--ip','127.0.0.1','--port',String(port),'--local'],{stdio:['ignore',openSync(join(workdir,'worker.log'),'w'),openSync(join(workdir,'worker-errors.log'),'w')],env:{...process.env,WRANGLER_SEND_METRICS:'false'}});
  let ready=false;
  for(let i=0;i<100;i++){
    if(server.exitCode!==null)break;
    try{const r=await fetch(origin+'/health');if(r.ok){ready=true;break;}}catch(_){}
    await new Promise(r=>setTimeout(r,150));
  }
  assert.ok(ready,'Emulador Cloudflare não iniciou: '+readFileSync(join(workdir,'worker-errors.log'),'utf8'));
});
after(()=>{if(server)server.kill();});

test('Python packages verify in the Cloudflare JavaScript protocol',async()=>{
  for(const raw of fixture.raw){const p=await verify(bytes(raw),fixture.trust);assert.equal(p.document.election.id,fixture.eid);}
  const wrong=structuredClone(fixture.trust);wrong[fixture.eid].fingerprint='0'.repeat(64);
  await assert.rejects(()=>verify(bytes(fixture.raw[0]),wrong));
  const altered=bytes(fixture.raw[0]);altered[45]^=1;
  await assert.rejects(()=>verify(altered,fixture.trust));
  assert.throws(()=>files(new Uint8Array(8*1024*1024+1)));
  assert.equal(esc('<script>"&'),'&lt;script&gt;&quot;&amp;');
});

test('Worker and D1 receive stages, deduplicate, preserve revisions and serve exact assets',async()=>{
  assert.match(await (await fetch(origin+'/')).text(),/Não há votações no momento/);
  assert.equal((await fetch(origin+'/api/transmissions',{method:'POST',body:bytes(fixture.raw[0])})).status,401);
  assert.equal((await post(fixture.raw[1])).status,409);
  const first=await post(fixture.raw[0]);assert.equal(first.status,200,await first.clone().text());const receipt=await first.json();
  assert.match(await (await fetch(origin+'/')).text(),/Eleição de teste isolado/);
  const duplicate=await post(fixture.raw[0]);assert.deepEqual(await duplicate.json(),receipt);
  assert.equal((await post(fixture.conflict)).status,409);
  assert.equal((await post(fixture.raw[3])).status,409);
  for(const raw of fixture.raw.slice(1,4)){const r=await post(raw);assert.equal(r.status,200,await r.clone().text());}
  assert.match(await (await fetch(origin+'/elections/'+fixture.eid)).text(),/>Parcial</);
  const last=await post(fixture.raw[4]);assert.equal(last.status,200,await last.clone().text());
  assert.match(await (await fetch(origin+'/elections/'+fixture.eid)).text(),/>Definitivo</);
  assert.match(await (await fetch(origin+'/')).text(),/Não há votações no momento/);
  const docid=fixture.docs[3].id;
  assert.equal((await fetch(origin+'/documents/'+docid)).status,200);
  const download=await fetch(origin+'/documents/'+docid+'/package');
  assert.deepEqual(new Uint8Array(await download.arrayBuffer()),bytes(fixture.raw[3]));
  assert.ok((await (await fetch(origin+'/documents/'+docid+'/pdf')).text()).startsWith('%PDF-'));
  const manifest=await (await fetch(origin+'/documents/'+docid+'/manifest')).json();assert.equal(manifest.manifest.document.id,docid);
  const revised=await post(fixture.revision);assert.equal(revised.status,200,await revised.clone().text());
  assert.equal((await fetch(origin+'/documents/'+docid)).status,200);
  assert.equal((await fetch(origin+'/documents/'+fixture.revision_id)).status,200);
  assert.equal((await post(fixture.changed_totals)).status,409);
  assert.equal((await fetch(origin+'/verify')).status,200);
  assert.equal((await fetch(origin+'/portal.css')).status,200);
  assert.equal((await fetch(origin+'/verify.js')).status,200);
});

test('Simultaneous retries yield the same durable receipt',async()=>{
  const replies=await Promise.all(Array.from({length:4},()=>post(fixture.raw[0])));
  const receipts=await Promise.all(replies.map(r=>r.json()));
  assert.ok(receipts.every(r=>r.protocol===receipts[0].protocol));
});

test('Camera decoder reads the actual thermal QR and verifies published data',async()=>{
  const f=fixture.frame,decoded=jsQR(new Uint8ClampedArray(Buffer.from(f.rgba,'base64')),f.width,f.height);
  assert.equal(decoded.data,fixture.qr);
  const origin='https://eleicao.example';
  const load=async()=>fixture.envelope;
  const result=await verifyScanned(decoded.data,origin,load);
  assert.equal(result.trusted,true);assert.equal(result.document.id,fixture.docs[3].id);
  const summary=await verifyScanned(decoded.data,origin,async()=>{throw Error('offline');});
  assert.equal(summary.trusted,false);assert.match(summary.message,/não confirmados/);
  const tampered=fixture.qr.replace('result','zero');
  await assert.rejects(()=>verifyScanned(tampered,origin,load),/Assinatura inválida/);
  const wrong=structuredClone(fixture.envelope);wrong.manifest.document.totals.total++;
  await assert.rejects(()=>verifyScanned(decoded.data,origin,async()=>wrong),/Assinatura inválida/);
  assert.throws(()=>parseQR('https://attacker.example/documents/'+fixture.docs[3].id,origin));
  assert.throws(()=>parseQR('javascript:alert(1)',origin));
  const page=await (await fetch('http://127.0.0.1:'+Number(process.env.CF_TEST_PORT||18769)+'/verify')).text();
  assert.match(page,/id="startCamera"/);assert.match(page,/playsinline/);assert.doesNotMatch(page,/<textarea|<input|verifyForm/);
});

test('Only the latest election appears, including after old election corrections',async()=>{
  assert.equal((await post(fixture.next_config)).status,200);
  let page=await (await fetch(origin+'/')).text();
  assert.match(page,/Nova eleição atual/);assert.doesNotMatch(page,/Eleição de teste isolado/);
  assert.equal((await post(fixture.old_revision)).status,200);
  page=await (await fetch(origin+'/')).text();
  assert.match(page,/Nova eleição atual/);assert.doesNotMatch(page,/Eleição de teste isolado/);
  assert.equal((await fetch(origin+'/documents/'+fixture.docs[0].id)).status,200);
});
