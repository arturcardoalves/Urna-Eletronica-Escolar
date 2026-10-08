const status = document.getElementById('pairStatus');
document.getElementById('enablePairing').onclick = async () => {
  try {
    const r = await fetch('/api/deployment/pairing/open', {method:'POST'});
    const d = await r.json();
    status.textContent = r.ok ? 'Conexão permitida. Na urna, clique Procurar Central.' : d.detail;
  } catch (_) { status.textContent = 'Central desconectada.'; }
};
async function refreshPairing() {
  try {
    const r = await fetch('/api/deployment/pairing/pending');
    if (!r.ok) { status.textContent = 'Entre como administrador para conectar a urna.'; return; }
    const d = await r.json();
    const root = document.getElementById('pairRequests'); root.replaceChildren();
    for (const item of d.requests) {
      const box = document.createElement('div'); box.className = 'card';
      const name = document.createElement('h2'); name.textContent = item.name;
      const code = document.createElement('p'); code.textContent = 'Código de conferência: ' + item.code;
      const button = document.createElement('button'); button.textContent = 'Os códigos são iguais — conectar';
      button.onclick = async () => {
        button.disabled = true;
        try {
          const result = await fetch('/api/deployment/pairing/' + encodeURIComponent(item.id) + '/approve', {method:'POST'});
          const data = await result.json();
          status.textContent = result.ok ? data.urn_code + ' autorizada. Conclua na tela da urna.' : data.detail;
        } catch (_) { status.textContent = 'Conexão interrompida. Confira novamente.'; }
        refreshPairing();
      };
      box.append(name, code, button); root.append(box);
    }
  } catch (_) { status.textContent = 'Central desconectada.'; }
}
setInterval(refreshPairing, 2000); refreshPairing();
