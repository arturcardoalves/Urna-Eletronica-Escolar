import hashlib
import json
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select, func
from app import deployment
from app.db import SessionLocal
from app.models import Ballot, NativeVoteState, Urn, PairingRequest, Election, PairedComputer, Voter, DevicePrintCommand
from app.services import get_election
from app.security import sha256_text
from app.config import PRIVATE_KEY_PATH, PRIVATE_KEY_PASSWORD_PATH
from app.tally_service import tally_closed_election
from native_runtime import verification_code
from conftest import PASSWORD


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def connect(c):
    ok(c.post('/api/deployment/pairing/open'))
    token = secrets.token_urlsafe(32)
    item = ok(c.post('/api/deployment/pair', data={'token_hash': sha256_text(token), 'computer_name': 'PC-URNA'}))
    pending = ok(c.get('/api/deployment/pairing/pending'))['requests']
    assert pending[0]['code'] == verification_code(deployment.identity()['id'], token)
    approved = ok(c.post(f"/api/deployment/pairing/{item['id']}/approve"))
    assert approved['urn_code'] == 'URNA01'
    headers = {'Authorization': 'Bearer ' + token}
    ok(c.post('/api/native/heartbeat', headers=headers, data={'printer_name': 'Simulada', 'printer_mode': 'windows', 'printer_ready': 'true'}))
    ticket = ok(c.post('/api/native/browser-ticket', headers=headers))['path']
    assert c.get(ticket).status_code == 200
    assert c.get(ticket).status_code == 401  # one-time browser launch
    return headers


def complete(c, headers, success=True):
    job = ok(c.get('/api/native/print-job', headers=headers))
    assert job['pending']
    ok(c.post(f"/api/native/print-job/{job['id']}/complete", headers=headers, data={'success': str(success).lower()}))
    return job


def open_poll(c):
    headers = connect(c)
    assert c.post('/admin/seal', follow_redirects=False).status_code == 303
    c.cookies.delete('session_id')
    assert c.post('/login', data={'username':'mesa', 'password':PASSWORD}, follow_redirects=False).status_code == 303
    opening = ok(c.post('/api/mesario/open/prepare', data={'password': PASSWORD}))
    assert c.post('/api/mesario/open/commit', data={'ticket': opening['ticket']}).status_code == 409
    zero = complete(c, headers)
    assert zero['kind'] == 'zero'
    assert zero['payload']['copies'] == 3
    assert ok(c.get('/api/mesario/open/ready', params={'ticket': opening['ticket']}))['ready']
    ok(c.post('/api/mesario/open/commit', data={'ticket': opening['ticket']}))
    return headers


def authorize(c, enrollment='1000'):
    ok(c.post('/api/mesario/authorize', data={'enrollment': enrollment, 'urn_code': 'URNA01'}))
    return ok(c.get('/api/urna/URNA01/authorization'))['token']


def vote(c, token, blank=False):
    return c.post('/api/urna/URNA01/vote', data={'token': token, 'choice_type': 'blank' if blank else 'slate', 'slate_number': 10})


def count_votes():
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(Ballot))


