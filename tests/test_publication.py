"""All election identities and totals here are synthetic; no production data."""
import copy
import io
import json
import sys
import zipfile
from pathlib import Path
from uuid import uuid4
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from publication_core.protocol import (canonical, digest, sign_package, verify_package,
                                       verify_qr, InvalidPackage)
from publication_core.documents import render_pdf, links, qr_image
from publication_core.media import export_package, find_packages
from portal.app import create_app


@pytest.fixture
def packets():
    key = Ed25519PrivateKey.generate()
    eid = str(uuid4())
    urns = [{'id': str(uuid4()), 'code': f'URNA{i:02d}', 'name': f'Urna {i}'} for i in (1, 2)]
    election = {'id': eid, 'name': 'Eleição de teste isolado', 'school': 'Escola fictícia',
                'public_url': 'https://eleicao.example', 'identified': True, 'registered': 25,
                'allow_blank': True, 'sealed_at': '2026-10-13T10:00:00+00:00', 'config_hash': 'a'*64,
                'slates': [{'number': 10, 'name': 'Chapa fictícia', 'members': [], 'photo': None}], 'urns': urns}
    base = {'schema_version': 1, 'id': str(uuid4()), 'kind': 'configuration', 'revision': 1,
            'previous': None, 'correction': '', 'created_at': '2026-10-13T10:00:00+00:00',
            'election': election, 'urn_id': None, 'configuration_digest': None, 'totals': None,
            'evidence':{'software_version':'2.3.0','zero_issued_at':None,'opened_at':None,'closed_at':None,'zero_snapshot_hash':None,'ballot_set_hash':None}}
    def build(doc):
        return sign_package(doc, {'document.pdf': render_pdf(doc, links(doc, key), {})}, key)
    config = build(base)
    docs = [base]
    raw = [config]
    for kind, hour in [('zero', '11'), ('result', '12')]:
        for index, urn in enumerate(urns):
            d = copy.deepcopy(base)
            d.update(id=str(uuid4()), kind=kind, urn_id=urn['id'], configuration_digest=digest(canonical(base)), created_at=f'2026-10-13T{hour}:00:00+00:00')
            count = index + 1 if kind == 'result' else 0
            d['totals'] = {'registered': 25, 'slates': [{'number': 10, 'votes': count}], 'blank': 0, 'null': 0, 'total': count, 'attendance': count}
            d['evidence'].update(zero_issued_at='2026-10-13T11:00:00+00:00',zero_snapshot_hash='b'*64)
            if kind=='result':d['evidence'].update(opened_at='2026-10-13T11:01:00+00:00',closed_at='2026-10-13T12:00:00+00:00',ballot_set_hash='c'*64)
            docs.append(d); raw.append(build(d))
    fp = digest(key.public_key().public_bytes_raw())
    trust = {eid: {'fingerprint': fp, 'public_url': election['public_url'], 'token_sha256': digest(b'test-only-token')}}
    return {'key': key, 'docs': docs, 'raw': raw, 'build': build, 'eid': eid, 'fp': fp, 'trust': trust}


