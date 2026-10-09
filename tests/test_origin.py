"""Exercise the real origin middleware without TestClient's worker thread."""
import asyncio

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.main import security_headers


@pytest.mark.parametrize('path', ['/setup', '/login'])
@pytest.mark.parametrize('origin,allowed', [
    ('https://127.0.0.1:8443', True),
    ('null', False),
    ('https://evil.example', False),
    ('https://localhost:8443', False),
    ('http://127.0.0.1:8443', False),
    ('https://127.0.0.1:9443', False),
])
def test_form_origin_guard(path, origin, allowed):
    request = Request({
        'type': 'http', 'method': 'POST', 'scheme': 'https',
        'path': path, 'query_string': b'',
        'server': ('127.0.0.1', 8443), 'client': ('127.0.0.1', 1234),
        'headers': [(b'host', b'127.0.0.1:8443'), (b'origin', origin.encode())],
    })
    called = []

    async def endpoint(request):
        called.append(True)
        return Response(status_code=200)

    response = asyncio.run(security_headers(request, endpoint))
    assert response.status_code == (200 if allowed else 403)
    assert bool(called) == allowed
    if allowed:
        assert response.headers['Referrer-Policy'] == 'same-origin'