def test_first_install_opens_setup(client):
    r = client.get('/admin', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == '/setup'
    assert client.get('/api/mesario/status').status_code == 401


def test_first_setup_accepts_loopback_hostname_alias(client):
    data = {'username': 'admin', 'display_name': 'Admin local', 'password': 'Senha-local-230!'}
    accepted = client.post('/setup', headers={'Origin': 'https://localhost'}, data=data, follow_redirects=False)
    assert accepted.status_code == 303 and accepted.headers['location'] == '/login'


def test_first_setup_rejects_remote_origin(client):
    response = client.post(
        '/setup',
        headers={'Origin': 'https://192.168.0.50:8443'},
        data={'username': 'admin', 'display_name': 'Admin remoto', 'password': 'Senha-local-230!'},
    )
    assert response.status_code == 403


def test_login_page_for_returning_install(prepared):
    prepared.cookies.clear()
    r = prepared.get('/mesario', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == '/login'


def test_pairing_requires_admin_window_and_valid_token(prepared):
    c = prepared
    assert c.get('/api/native/print-job').status_code == 401
    assert c.post('/api/deployment/pair', data={'token_hash': 'a'*64, 'computer_name':'pc'}).status_code == 409
    ok(c.post('/api/deployment/pairing/open'))
    assert c.post('/api/deployment/pair', data={'token_hash': 'bad', 'computer_name':'pc'}).status_code == 400
    item = ok(c.post('/api/deployment/pair', data={'token_hash':'a'*64, 'computer_name':'pc'}))
    with SessionLocal() as db:
        db.get(PairingRequest, item['id']).expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    assert c.get('/api/deployment/pair/'+item['id']).status_code == 410


def test_complete_20_vote_election_and_tally(prepared):
    c = prepared
    headers = open_poll(c)
    for i in range(20):
        token = authorize(c, str(1000+i))
        receipt = ok(vote(c, token, blank=i%5==0))
        assert receipt['recorded'] and receipt['managed_print']
        assert ok(vote(c, token, blank=i%5==0))['recorded']
        assert count_votes() == i+1  # lost-response replay must not add a vote
        job = complete(c, headers)
        assert job['kind'] == 'ballot' and job['payload']['copies'] == 1
        assert ok(c.post('/api/urna/URNA01/vote-status', data={'token': token}))['print_state'] == 'DONE'
    closing = ok(c.post('/api/mesario/close', data={'password':PASSWORD, 'confirm_close':'yes'}))
    result = closing['result']
    assert result['total'] == 20 and result['blank'] == 4
    assert result['slates'][0]['votes'] == 16
    bu = complete(c, headers)
    assert bu['kind'] == 'result' and bu['payload']['copies'] == 3
    assert ok(c.get('/api/mesario/close/ready', params={'ticket':closing['ticket']}))['ready']
    pdf = c.get('/reports/result.pdf')
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
    c.cookies.delete('session_id')
    assert c.post('/login', data={'username':'admin','password':PASSWORD}, follow_redirects=False).status_code == 303
    r = c.post('/admin/new-election', data={'confirm_text':'NOVA ELEICAO'}, follow_redirects=False)
    assert r.status_code == 303, r.text
    assert ok(c.post('/api/native/heartbeat', headers=headers))['election_state'] == 'CONFIG'
    assert count_votes() == 0
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(PairedComputer)) == 1


def test_failure_reprint_never_adds_vote_and_blocks_next_voter(prepared):
    c = prepared; h = open_poll(c)
    token = authorize(c)
    ok(vote(c, token))
    assert c.post('/api/mesario/authorize', data={'enrollment':'1001','urn_code':'URNA01'}).status_code == 409
    first = complete(c, h, False)
    assert c.post('/api/mesario/authorize', data={'enrollment':'1001','urn_code':'URNA01'}).status_code == 409
    ok(c.post('/api/mesario/reprint', data={'urn_code':'URNA01'}))
    second = complete(c, h)
    assert second['id'] != first['id'] and count_votes() == 1
    authorize(c, '1001')
    with SessionLocal() as db:
        urn = db.scalar(select(Urn))
        assert not db.get(NativeVoteState, urn.id).encrypted_payload
        assert urn.pending_reprint_ballot_id is None


def test_offline_native_worker_blocks_authorization(prepared):
    c = prepared; open_poll(c)
    with SessionLocal() as db:
        db.scalar(select(Urn)).native_seen_at = datetime.utcnow() - timedelta(seconds=20)
        db.commit()
    r = c.post('/api/mesario/authorize', data={'enrollment':'1000','urn_code':'URNA01'})
    assert r.status_code == 409 and 'desconectado' in r.text


def test_browser_cannot_complete_native_print(prepared):
    c = prepared; open_poll(c)
    assert c.post('/api/urna/URNA01/print-complete', data={'ballot_id':'fake'}).status_code == 409
    assert c.get('/api/urna/URNA01/print-command').status_code == 409


def test_vote_and_print_command_roll_back_together(prepared, monkeypatch):
    c = prepared; open_poll(c); token = authorize(c)
    def fail(*args):
        raise RuntimeError('simulated storage failure')
    monkeypatch.setattr(deployment, 'record_vote', fail)
    try:
        vote(c, token)
    except RuntimeError:
        pass
    assert count_votes() == 0
    with SessionLocal() as db:
        voter = db.scalar(select(Voter).where(Voter.enrollment=='1000'))
        assert voter.status == 'IN_PROGRESS'
    assert not ok(c.post('/api/urna/URNA01/vote-status', data={'token':token}))['recorded']


def test_native_receipt_survives_database_reopen(prepared):
    c = prepared; h = open_poll(c); token = authorize(c); ok(vote(c, token))
    from app.db import engine
    engine.dispose()
    assert ok(c.post('/api/urna/URNA01/vote-status', data={'token':token}))['recorded']
    assert ok(vote(c, token))['recorded'] and count_votes() == 1
    complete(c,h)


def test_untrusted_local_control_rejected(client):
    assert client.get('/api/local/status').status_code == 403
    assert client.post('/api/local/stop').status_code == 403


def test_concurrent_replay_records_one_vote(prepared):
    from concurrent.futures import ThreadPoolExecutor
    c = prepared; h = open_poll(c); token = authorize(c)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: vote(c, token), range(2)))
    assert all(r.status_code == 200 for r in responses)
    assert count_votes() == 1
    complete(c, h)


def test_local_control_reports_health_and_refuses_open_shutdown(prepared):
    from app.config import DATA_DIR
    key = secrets.token_urlsafe(32)
    (DATA_DIR/'control.key').write_text(key)
    c = prepared; open_poll(c)
    data = ok(c.get('/api/local/status',headers={'X-Local-Control':key}))
    assert data['database'] and data['state'] == 'OPEN' and data['urns'][0]['connected']
    assert c.post('/api/local/stop',headers={'X-Local-Control':key}).status_code == 409
