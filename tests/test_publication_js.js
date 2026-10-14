const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const {canonical,sha,checkSignature}=require('../portal/static/verify.js');
test('canonical JSON is ASCII, sorted and retains accents as escaped code points',()=>{
  assert.equal(canonical({z:'çã😀',a:[1,null,true,'\n']}),'{'+'"a":[1,null,true,"\\n"],"z":"\\u00e7\\u00e3\\ud83d\\ude00"}');
});
test('browser verifier validates Ed25519 and rejects altered data',async()=>{
  const pair=crypto.generateKeyPairSync('ed25519');
  const pub=pair.publicKey.export({format:'der',type:'spki'}).subarray(-32).toString('base64url');
  const text='URNA-QR-V1\0signed document';
  const sig=crypto.sign(null,Buffer.from(text),pair.privateKey).toString('base64url');
  assert.equal(await checkSignature(pub,sig,text),await sha(Buffer.from(pub,'base64url')));
  await assert.rejects(()=>checkSignature(pub,sig,text+'changed'));
});
const {readFileSync}=require('node:fs');
const vm=require('node:vm');
function cameraBrowser(getUserMedia){
  const nodes=Object.fromEntries(['camera','startCamera','stopCamera','verification','verifiedData'].map(id=>[id,{hidden:false,disabled:false,textContent:'',events:{},addEventListener(name,fn){this.events[name]=fn;}}]));
  Object.assign(nodes.camera,{readyState:0,videoWidth:0,srcObject:null,async play(){}});
  const events={},timers=new Set();
  const document={hidden:false,getElementById:id=>nodes[id],createElement:()=>({getContext:()=>({})}),addEventListener:(name,fn)=>events[name]=fn};
  const sandbox={document,navigator:{mediaDevices:{getUserMedia}},location:{origin:'https://portal.example',hash:''},crypto:crypto.webcrypto,TextEncoder,Uint8Array,URL,atob,AbortSignal,jsQR:()=>null,setTimeout:fn=>{timers.add(fn);return fn;},clearTimeout:fn=>timers.delete(fn),window:{addEventListener:(name,fn)=>events[name]=fn}};
  vm.runInNewContext(readFileSync(require.resolve('../portal/static/verify.js'),'utf8'),sandbox);
  return {nodes,events,document,timers};
}
test('camera asks for video only and stops on stop button or page hide',async()=>{
  let stopped=0,constraints;
  const stream={getTracks:()=>[{stop(){stopped++;}}]};
  const b=cameraBrowser(async c=>{constraints=c;return stream;});
  await b.nodes.startCamera.events.click();
  assert.equal(constraints.audio,false);assert.equal(constraints.video.facingMode.ideal,'environment');
  assert.equal(b.nodes.camera.srcObject,stream);assert.equal(b.nodes.stopCamera.hidden,false);
  b.nodes.stopCamera.events.click();assert.equal(stopped,1);assert.equal(b.nodes.camera.srcObject,null);assert.equal(b.timers.size,0);
  await b.nodes.startCamera.events.click();b.document.hidden=true;b.events.visibilitychange();assert.equal(stopped,2);
});
test('camera permission denial has a clear message without file or text fallback',async()=>{
  const b=cameraBrowser(async()=>{const e=Error('denied');e.name='NotAllowedError';throw e;});
  await b.nodes.startCamera.events.click();
  assert.match(b.nodes.verification.textContent,/Acesso à câmera não permitido/);assert.equal(b.nodes.startCamera.disabled,false);
});
test('camera granted after navigation is immediately released',async()=>{
  let resolve,stopped=0;
  const b=cameraBrowser(()=>new Promise(r=>resolve=r));
  const opening=b.nodes.startCamera.events.click();b.events.pagehide();
  resolve({getTracks:()=>[{stop(){stopped++;}}]});await opening;
  assert.equal(stopped,1);assert.equal(b.nodes.camera.srcObject,null);
});