def upload(client, raw, token='test-only-token'):
    return client.post('/api/transmissions', content=raw, headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/octet-stream'})


def test_signed_packages_and_qr_roundtrip(packets):
    for raw, doc in zip(packets['raw'], packets['docs']):
        p = verify_package(raw, packets['fp'], packets['eid'])
        assert p['document'] == doc
        qr = links(doc, packets['key'])['verification']
        assert verify_qr(qr, packets['fp'], raw)['trusted']
    with pytest.raises(InvalidPackage):
        verify_qr(links(packets['docs'][1], packets['key'])['verification'], packets['fp'], packets['raw'][2])


@pytest.mark.parametrize('attack', ['pdf', 'signature', 'extra', 'traversal', 'duplicate', 'voters', 'wrong-key', 'wrong-election'])
def test_rejects_tampering_and_private_fields(packets, attack):
    raw = packets['raw'][0]
    if attack == 'wrong-key':
        with pytest.raises(InvalidPackage): verify_package(raw, '0'*64)
        return
    if attack == 'wrong-election':
        with pytest.raises(InvalidPackage): verify_package(raw, expected_election=str(uuid4()))
        return
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        content = {n: z.read(n) for n in z.namelist()}
    if attack == 'pdf': content['document.pdf'] += b'changed'
    if attack == 'signature':
        envelope = json.loads(content['manifest.json']); envelope['signature'] = 'A'*86
        content['manifest.json'] = canonical(envelope)
    if attack in ('extra', 'traversal'): content['voters.csv' if attack == 'extra' else '../escape'] = b'secret'
    if attack == 'voters':
        envelope = json.loads(content['manifest.json']); envelope['manifest']['document']['voters'] = []
        content['manifest.json'] = canonical(envelope)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for n, v in content.items(): z.writestr(n, v)
        if attack == 'duplicate':
            with pytest.warns(UserWarning): z.writestr('document.pdf', b'%PDF-fake')
    with pytest.raises(InvalidPackage): verify_package(buf.getvalue())


def test_qr_rasters_decode_at_thermal_resolution(packets):
    import zxingcpp
    for doc in packets['docs'][1:]:
        for kind in ('consultation', 'verification'):
            text = links(doc, packets['key'])[kind]
            raster = qr_image(text)
            assert raster.width <= 528
            assert zxingcpp.read_barcode(raster).text == text


def test_both_qrs_decode_inside_actual_thermal_document(packets):
    import zxingcpp
    from print_agent.agent import _render_zero_receipt_image, _render_result_receipt_image
    for renderer,index in [(_render_zero_receipt_image,1),(_render_result_receipt_image,3)]:
        doc=packets['docs'][index];qr=links(doc,packets['key'])
        paper={'institution':doc['election']['school'],'election':doc['election']['name'],
               'slates':[{'number':10,'name':'Chapa fictícia','members':[],'votes':doc['totals']['total']}],
               'publication':qr,'total':doc['totals']['total'],'allow_blank':True}
        image=renderer(paper)
        decoded={result.text for result in zxingcpp.read_barcodes(image)}
        assert qr['consultation'] in decoded and qr['verification'] in decoded


def test_usb_export_is_byte_identical_and_conflicts_fail(packets, tmp_path):
    raw = packets['raw'][0]
    path = export_package(raw, tmp_path, allowed_drives=[tmp_path])
    assert path.read_bytes() == raw
    assert export_package(raw, tmp_path, allowed_drives=[tmp_path]) == path
    assert find_packages([tmp_path]) == [path]
    path.write_bytes(b'changed')
    with pytest.raises(ValueError): export_package(raw, tmp_path, allowed_drives=[tmp_path])
    with pytest.raises(ValueError): export_package(raw, tmp_path, allowed_drives=[])


def test_portal_stage_order_dedup_partial_final_and_restart(packets, tmp_path):
    app = create_app(tmp_path, packets['trust'])
    with TestClient(app) as c:
        assert upload(c, packets['raw'][0], 'wrong').status_code == 401
        assert upload(c, packets['raw'][1]).status_code == 409
        first = upload(c, packets['raw'][0]); assert first.status_code == 200, first.text
        assert upload(c, packets['raw'][0]).json() == first.json()
        assert upload(c, packets['raw'][3]).status_code == 409
        for raw in packets['raw'][1:4]: assert upload(c, raw).status_code == 200
        summary = app.state.archive.summary(packets['eid'])
        assert summary['status'] == 'Parcial' and summary['totals']['total'] == 1
        assert upload(c, packets['raw'][4]).status_code == 200
        assert c.get('/').status_code == 200
        assert c.get('/elections/'+packets['eid']).status_code == 200
        docid = packets['docs'][3]['id']
        assert c.get('/documents/'+docid).status_code == 200
        assert c.get('/documents/'+docid+'/pdf').content.startswith(b'%PDF')
        assert c.get('/documents/'+docid+'/package').content == packets['raw'][3]
        assert c.get('/verify').status_code == 200
        assert c.get('/documents/missing').status_code == 404
    reopened = create_app(tmp_path, packets['trust'])
    assert reopened.state.archive.summary(packets['eid'])['status'] == 'Definitivo'
    assert reopened.state.archive.summary(packets['eid'])['totals']['total'] == 3
    with TestClient(reopened) as c:
        assert upload(c, packets['raw'][0]).json() == first.json()


def test_portal_preserves_revisions_and_blocks_changed_totals(packets, tmp_path):
    app = create_app(tmp_path, packets['trust'])
    with TestClient(app) as c:
        for raw in packets['raw']: assert upload(c, raw).status_code == 200
        doc = copy.deepcopy(packets['docs'][3])
        doc.update(id=str(uuid4()), revision=2, previous=digest(canonical(doc)), correction='Nota pública de esclarecimento')
        raw = packets['build'](doc)
        assert upload(c, raw).status_code == 200
        assert c.get('/documents/'+packets['docs'][3]['id']+'/package').content == packets['raw'][3]
        bad = copy.deepcopy(doc)
        bad.update(id=str(uuid4()), revision=3, previous=digest(canonical(doc)))
        bad['totals'].update(total=2, attendance=2)
        bad['totals']['slates'][0]['votes'] = 2
        assert upload(c, packets['build'](bad)).status_code == 409
        duplicate = copy.deepcopy(doc); duplicate['correction'] = 'Outro conteúdo para o mesmo ID'
        assert upload(c, packets['build'](duplicate)).status_code == 409


def test_publication_integrates_real_voting_flow(prepared, tmp_path):
    from test_integration import connect, ok, complete, authorize, vote
    from conftest import PASSWORD
    from app.db import SessionLocal
    from app.models import PublicationDocument
    from app import publication
    from sqlalchemy import select
    c = prepared
    h = connect(c)
    response = c.post('/admin/publication/configure', data={'url': 'https://eleicao.example'}, follow_redirects=False)
    assert response.status_code == 303, response.text
    response = c.post('/admin/seal', follow_redirects=False)
    assert response.status_code == 303, response.text
    assert c.post('/admin/publication/configure', data={'url': 'https://other.example'}).status_code == 409
    assert c.get('/admin/publication').status_code == 200
    c.cookies.delete('session_id')
    c.post('/login', data={'username':'mesa', 'password':PASSWORD})
    opening = ok(c.post('/api/mesario/open/prepare', data={'password': PASSWORD}))
    with SessionLocal() as db:
        zero = db.scalar(select(PublicationDocument).where(PublicationDocument.kind=='zero'))
        assert zero and not publication.ready_to_export(db, zero)
    job = complete(c, h)
    assert job['payload']['paper']['publication']['verification'].startswith('https://eleicao.example/verify#UE1|')
    ok(c.post('/api/mesario/open/commit', data={'ticket': opening['ticket']}))
    token = authorize(c); ok(vote(c, token)); complete(c, h)
    token = authorize(c, '1001'); ok(vote(c, token, blank=True)); complete(c, h)
    closing = ok(c.post('/api/mesario/close', data={'password': PASSWORD, 'confirm_close':'yes'}))
    assert closing['result']['total'] == 2
    complete(c, h)
    with SessionLocal() as db:
        rows = db.scalars(select(PublicationDocument).order_by(PublicationDocument.created_at)).all()
        assert [r.kind for r in rows] == ['configuration', 'zero', 'result']
        assert all(publication.ready_to_export(db, r) for r in rows)
        data = [r.package for r in rows]
        p = verify_package(data[0]); eid = p['document']['election']['id']
        for raw in data:
            doc = verify_package(raw)['document']
            assert 'Eleitor teste' not in canonical(doc).decode()
        assert verify_package(data[-1])['document']['totals']['blank'] == 1
    portal = create_app(tmp_path, {eid: {'fingerprint': p['fingerprint'], 'public_url': 'https://eleicao.example', 'token_sha256': digest(b'test-only-token')}})
    with TestClient(portal) as pc:
        for raw in data:
            reply = upload(pc, raw); assert reply.status_code == 200, reply.text
        assert portal.state.archive.summary(eid)['totals']['total'] == 2
    assert c.get('/admin/publication').status_code == 403
    c.cookies.delete('session_id')
    c.post('/login',data={'username':'admin','password':PASSWORD})
    result_id=verify_package(data[-1])['document']['id']
    response=c.post('/admin/publication/'+result_id+'/rectify',data={'reason':'Nota adicional sem mudar contagens'},follow_redirects=False)
    assert response.status_code==303,response.text
    with SessionLocal() as db:
        new=db.scalars(select(PublicationDocument).where(PublicationDocument.kind=='result').order_by(PublicationDocument.revision.desc())).first()
        assert new.revision==2 and not publication.ready_to_export(db,new)
        assert verify_package(new.package)['document']['totals']==verify_package(data[-1])['document']['totals']
    complete(c,h)
    with SessionLocal() as db:
        new=db.scalars(select(PublicationDocument).where(PublicationDocument.kind=='result').order_by(PublicationDocument.revision.desc())).first()
        assert publication.ready_to_export(db,new)


def test_second_urn_without_votes_exports_zero_not_global_result(prepared):
    import secrets
    from test_integration import connect,ok,complete,authorize,vote
    from conftest import PASSWORD
    from app.security import sha256_text
    from app.db import SessionLocal
    from app.models import PublicationDocument
    from sqlalchemy import select
    c=prepared;first=connect(c)
    token=secrets.token_urlsafe(32)
    item=ok(c.post('/api/deployment/pair',data={'token_hash':sha256_text(token),'computer_name':'PC-URNA2'}))
    approved=ok(c.post(f"/api/deployment/pairing/{item['id']}/approve"))
    assert approved['urn_code']=='URNA02'
    second={'Authorization':'Bearer '+token}
    ok(c.post('/api/native/heartbeat',headers=second,data={'printer_name':'Simulada2','printer_mode':'windows','printer_ready':'true'}))
    c.post('/admin/publication/configure',data={'url':'https://eleicao.example'})
    assert c.post('/admin/seal',follow_redirects=False).status_code==303
    c.cookies.delete('session_id');c.post('/login',data={'username':'mesa','password':PASSWORD})
    opening=ok(c.post('/api/mesario/open/prepare',data={'password':PASSWORD}))
    complete(c,first);complete(c,second)
    ok(c.post('/api/mesario/open/commit',data={'ticket':opening['ticket']}))
    token=authorize(c);ok(vote(c,token));complete(c,first)
    closing=ok(c.post('/api/mesario/close',data={'password':PASSWORD,'confirm_close':'yes'}))
    assert closing['result']['total']==1
    bu1=complete(c,first);bu2=complete(c,second)
    assert bu1['payload']['paper']['total']==1
    assert bu2['payload']['paper']['total']==0
    assert all(s['votes']==0 for s in bu2['payload']['paper']['slates'])
    with SessionLocal() as db:
        row=db.scalar(select(PublicationDocument).where(PublicationDocument.kind=='result',PublicationDocument.urn_code=='URNA02'))
        assert verify_package(row.package)['document']['totals']['total']==0


def test_cloudflare_schema_matches_python():
    from publication_core.schema import Document
    schema=Path(__file__).resolve().parents[1]/'portal/cloudflare/document-schema.json'
    assert json.loads(schema.read_text('utf-8'))==Document.model_json_schema()


def test_public_candidate_photo_metadata_is_removed(prepared):
    from PIL import Image,PngImagePlugin
    from test_integration import connect
    from app.config import DATA_DIR
    from app.db import SessionLocal
    from app.models import Slate,PublicationDocument
    from sqlalchemy import select
    path=DATA_DIR/'user_static'/'candidate-test.png'
    path.parent.mkdir(parents=True,exist_ok=True)
    metadata=PngImagePlugin.PngInfo();metadata.add_text('private-note','metadata-that-must-not-leave-central')
    Image.new('RGB',(100,100),'white').save(path,pnginfo=metadata)
    with SessionLocal() as db:
        db.scalar(select(Slate)).logo_path='/user-static/candidate-test.png';db.commit()
    c=prepared;connect(c)
    c.post('/admin/publication/configure',data={'url':'https://eleicao.example'})
    response=c.post('/admin/seal',follow_redirects=False);assert response.status_code==303,response.text
    with SessionLocal() as db:
        raw=db.scalar(select(PublicationDocument).where(PublicationDocument.kind=='configuration')).package
        photo=verify_package(raw)['assets']['photo-10.png']
        assert b'metadata-that-must-not-leave-central' not in photo
        with Image.open(io.BytesIO(photo)) as im:assert not im.info


def test_two_urns_vote_concurrently_without_crossing_totals(prepared):
    import secrets
    from concurrent.futures import ThreadPoolExecutor
    from test_integration import connect,ok,complete,authorize
    from conftest import PASSWORD
    from app.main import app
    from app.security import sha256_text
    c=prepared;first=connect(c)
    secret=secrets.token_urlsafe(32)
    item=ok(c.post('/api/deployment/pair',data={'token_hash':sha256_text(secret),'computer_name':'Segunda urna fictícia'}))
    assert ok(c.post(f"/api/deployment/pairing/{item['id']}/approve"))['urn_code']=='URNA02'
    second={'Authorization':'Bearer '+secret}
    ok(c.post('/api/native/heartbeat',headers=second,data={'printer_name':'Simulada2','printer_mode':'windows','printer_ready':'true'}))
    c.post('/admin/publication/configure',data={'url':'https://eleicao.example'})
    assert c.post('/admin/seal',follow_redirects=False).status_code==303
    c.cookies.delete('session_id');c.post('/login',data={'username':'mesa','password':PASSWORD})
    opening=ok(c.post('/api/mesario/open/prepare',data={'password':PASSWORD}))
    complete(c,first);complete(c,second)
    ok(c.post('/api/mesario/open/commit',data={'ticket':opening['ticket']}))
    with TestClient(app,base_url='https://testserver') as other:
        path=ok(c.post('/api/native/browser-ticket',headers=second))['path']
        assert other.get(path).status_code==200
        token1=authorize(c,'1000')
        ok(c.post('/api/mesario/authorize',data={'enrollment':'1001','urn_code':'URNA02'}))
        token2=ok(other.get('/api/urna/URNA02/authorization'))['token']
        requests=[(c,'URNA01',token1,'slate'),(other,'URNA02',token2,'blank')]
        def cast(args):
            client,code,token,choice=args
            return ok(client.post('/api/urna/'+code+'/vote',data={'token':token,'choice_type':choice,'slate_number':10}))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(cast,requests))
        assert all(r['recorded'] for r in results)
        complete(c,first);complete(c,second)
    closing=ok(c.post('/api/mesario/close',data={'password':PASSWORD,'confirm_close':'yes'}))
    assert closing['result']['total']==2 and closing['result']['blank']==1
    assert closing['result']['per_urn']['URNA01']['slates'][0]['votes']==1
    assert closing['result']['per_urn']['URNA02']['blank']==1


