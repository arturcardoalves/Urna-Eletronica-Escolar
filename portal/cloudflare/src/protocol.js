import validate from './validate.cjs';
const enc=new TextEncoder(),dec=new TextDecoder('utf-8',{fatal:true});
export const MAX_PACKAGE=8*1024*1024;
const crcTable=Uint32Array.from({length:256},(_,i)=>{let c=i;for(let n=0;n<8;n++)c=(c&1)?0xedb88320^(c>>>1):c>>>1;return c>>>0;});
function crc32(bytes){let c=0xffffffff;for(let i=0;i<bytes.length;i++)c=crcTable[(c^bytes[i])&255]^(c>>>8);return (c^0xffffffff)>>>0;}
const ascii=x=>JSON.stringify(x).replace(/[\u007f-\uffff]/g,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));
export function canonical(x){
  if(Array.isArray(x))return '['+x.map(canonical).join(',')+']';
  if(x!==null&&typeof x==='object')return '{'+Object.keys(x).sort().map(k=>ascii(k)+':'+canonical(x[k])).join(',')+'}';
  return ascii(x);
}
export async function sha(x){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',x)),v=>v.toString(16).padStart(2,'0')).join('');}
function fail(message){throw new Error(message);}
function unb64(s){if(typeof s!=='string'||!/^[A-Za-z0-9_-]+$/.test(s))fail('Base64 inválido');return Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-s.length%4)%4)),c=>c.charCodeAt(0));}
export function files(raw){
  if(raw.byteLength>MAX_PACKAGE||raw.byteLength<22)fail('Pacote excede o limite de 8 MiB do portal gratuito ou está incompleto');
  const bytes=new Uint8Array(raw),v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),out={};let pos=0;
  const entries=[];
  while(pos+30<=bytes.length&&v.getUint32(pos,true)===0x04034b50){
    const flags=v.getUint16(pos+6,true),method=v.getUint16(pos+8,true),size=v.getUint32(pos+18,true),unpacked=v.getUint32(pos+22,true),n=v.getUint16(pos+26,true),extra=v.getUint16(pos+28,true);
    if(flags!==0||method!==0||size!==unpacked||size>MAX_PACKAGE)fail('Formato não suportado. Exporte um pacote com a versão atual da Central (ZIP sem compressão).');
    const start=pos+30+n+extra,end=start+size;
    if(end>bytes.length||extra!==0)fail('ZIP inválido');
    const name=dec.decode(bytes.subarray(pos+30,pos+30+n));
    if(!/^(manifest\.json|document\.pdf|photo-\d{1,2}\.png)$/.test(name)||Object.hasOwn(out,name)||entries.length>=102)fail('Arquivos repetidos ou não permitidos');
    const checksum=v.getUint32(pos+14,true),content=bytes.subarray(start,end);
    if(crc32(content)!==checksum)fail('Checksum ZIP inválido');
    entries.push({name,size,offset:pos,checksum});out[name]=content;pos=end;
  }
  const centralStart=pos;
  for(const item of entries){
    if(pos+46>bytes.length||v.getUint32(pos,true)!==0x02014b50)fail('Índice ZIP inválido');
    const n=v.getUint16(pos+28,true),extra=v.getUint16(pos+30,true),comment=v.getUint16(pos+32,true);
    if(v.getUint16(pos+8,true)!==0||v.getUint16(pos+10,true)!==0||v.getUint32(pos+16,true)!==item.checksum||v.getUint32(pos+20,true)!==item.size||v.getUint32(pos+24,true)!==item.size||v.getUint32(pos+42,true)!==item.offset||dec.decode(bytes.subarray(pos+46,pos+46+n))!==item.name)fail('Índice ZIP diverge dos arquivos');
    pos+=46+n+extra+comment;
  }
  if(entries.length<2||pos+22!==bytes.length||v.getUint32(pos,true)!==0x06054b50||v.getUint16(pos+4,true)!==0||v.getUint16(pos+6,true)!==0||v.getUint16(pos+20,true)!==0||v.getUint16(pos+8,true)!==entries.length||v.getUint16(pos+10,true)!==entries.length||v.getUint32(pos+12,true)!==pos-centralStart||v.getUint32(pos+16,true)!==centralStart)fail('Fim ZIP inválido');
  return out;
}
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const time=s=>typeof s==='string'&&/(Z|[+-]\d\d:\d\d)$/.test(s)&&Number.isFinite(Date.parse(s));
export function semantics(d){
  if(!validate(d))fail('Dados públicos fora do esquema permitido');
  const e=d.election,t=d.totals,p=d.evidence;
  if(['previous','correction','configuration_digest'].some(k=>!Object.hasOwn(d,k))||!Object.hasOwn(e,'registered')||e.slates.some(s=>!Object.hasOwn(s,'photo')))fail('Documento deve conter todos os campos normalizados do protocolo');
  if(!uuid.test(d.id)||!uuid.test(e.id)||e.urns.some(u=>!uuid.test(u.id)))fail('Identificador inválido');
  let url;try{url=new URL(e.public_url);}catch(_){fail('Portal inválido');}
  if(url.protocol!=='https:'||url.origin!==e.public_url||url.username||url.password)fail('Use somente a origem HTTPS do portal');
  if(!time(d.created_at)||!time(e.sealed_at)||[p.zero_issued_at,p.opened_at,p.closed_at].some(s=>s!==null&&!time(s)))fail('Horário inválido');
  if((d.revision===1)!==(d.previous===null)||(d.revision>1&&!d.correction.trim()))fail('Revisão inválida');
  if(e.identified!==(e.registered!==null))fail('Cadastro incompatível');
  const numbers=e.slates.map(s=>s.number);
  if(new Set(numbers).size!==numbers.length||new Set(e.urns.map(u=>u.id)).size!==e.urns.length||new Set(e.urns.map(u=>u.code)).size!==e.urns.length)fail('Chapas ou urnas repetidas');
  if(d.kind==='configuration'){
    if(t!==null||d.urn_id!==null||d.configuration_digest!==null)fail('Configuração inválida');
  }else{
    if(!e.urns.some(u=>u.id===d.urn_id)||!t||!d.configuration_digest||!p.zero_snapshot_hash||!p.zero_issued_at)fail('Documento incompleto');
    if(t.total!==t.slates.reduce((n,s)=>n+s.votes,0)+t.blank+t.null||new Set(t.slates.map(s=>s.number)).size!==numbers.length||t.slates.some(s=>!numbers.includes(s.number)))fail('Contagem inconsistente');
    if(e.identified!==(t.attendance!==null)||e.identified!==(t.registered!==null)||(e.identified&&(t.attendance!==t.total||t.registered<e.registered||t.total>t.registered)))fail('Comparecimento inconsistente');
    if(!e.allow_blank&&t.blank)fail('Brancos desabilitados');
    if(d.kind==='zero'&&t.total)fail('Zerésima com votos');
    if(d.kind==='result'&&(!p.opened_at||!p.closed_at||!p.ballot_set_hash||Date.parse(p.closed_at)<Date.parse(p.opened_at)))fail('Encerramento inválido');
  }
}
export async function verify(raw,registry){
  const assets=files(raw),mbytes=assets['manifest.json'];
  if(!mbytes||mbytes.length>512*1024)fail('Manifesto inválido ou excessivo');
  const text=dec.decode(mbytes),envelope=JSON.parse(text);
  // Canonical equality also rejects duplicate JSON keys and alternate numeric spellings.
  if(canonical(envelope)!==text||Object.keys(envelope).sort().join(',')!=='manifest,signature')fail('Manifesto não canônico');
  const m=envelope.manifest;
  if(Object.keys(m).sort().join(',')!=='assets,document,public_key')fail('Manifesto inválido');
  semantics(m.document);
  const d=m.document,entry=registry[d.election.id],pub=unb64(m.public_key),fingerprint=await sha(pub);
  if(!entry||entry.fingerprint!==fingerprint||entry.public_url!==d.election.public_url)fail('Eleição ou chave não reconhecida pelo portal');
  const key=await crypto.subtle.importKey('raw',pub,'Ed25519',false,['verify']);
  if(!await crypto.subtle.verify('Ed25519',key,unb64(envelope.signature),enc.encode('URNA-PUBLICATION-V1\0'+canonical(m))))fail('Assinatura não confere');
  const expected=['document.pdf',...new Set(d.election.slates.filter(s=>s.photo).map(s=>s.photo))].sort();
  if(Object.keys(assets).filter(n=>n!=='manifest.json').sort().join(',')!==expected.join(',')||Object.keys(m.assets).sort().join(',')!==expected.join(','))fail('Arquivos extras ou ausentes');
  await Promise.all(expected.map(async name=>{
    const bytes=assets[name],info=m.assets[name];
    if(canonical(info)!==canonical({size:bytes.length,sha256:await sha(bytes)}))fail('Arquivo adulterado');
    if(name==='document.pdf'&&dec.decode(bytes.subarray(0,5))!=='%PDF-')fail('PDF inválido');
    if(name.endsWith('.png')){
      const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.length);
      if(bytes.length<24||Array.from(bytes.subarray(0,8)).join(',')!=='137,80,78,71,13,10,26,10'||view.getUint32(16)>1600||view.getUint32(20)>1600)fail('Foto PNG inválida');
    }
  }));
  return {document:d,envelope,assets,fingerprint,digest:await sha(enc.encode(canonical(d))),hash:await sha(raw)};
}
