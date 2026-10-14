document.addEventListener('DOMContentLoaded',()=>{
  const notice=document.getElementById('publicationNotice');
  if(!notice)return;
  async function refresh(){
    try{
      const response=await fetch('/api/publication/status',{cache:'no-store'});
      if(!response.ok)return;
      const data=await response.json();
      notice.textContent=data.message;notice.hidden=!data.message;
    }catch(_){/* Connectivity is already reported by the station's main status. */}
  }
  refresh();setInterval(refresh,5000);
});