def test_windows_key_roundtrip(tmp_path):
    from publication_core.keys import signing_key
    eid = str(uuid4())
    if sys.platform != 'win32': pytest.skip('DPAPI requer Windows')
    one = signing_key(tmp_path, eid)
    two = signing_key(tmp_path, eid)
    assert one.public_key().public_bytes_raw() == two.public_key().public_bytes_raw()
    assert one.private_bytes_raw() not in (tmp_path/(eid+'.key')).read_bytes()


def test_portal_current_election_and_camera_only(packets, tmp_path):
    app = create_app(tmp_path, packets['trust'])
    with TestClient(app) as c:
        assert 'Não há votações no momento.' in c.get('/').text
        assert upload(c, packets['raw'][0]).status_code == 200
        page = c.get('/').text
        assert packets['docs'][0]['election']['name'] in page
        assert 'Eleições e arquivo público' not in page
        for raw in packets['raw'][1:]:
            assert upload(c, raw).status_code == 200
        assert 'Não há votações no momento.' in c.get('/').text
        assert c.get('/documents/'+packets['docs'][3]['id']).status_code == 200
        verify = c.get('/verify')
        assert 'id="startCamera"' in verify.text
        assert '<input' not in verify.text and '<textarea' not in verify.text
        assert verify.headers['Permissions-Policy'] == 'camera=(self), microphone=()'
        assert c.get('/static/jsQR.js').status_code == 200

