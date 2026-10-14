"""Run with uvicorn portal.app:create_app --factory, behind HTTPS."""
import json
import os
import sys
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN'))
from publication_core.protocol import MAX_PACKAGE, InvalidPackage, verify_package
from .store import Archive


def create_app(data_dir=None, trust=None):
    folder = Path(data_dir or os.environ.get('PORTAL_DATA_DIR', str(ROOT / 'portal/data')))
    folder.mkdir(parents=True, exist_ok=True)
    if trust is None:
        trust_path = os.environ.get('PORTAL_TRUST_FILE')
        trust = json.loads(Path(trust_path).read_text('utf-8')) if trust_path else {}
    archive = Archive(folder / 'publications.sqlite3', trust)
    app = FastAPI(title='Portal da Urna Escolar', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.archive = archive
    templates = Jinja2Templates(directory=str(ROOT / 'portal/templates'))
    app.mount('/static', StaticFiles(directory=ROOT / 'portal/static'), name='static')

    @app.middleware('http')
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers['Permissions-Policy'] = 'camera=(self), microphone=()'
        response.headers['Permissions-Policy'] = 'camera=(self), microphone=()'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        return response

    @app.post('/api/transmissions')
    async def receive(request: Request):
        auth = request.headers.get('authorization', '')
        allowed = archive.authorize(auth[7:]) if auth.startswith('Bearer ') and len(auth) <= 512 else {}
        if not allowed:
            raise HTTPException(401, 'Credencial de transmissão inválida')
        if request.headers.get('content-type', '').split(';')[0] != 'application/octet-stream':
            raise HTTPException(415, 'Envie um pacote .uepkg')
        body = bytearray()
        async for part in request.stream():
            if len(body) + len(part) > MAX_PACKAGE:
                raise HTTPException(413, 'Pacote muito grande')
            body.extend(part)
        try:
            # SQLite and signature verification run outside the event loop.
            from starlette.concurrency import run_in_threadpool
            result = await run_in_threadpool(archive.accept, bytes(body), allowed)
            return JSONResponse(result)
        except InvalidPackage as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get('/')
    def home(request: Request):
        with archive.connect() as db:
            current = db.execute("SELECT election FROM documents WHERE kind='configuration' AND revision=1 ORDER BY received DESC,id DESC LIMIT 1").fetchone()
        summary = archive.summary(current['election']) if current else None
        if summary and summary['status'] != 'Definitivo':
            return templates.TemplateResponse(request=request, name='election.html', context=summary)
        return templates.TemplateResponse(request=request, name='home.html', context={})

    @app.get('/elections/{eid}')
    def election(request: Request, eid: str):
        summary = archive.summary(eid)
        if not summary:
            raise HTTPException(404, 'Eleição ainda não publicada')
        return templates.TemplateResponse(request=request, name='election.html', context=summary)

    def document(docid):
        row = archive.get(docid)
        if not row:
            raise HTTPException(404, 'Documento ainda não transmitido. Consulte novamente após a publicação.')
        return row, verify_package(row['package'])

    @app.get('/documents/{docid}')
    def doc_page(request: Request, docid: str):
        row, p = document(docid)
        return templates.TemplateResponse(request=request, name='document.html', context={'doc': p['document'], 'fingerprint': p['fingerprint'], 'receipt': json.loads(row['receipt']), 'digest': p['digest']})

    @app.get('/documents/{docid}/package')
    def package(docid: str):
        row, _ = document(docid)
        return Response(row['package'], media_type='application/octet-stream', headers={'Content-Disposition': f'attachment; filename="{docid}.uepkg"'})

    @app.get('/documents/{docid}/manifest')
    def manifest(docid: str):
        _, p = document(docid)
        return JSONResponse(p['envelope'], headers={'Content-Disposition': f'attachment; filename="{docid}.json"'})

    @app.get('/documents/{docid}/pdf')
    def pdf(docid: str):
        _, p = document(docid)
        return Response(p['assets']['document.pdf'], media_type='application/pdf', headers={'Content-Disposition': f'inline; filename="{docid}.pdf"', 'Content-Security-Policy': "sandbox"})

    @app.get('/documents/{docid}/photos/{name}')
    def photo(docid: str, name: str):
        _, p = document(docid)
        if not name.startswith('photo-') or not name.endswith('.png') or name not in p['assets']:
            raise HTTPException(404)
        return Response(p['assets'][name], media_type='image/png')

    @app.get('/verify')
    def verify(request: Request):
        return templates.TemplateResponse(request=request, name='verify.html', context={})

    @app.get('/health')
    def health():
        return {'status': 'ok'}
    return app
