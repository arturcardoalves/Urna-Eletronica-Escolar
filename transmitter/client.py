"""No redirects, no silent retries and no trust in a URL supplied by removable media."""
import json
import ssl
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from uuid import UUID
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN'))
from publication_core.protocol import verify_package, InvalidPackage
from publication_core.schema import Election


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirecionamento recusado. Confira o endereço do portal.')


def transmit(raw, portal_url, token, fingerprint, election_id, *, context=None):
    """Caller must obtain operator confirmation before invoking this function."""
    url = Election.url(portal_url.strip())
    if not fingerprint or not election_id or not token or any(c.isspace() for c in token):
        raise ValueError('Informe eleição, chave confiável e credencial de transmissão')
    validated = verify_package(raw, fingerprint, election_id)
    if validated['document']['election']['public_url'] != url:
        raise ValueError('Portal escolhido difere do endereço lacrado')
    request = urllib.request.Request(url + '/api/transmissions', data=raw, method='POST',
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/octet-stream'})
    opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=context or ssl.create_default_context()))
    try:
        with opener.open(request, timeout=30) as response:
            content = response.read(65537)
            if len(content) > 65536:
                raise ValueError('Resposta excessiva do portal')
            receipt = json.loads(content)
    except urllib.error.HTTPError as exc:
        # Do not echo tokens, request headers or arbitrary HTML error pages.
        raise ValueError(f'Portal recusou a transmissão (HTTP {exc.code}). Nenhum arquivo foi apagado; confira a configuração e a sequência dos documentos.') from exc
    if (receipt.get('document_id') != validated['document']['id'] or
        receipt.get('election_id') != election_id or receipt.get('sha256') != validated['package_hash']):
        raise InvalidPackage('Comprovante não corresponde ao pacote enviado')
    UUID(receipt['protocol'])
    if datetime.fromisoformat(receipt['received_at']).tzinfo is None:
        raise InvalidPackage('Comprovante sem horário completo')
    return receipt
