'use strict';
// Camera frames remain local. Only signed public documents are fetched from this origin.
const enc = new TextEncoder();
const ascii = value => JSON.stringify(value).replace(/[\u007f-\uffff]/g, c => '\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));
const canonical = value => {
  if (Array.isArray(value)) return '['+value.map(canonical).join(',')+']';
  if (value !== null && typeof value === 'object') return '{'+Object.keys(value).sort().map(k=>ascii(k)+':'+canonical(value[k])).join(',')+'}';
  return ascii(value);
};
const unb64 = s => {if(!/^[A-Za-z0-9_-]+$/.test(s))throw Error('Base64 inválido');return Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-s.length%4)%4)),c=>c.charCodeAt(0));};
const sha = async bytes => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
async function checkSignature(publicKey,signature,text){
  const key=await crypto.subtle.importKey('raw',unb64(publicKey),{name:'Ed25519'},false,['verify']);
  if(!await crypto.subtle.verify({name:'Ed25519'},key,unb64(signature),enc.encode(text)))throw Error('Assinatura inválida');
  return sha(unb64(publicKey));
}
const uuidPattern=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function parseQR(value,origin){
  if(typeof value!=='string'||value.length>2000)throw Error('QR não reconhecido');
  let text=value.trim(),consultation=null;
  if(!text.startsWith('UE1|')){
    let url;try{url=new URL(text);}catch(_){throw Error('QR não reconhecido');}
    if(url.origin!==origin||url.search)throw Error('Este QR não pertence a este portal');
    if(url.pathname==='/verify'&&url.hash)text=decodeURIComponent(url.hash.slice(1));
    else if(/^\/documents\/[0-9a-f-]{36}$/.test(url.pathname)&&!url.hash)consultation=url.pathname.split('/')[2];
    else throw Error('Use o QR de verificação do documento');
  }
  if(consultation){if(!uuidPattern.test(consultation))throw Error('ID inválido');return {id:consultation,parts:null};}
  const parts=text.split('|');
  if(parts.length!==9||parts[0]!=='UE1'||!uuidPattern.test(parts[1])||!uuidPattern.test(parts[2])||!(parts[3]==='-'||uuidPattern.test(parts[3]))||!['configuration','zero','result'].includes(parts[4])||!/^[1-9][0-9]*$/.test(parts[5])||!/^[a-f0-9]{64}$/.test(parts[6])||unb64(parts[7]).length!==32||unb64(parts[8]).length!==64)throw Error('QR não reconhecido');
  return {id:parts[2],parts};
}
async function verifyScanned(value,origin,loadManifest){
  const {id,parts}=parseQR(value,origin);
  let fingerprint=null;
  if(parts)fingerprint=await checkSignature(parts[7],parts[8],'URNA-QR-V1\0'+parts.slice(0,8).join('|'));
  let envelope;
  try{envelope=await loadManifest(id);}catch(error){
    if(!parts)throw Error('Documento indisponível. Escaneie o QR de verificação para conferir a assinatura do resumo.');
    return {trusted:false,message:'Assinatura do resumo válida. Documento indisponível no portal: identidade da chave e valores ainda não confirmados.',fingerprint};
  }
  const m=envelope.manifest,doc=m.document;
  const fp=await checkSignature(m.public_key,envelope.signature,'URNA-PUBLICATION-V1\0'+canonical(m));
  if(doc.id!==id)throw Error('Documento retornado não corresponde ao QR');
  if(parts&&(fingerprint!==fp||parts[1]!==doc.election.id||parts[3]!==(doc.urn_id||'-')||parts[4]!==doc.kind||parts[5]!==String(doc.revision)||parts[6]!==await sha(enc.encode(canonical(doc)))))throw Error('QR e documento assinado não correspondem');
  return {trusted:true,message:parts?'Assinatura válida. QR corresponde ao documento publicado. Compare os dados abaixo com o papel.':'Documento publicado com assinatura válida. Este é o QR de consulta; escaneie também o QR de verificação para conferir o resumo impresso.',fingerprint:fp,document:doc};
}
function cameraError(error){
  if(error.name==='NotAllowedError'||error.name==='SecurityError')return 'Acesso à câmera não permitido. Autorize nas configurações do navegador e tente novamente.';
  if(error.name==='NotFoundError')return 'Nenhuma câmera foi encontrada neste dispositivo.';
  if(error.name==='NotReadableError')return 'A câmera está ocupada ou indisponível. Feche outros aplicativos que a utilizam.';
  return 'Não foi possível abrir a câmera. Use HTTPS e um navegador atualizado.';
}
if(typeof document!=='undefined'){
  const el=id=>document.getElementById(id),video=el('camera'),start=el('startCamera'),stopButton=el('stopCamera');
  let stream=null,timer=null,generation=0;
  const stop=()=>{generation++;clearTimeout(timer);timer=null;if(stream)stream.getTracks().forEach(track=>track.stop());stream=null;video.srcObject=null;video.hidden=true;stopButton.hidden=true;start.disabled=false;};
  const loadManifest=async id=>{
    const response=await fetch('/documents/'+id+'/manifest',{redirect:'error',cache:'no-store',signal:AbortSignal.timeout(15000)});
    if(!response.ok)throw Error('Documento ainda não disponível');
    const text=await response.text();if(text.length>1024*1024)throw Error('Documento muito grande');return JSON.parse(text);
  };
  const scanned=async value=>{
    stop();const run=generation;el('verification').textContent='Conferindo assinatura…';el('verifiedData').textContent='';
    try{
      if(!crypto.subtle)throw Error('Este navegador não oferece verificação criptográfica. Use HTTPS e um navegador atualizado.');
      const result=await verifyScanned(value,location.origin,loadManifest);
      if(run!==generation)return;
      el('verification').textContent=result.message;
      const doc=result.document;
      el('verifiedData').textContent=doc?[
        'Eleição: '+doc.election.name,'Escola: '+doc.election.school,'Documento: '+({configuration:'Configuração e lacração',zero:'Zerésima',result:'Boletim de Urna'}[doc.kind]),
        'Urna: '+(doc.election.urns.find(u=>u.id===doc.urn_id)?.name||'Todas'),'Revisão: '+doc.revision,
        ...(doc.totals?[...doc.totals.slates.map(s=>'Chapa '+s.number+' — '+doc.election.slates.find(c=>c.number===s.number)?.name+': '+s.votes),'Brancos: '+doc.totals.blank,'Nulos: '+doc.totals.null,'Total: '+doc.totals.total,'Comparecimento: '+(doc.totals.attendance??'Não aferido')]:[]),
        'Documento: '+doc.id,'Impressão digital da chave: '+result.fingerprint
      ].join('\n'):'Impressão digital da chave: '+result.fingerprint;
    }catch(error){if(run===generation)el('verification').textContent='Não verificado: '+error.message;}
  };
  start.addEventListener('click',async()=>{
    stop();start.disabled=true;el('verifiedData').textContent='';el('verification').textContent='Abrindo câmera…';const run=generation;
    try{
      if(!navigator.mediaDevices?.getUserMedia)throw Error('Câmera indisponível');
      if(typeof jsQR!=='function')throw Error('Leitor não carregado');
      const opened=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:720}}});
      if(run!==generation){opened.getTracks().forEach(track=>track.stop());return;}
      stream=opened;video.srcObject=opened;video.hidden=false;stopButton.hidden=false;await video.play();
      if(run!==generation)return;
      el('verification').textContent='Aponte a câmera para o QR Code. Mantenha o papel firme e bem iluminado.';
      const canvas=document.createElement('canvas'),context=canvas.getContext('2d',{willReadFrequently:true});
      const scan=()=>{
        if(run!==generation)return;
        try{if(video.readyState>=2&&video.videoWidth){const scale=Math.min(1,1280/video.videoWidth);canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);context.drawImage(video,0,0,canvas.width,canvas.height);const frame=context.getImageData(0,0,canvas.width,canvas.height);const code=jsQR(frame.data,frame.width,frame.height,{inversionAttempts:'attemptBoth'});if(code){scanned(code.data);return;}}}
        catch(_){stop();el('verification').textContent='Não foi possível ler a câmera. Tente novamente.';return;}
        timer=setTimeout(scan,180);
      };scan();
    }catch(error){if(run===generation){stop();el('verification').textContent=cameraError(error);}}
  });
  stopButton.addEventListener('click',()=>{stop();el('verification').textContent='Câmera parada. Toque em Abrir câmera para escanear novamente.';});
  window.addEventListener('pagehide',stop);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
}
if(typeof module!=='undefined')module.exports={canonical,sha,checkSignature,parseQR,verifyScanned,cameraError};