def test_admin_usb_export_waits_for_print_and_reexports_identical_bytes(prepared, tmp_path, monkeypatch):
    from conftest import PASSWORD
    from test_integration import connect, ok, complete
    from publication_core import media
    from app import publication_routes
    from app.db import SessionLocal
    from app.models import PublicationDocument
    from sqlalchemy import select
    c = prepared
    drive = tmp_path / 'midia-simulada'
    drive.mkdir()
    monkeypatch.setattr(media, 'removable_drives', lambda: [drive])
    monkeypatch.setattr(publication_routes, 'removable_drives', lambda: [drive])
    h = connect(c)
    assert c.post('/admin/publication/configure', data={'url':'https://eleicao.example'}, follow_redirects=False).status_code == 303
    assert c.post('/admin/seal', follow_redirects=False).status_code == 303
    c.cookies.delete('session_id')
    c.post('/login', data={'username':'mesa','password':PASSWORD})
    ok(c.post('/api/mesario/open/prepare', data={'password':PASSWORD}))
    assert c.post('/admin/publication/export', data={'drive':str(drive)}).status_code == 403
    assert c.post('/api/local/publication/export', data={'drive':str(drive)}).status_code in (401,403)
    c.cookies.delete('session_id')
    c.post('/login', data={'username':'admin','password':PASSWORD})
    assert c.post('/admin/publication/export', data={'drive':str(drive)}, follow_redirects=False).status_code == 303
    found = media.find_packages([drive])
    assert [verify_package(p.read_bytes())['document']['kind'] for p in found] == ['configuration']
    with SessionLocal() as db:
        zero = db.scalar(select(PublicationDocument).where(PublicationDocument.kind=='zero'))
        assert zero and not zero.exported
    complete(c,h)
    assert c.post('/admin/publication/export', data={'drive':str(drive)}, follow_redirects=False).status_code == 303
    found = media.find_packages([drive])
    original = {p.name:p.read_bytes() for p in found}
    assert set(verify_package(raw)['document']['kind'] for raw in original.values()) == {'configuration','zero'}
    assert c.post('/admin/publication/export', data={'drive':str(drive)}, follow_redirects=False).status_code == 303
    assert {p.name:p.read_bytes() for p in media.find_packages([drive])} == original
    # Removing/reinserting a disk with conflicting bytes must never overwrite them.
    conflicting = found[0]
    conflicting.write_bytes(b'conteudo adulterado na midia simulada')
    reply=c.post('/admin/publication/export', data={'drive':str(drive)}, follow_redirects=False)
    assert reply.status_code == 409
    assert conflicting.read_bytes() == b'conteudo adulterado na midia simulada'
