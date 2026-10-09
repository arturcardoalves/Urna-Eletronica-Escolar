"""Regression tests use temporary data/fake drivers; never the installed election."""
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from print_agent import agent
from upgrade_guard import check_and_backup

ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_preserves_archived_databases_and_committed_wal(tmp_path):
    data = tmp_path / 'Servidor'
    archive = data / 'archives' / 'encerrada'
    archive.mkdir(parents=True)
    with sqlite3.connect(data / 'urna_escolar.db') as db:
        db.execute('CREATE TABLE elections(state TEXT)')
        db.execute("INSERT INTO elections VALUES ('CLOSED')")
    original = sqlite3.connect(archive / 'eleicao.db')
    try:
        original.execute('PRAGMA journal_mode=WAL')
        original.execute('CREATE TABLE totals(votes INTEGER)')
        original.execute('INSERT INTO totals VALUES (12)')
        original.commit()
        (archive / 'instrucoes.txt').write_text('Preservar documento', encoding='utf-8')
        check_and_backup(tmp_path)
        backup = next((tmp_path / 'Backups').iterdir()) / 'Servidor' / 'archives' / 'encerrada'
        with sqlite3.connect(backup / 'eleicao.db') as copy:
            assert copy.execute('SELECT votes FROM totals').fetchone() == (12,)
            assert copy.execute('PRAGMA quick_check').fetchone() == ('ok',)
        assert (backup / 'instrucoes.txt').read_text('utf-8') == 'Preservar documento'
        assert not (backup / 'eleicao.db-wal').exists()
    finally:
        original.close()


def test_upgrade_preserves_partial_first_setup_without_database(tmp_path):
    data = tmp_path / 'Servidor' / 'tls'
    data.mkdir(parents=True)
    (data / 'example.txt').write_text('fake setup material')
    check_and_backup(tmp_path)
    backup = next((tmp_path / 'Backups').iterdir()) / 'Servidor' / 'tls'
    assert (backup / 'example.txt').read_text() == 'fake setup material'


@pytest.mark.parametrize('renderer,old_limit', [
    (agent._render_zero_receipt_image, 5200),
    (agent._render_result_receipt_image, 7000),
])
def test_long_receipts_keep_third_signature(monkeypatch, renderer, old_limit):
    # Raster/layout validation with Pillow's test font; actual Atkinson and
    # physical driver/cutter alignment remain equipment checks.
    monkeypatch.setattr(agent, '_pil_font', lambda size, bold=False: ImageFont.load_default(size=size))
    signatures = []
    original = ImageDraw.ImageDraw.text

    def capture(draw, xy, text, *args, **kwargs):
        if text == 'Assinatura 3':
            signatures.append(xy)
        return original(draw, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, 'text', capture)
    paper = {'slates': [{'number': i, 'name': 'Chapa escola com nome completo para teste',
                          'votes': i, 'members': [{'name': 'Nome completo ficticio', 'role': 'Representante'}]}
                         for i in range(1, 40)], 'total': 780, 'allow_blank': True}
    image = renderer(paper)
    assert image.height > old_limit
    assert len(signatures) == 1
    assert signatures[0][1] + 22 < image.height
    # The rendered signature actually exists near the document end.
    assert image.crop((50, signatures[0][1], 500, signatures[0][1] + 30)).getextrema()[0] == 0


def test_long_raster_transmits_all_rows_in_bounded_strips():
    image = Image.new('L', (8, 66000), 0)
    payload = agent._escpos_raster_bytes(image)
    rows = 0
    while payload:
        assert payload[:4] == b'\x1dv0\x00'
        width = int.from_bytes(payload[4:6], 'little')
        height = int.from_bytes(payload[6:8], 'little')
        assert width == 1 and 0 < height <= 512
        assert payload[8:8 + height] == b'\xff' * height
        rows += height
        payload = payload[8 + width * height:]
    assert rows == 66000


def test_raw_partial_transmission_aborts_spool_job(monkeypatch):
    calls = []
    class Spooler:
        def OpenPrinter(self, name): return 'printer'
        def StartDocPrinter(self, *args): calls.append('start')
        def StartPagePrinter(self, *args): pass
        def WritePrinter(self, handle, data): return len(data) - 1
        def AbortPrinter(self, *args): calls.append('abort')
        def EndDocPrinter(self, *args): calls.append('end')
        def ClosePrinter(self, *args): calls.append('close')
    monkeypatch.setattr(agent, '_require_windows', lambda: None)
    monkeypatch.setattr(agent, 'win32print', Spooler())
    with pytest.raises(OSError, match='parte'):
        agent._escpos_print(agent.PrintJob(printer='FAKE', text='documento de teste'))
    assert calls == ['start', 'abort', 'close']


def test_optional_legacy_http_rejects_remote_clients():
    with TestClient(agent.app, client=('192.168.0.25', 1234)) as client:
        assert client.get('/health').status_code == 403
        assert client.post('/print', json={'printer': 'FAKE'}).status_code == 403
    with TestClient(agent.app, client=('127.0.0.1', 1234)) as client:
        assert client.get('/health').status_code == 200


@pytest.mark.skipif(os.name != 'nt', reason='Windows PowerShell reset implementation')
@pytest.mark.parametrize('role,filename', [('central', 'RESETAR_PC_CENTRAL_MESA.bat'), ('urna', 'RESETAR_PC_URNA.bat')])
def test_reset_embedded_powershell_only_deletes_confirmed_role_data(tmp_path, role, filename):
    local = tmp_path / 'Perfil com acentos á' / 'AppData'
    machine = tmp_path / 'ProgramData'
    for base in (local, machine):
        (base / 'UrnaEscolar').mkdir(parents=True)
        (base / 'unrelated.txt').write_text('keep')
    (local / 'UrnaEscolar' / 'desktop.json').write_text('{}')
    (machine / 'UrnaEscolar' / 'role.json').write_text('{"role":"' + role + '"}')
    for name in ('Servidor', 'logs', 'Backups'):
        (machine / 'UrnaEscolar' / name).mkdir()
        (machine / 'UrnaEscolar' / name / 'fake.txt').write_text('fake data')
    body = (ROOT / filename).read_text('utf-8').split('# POWERSHELL_RESET\n', 1)[1].split('# INTERACTIVE_RESET', 1)[0]
    script = tmp_path / 'test_reset.ps1'
    script.write_text(body + '\nReset-UrnaData $env:RESET_TEST_LOCAL $env:RESET_TEST_MACHINE $env:RESET_TEST_ROLE\n', encoding='utf-8-sig')
    env = dict(os.environ, RESET_TEST_LOCAL=str(local), RESET_TEST_MACHINE=str(machine), RESET_TEST_ROLE=role)
    ps = shutil.which('powershell.exe')
    assert ps
    completed = subprocess.run([ps, '-NoProfile', '-File', str(script)], env=env, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert not (local / 'UrnaEscolar').exists()
    assert (machine / 'UrnaEscolar' / 'role.json').exists()
    assert not (machine / 'UrnaEscolar' / 'logs').exists()
    for name in ('Servidor', 'Backups'):
        assert (machine / 'UrnaEscolar' / name).exists() == (role == 'urna')
    assert all((base / 'unrelated.txt').read_text() == 'keep' for base in (local, machine))
