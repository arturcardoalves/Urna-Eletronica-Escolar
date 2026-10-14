import {verify,files,sha,canonical,MAX_PACKAGE} from './protocol.js';
import * as views from './views.js';
const enc=new TextEncoder();
const CHUNK=512*1024;
const stmt=(db,sql,...values)=>db.prepare(sql).bind(...values);
const eq=(a,b)=>{if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;let v=0;for(let i=0;i<a.length;i++)v|=a.charCodeAt(i)^b.charCodeAt(i);return v===0;};
function error(code,message){return new Response(JSON.stringify({detail:message}),{status:code,headers:{'Content-Type':'application/json'}});}
const json=value=>new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
const html=value=>new Response(value,{headers:{'Content-Type':'text/html; charset=utf-8'}});
const latestSQL="SELECT d.* FROM documents d WHERE d.election=? AND d.revision=(SELECT MAX(x.revision) FROM documents x WHERE x.election=d.election AND x.kind=d.kind AND x.urn=d.urn)";
async function upload(request,env){
  let registry;try{registry=JSON.parse(env.TRUST_REGISTRY||'{}');}catch(_){return error(503,'Cadastro de chaves do portal indisponível');}
  const auth=request.headers.get('Authorization')||'';
  if(!auth.startsWith('Bearer ')||auth.length>512)return error(401,'Credencial de transmissão inválida');
  const tokenHash=await sha(enc.encode(auth.slice(7))),authorized={};
  for(const [eid,entry] of Object.entries(registry))if(eq(entry.token_sha256,tokenHash))authorized[eid]=entry;
  if(!Object.keys(authorized).length)return error(401,'Credencial de transmissão inválida');
  if(request.headers.get('Content-Type')?.split(';')[0]!=='application/octet-stream')return error(415,'Envie um pacote .uepkg');
  const reader=request.body?.getReader();if(!reader)return error(400,'Pacote ausente');
  const chunks=[];let length=0;
  while(true){const {done,value}=await reader.read();if(done)break;length+=value.length;if(length>MAX_PACKAGE){await reader.cancel();return error(413,'Limite de 8 MiB por pacote no portal gratuito');}chunks.push(value);}
  const raw=new Uint8Array(length);let offset=0;for(const c of chunks){raw.set(c,offset);offset+=c.length;}
  let p;try{p=await verify(raw,authorized);}catch(e){return error(409,e.message);}
  const d=p.document,eid=d.election.id,db=env.DB;
  const old=await stmt(db,'SELECT hash,receipt FROM documents WHERE id=?',d.id).first();
  if(old)return old.hash===p.hash?json(JSON.parse(old.receipt)):error(409,'ID já recebido com outro conteúdo');
  const previous=await stmt(db,'SELECT document,digest,revision FROM documents WHERE election=? AND kind=? AND urn=? ORDER BY revision DESC LIMIT 1',eid,d.kind,d.urn_id||'').first();
  if(previous){
    const before=JSON.parse(previous.document);
    if(d.revision!==previous.revision+1||d.previous!==previous.digest||['election','totals','configuration_digest','evidence'].some(k=>canonical(before[k])!==canonical(d[k])))return error(409,'Revisão fora de sequência ou com valores lacrados modificados');
  }else if(d.revision!==1)return error(409,'Envie as versões anteriores primeiro');
  if(d.kind!=='configuration'){
    const base=await stmt(db,"SELECT document FROM documents WHERE election=? AND kind='configuration' AND digest=?",eid,d.configuration_digest).first();
    if(!base||canonical(JSON.parse(base.document).election)!==canonical(d.election))return error(409,'Envie a configuração correspondente primeiro');
  }
  if(d.kind==='result'){
    const z=await stmt(db,"SELECT document FROM documents WHERE election=? AND kind='zero' AND urn=? ORDER BY revision DESC LIMIT 1",eid,d.urn_id).first();
    if(!z)return error(409,'Envie a Zerésima desta urna primeiro');
    const zero=JSON.parse(z.document);
    if(zero.evidence.zero_snapshot_hash!==d.evidence.zero_snapshot_hash||Date.parse(d.evidence.closed_at)<Date.parse(zero.evidence.zero_issued_at))return error(409,'Boletim não corresponde à Zerésima');
  }
  const receipt={protocol:crypto.randomUUID(),received_at:new Date().toISOString(),document_id:d.id,election_id:eid,sha256:p.hash};
  // The INSERT guards run inside the same atomic D1 batch as the immutable file chunks.
  // They also serialize sum/cadastro checks for simultaneous uploads of different urns.
  const guard=`AND (?='configuration' OR EXISTS(SELECT 1 FROM documents WHERE election=? AND kind='configuration' AND digest=?))
    AND (?='configuration' OR ?='zero' OR EXISTS(SELECT 1 FROM documents WHERE election=? AND urn=? AND kind='zero'))
    AND (?=1 OR EXISTS(SELECT 1 FROM documents WHERE election=? AND kind=? AND urn=? AND revision=? AND digest=?))
    AND (?!='result' OR NOT EXISTS(SELECT 1 FROM documents q WHERE q.election=? AND q.kind='result' AND q.urn!=? AND q.revision=(SELECT MAX(x.revision) FROM documents x WHERE x.election=q.election AND x.kind=q.kind AND x.urn=q.urn) AND (json_extract(q.document,'$.totals.registered') IS NOT ? OR json_extract(q.document,'$.evidence') IS NOT ?)))
    AND (?=0 OR ?!='result' OR ? >= ? + COALESCE((SELECT SUM(json_extract(q.document,'$.totals.total')) FROM documents q WHERE q.election=? AND q.kind='result' AND q.urn!=? AND q.revision=(SELECT MAX(x.revision) FROM documents x WHERE x.election=q.election AND x.kind=q.kind AND x.urn=q.urn)),0))`;
  const insert=stmt(db,`INSERT INTO documents SELECT ?,?,?,?,?,?,?,?,?,?,?,? WHERE 1=1 ${guard} ON CONFLICT(id) DO NOTHING`,
    d.id,eid,d.kind,d.urn_id||'',d.revision,p.digest,p.hash,canonical(d),canonical(p.envelope),p.fingerprint,JSON.stringify(receipt),receipt.received_at,
    d.kind,eid,d.configuration_digest,d.kind,d.kind,eid,d.urn_id,d.revision,eid,d.kind,d.urn_id||'',d.revision-1,d.previous,
    d.kind,eid,d.urn_id,d.totals?.registered??null,canonical(d.evidence),d.election.identified?1:0,d.kind,d.totals?.registered??0,d.totals?.total??0,eid,d.urn_id);
  const operations=[insert];
  for(let seq=0,pos=0;pos<raw.length;pos+=CHUNK,seq++)operations.push(stmt(db,'INSERT INTO package_chunks SELECT ?,?,? WHERE EXISTS(SELECT 1 FROM documents WHERE id=? AND hash=?) ON CONFLICT(document_id,sequence) DO NOTHING',d.id,seq,raw.slice(pos,pos+CHUNK).buffer,d.id,p.hash));
  try{await db.batch(operations);}catch(_){return error(409,'Não foi possível gravar: revisão conflitante ou limite do banco. Preserve a mídia e confira o portal.');}
  const saved=await stmt(db,'SELECT hash,receipt FROM documents WHERE id=?',d.id).first();
  if(!saved||saved.hash!==p.hash)return error(409,'Publicação bloqueada por inconsistência ou concorrência. Confira cadastro e versões.');
  return json(JSON.parse(saved.receipt));
}
async function route(request,env){
  const path=new URL(request.url).pathname;
  if(request.method==='POST'&&path==='/api/transmissions')return upload(request,env);
  if(request.method!=='GET')return error(405,'Método não permitido');
  if(path==='/health')return json({status:'ok'});
  if(path==='/verify')return html(views.verifier());
  if(path==='/'){
    const {results}=await env.DB.prepare("SELECT c.document,(SELECT COUNT(DISTINCT urn) FROM documents r WHERE r.election=c.election AND r.kind='result') count FROM documents c WHERE c.kind='configuration' AND c.revision=1 ORDER BY c.received DESC,c.id DESC LIMIT 1").all();
    const current=results[0];
    if(!current || current.count>=JSON.parse(current.document).election.urns.length)return html(views.home());
    const eid=JSON.parse(current.document).election.id;
    const rows=await stmt(env.DB,latestSQL,eid).all();
    const history=await stmt(env.DB,'SELECT id,kind,revision,receipt,received FROM documents WHERE election=? ORDER BY received DESC LIMIT 100',eid).all();
    return html(views.election(rows.results,history.results));
  }
  const election=path.match(/^\/elections\/([0-9a-f-]{36})$/);
  if(election){
    const {results}=await stmt(env.DB,latestSQL,election[1]).all();
    if(!results.length)return error(404,'Eleição ainda não publicada');
    const history=await stmt(env.DB,'SELECT id,kind,revision,receipt,received FROM documents WHERE election=? ORDER BY received DESC LIMIT 100',election[1]).all();
    return html(views.election(results,history.results));
  }
  const match=path.match(/^\/documents\/([0-9a-f-]{36})(?:\/(package|manifest|pdf|photos\/photo-\d{1,2}\.png))?$/);
  if(match){
    const row=await stmt(env.DB,'SELECT * FROM documents WHERE id=?',match[1]).first();
    if(!row)return error(404,'Documento ainda não transmitido. Consulte novamente após a publicação.');
    if(!match[2])return html(views.document(row));
    if(match[2]==='manifest')return new Response(row.manifest,{headers:{'Content-Type':'application/json','Content-Disposition':`attachment; filename="${row.id}.json"`}});
    const stored=await stmt(env.DB,'SELECT content FROM package_chunks WHERE document_id=? ORDER BY sequence',row.id).all();
    const chunks=stored.results.map(c=>new Uint8Array(c.content)),length=chunks.reduce((n,c)=>n+c.length,0);
    if(length>MAX_PACKAGE)return error(503,'Arquivo armazenado excede o limite');
    const raw=new Uint8Array(length);let offset=0;for(const c of chunks){raw.set(c,offset);offset+=c.length;}
    if(await sha(raw)!==row.hash)return error(503,'Arquivo armazenado não passou na conferência');
    if(match[2]==='package')return new Response(raw,{headers:{'Content-Type':'application/octet-stream','Content-Disposition':`attachment; filename="${row.id}.uepkg"`}});
    const name=match[2]==='pdf'?'document.pdf':match[2].slice(7),content=files(raw)[name];
    if(!content)return error(404,'Arquivo não encontrado');
    return new Response(content,{headers:{'Content-Type':name.endsWith('.pdf')?'application/pdf':'image/png','Content-Disposition':`inline; filename="${name}"`,...(name.endsWith('.pdf')?{'Content-Security-Policy':'sandbox'}:{})}});
  }
  return env.ASSETS.fetch(request);
}
export default {async fetch(request,env){
  let response;try{response=await route(request,env);}catch(_){response=error(503,'Portal temporariamente indisponível. A eleição offline continua independente. Preserve a mídia e tente transmitir novamente.');}
  const secured=new Response(response.body,response);
  secured.headers.set('Permissions-Policy','camera=(self), microphone=()');
  secured.headers.set('Permissions-Policy','camera=(self), microphone=()');
  secured.headers.set('X-Content-Type-Options','nosniff');secured.headers.set('Referrer-Policy','no-referrer');
  if(!secured.headers.has('Content-Security-Policy'))secured.headers.set('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
  return secured;
}};
