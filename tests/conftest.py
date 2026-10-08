import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DATA = tempfile.TemporaryDirectory(prefix='urna-230-tests-')
os.environ['URNA_DATA_DIR'] = TEST_DATA.name
os.environ['URNA_DB_PATH'] = str(Path(TEST_DATA.name) / 'test.db')
sys.path.insert(0, str(ROOT / 'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN'))
sys.path.insert(0, str(ROOT / 'installer'))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import engine, init_db, SessionLocal
from app.config import DB_PATH
from app.models import User, Slate, Voter
from app.security import hash_password
from app.auth import create_session
from app.services import get_election
from scripts.generate_tls import make_ca, make_server

PASSWORD = 'Teste-local-230!'

@pytest.fixture
def client():
    engine.dispose()
    for suffix in ('', '-wal', '-shm'):
        Path(str(DB_PATH) + suffix).unlink(missing_ok=True)
    init_db()
    ca_key, ca_cert = make_ca()
    with TestClient(app, base_url='https://testserver') as c:
        yield c
    engine.dispose()

@pytest.fixture
def prepared(client):
    with SessionLocal() as db:
        admin = User(username='admin', display_name='Admin teste', password_hash=hash_password(PASSWORD), role='ADMIN')
        db.add(admin)
        db.add(User(username='mesa', display_name='Mesa teste', password_hash=hash_password(PASSWORD), role='MESARIO'))
        db.add(Slate(number=10, name='Chapa teste'))
        for i in range(25):
            db.add(Voter(enrollment=str(1000+i), name=f'Eleitor teste {i}', class_code='302', shift='Noturno'))
        get_election(db).institution_name = 'Escola teste'
        db.flush()
        session = create_session(db, admin)
        db.commit()
    client.cookies.set('session_id', session)
    return client
