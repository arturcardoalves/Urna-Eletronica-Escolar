import sqlite3
from pathlib import Path
import pytest
import native_runtime
from native_runtime import (PrintJournal, Api, APP_HOME, browser_arguments,
    normalize_cut_feed_mm, send_print)
from print_agent.agent import PrintJob, _escpos_finish
from upgrade_guard import check_and_backup


def test_journal_closes_database_on_success_and_rollback(tmp_path):
    journal = PrintJournal(tmp_path / 'journal.db')
    with journal.connect() as connection:
        connection.execute("INSERT INTO jobs VALUES ('committed', 'SENT')")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute('SELECT 1')
    with pytest.raises(RuntimeError):
        with journal.connect() as failed_connection:
            failed_connection.execute("INSERT INTO jobs VALUES ('rolled-back', 'STARTED')")
            raise RuntimeError('interrupted transaction')
    with pytest.raises(sqlite3.ProgrammingError):
        failed_connection.execute('SELECT 1')
    with journal.connect() as check:
        assert check.execute('SELECT id FROM jobs').fetchall() == [('committed',)]
    # This is the Windows failure that previously stopped the frozen self-test.
    journal.path.unlink()


def test_successful_print_ack_retry_does_not_repeat(tmp_path):
    journal = PrintJournal(tmp_path/'journal.db'); calls=[]
    assert journal.perform('job',lambda:calls.append(1))
    journal = PrintJournal(tmp_path/'journal.db')
    assert journal.perform('job',lambda:calls.append(2))
    assert calls == [1]


def test_interrupted_print_requires_operator(tmp_path):
    journal = PrintJournal(tmp_path/'journal.db'); calls=[]
    with journal.connect() as db:
        db.execute("INSERT INTO jobs VALUES ('job', 'STARTED')")
    assert not journal.perform('job', lambda:calls.append(1))
    assert not calls


def test_failed_print_only_retries_with_new_authorized_job(tmp_path):
    journal=PrintJournal(tmp_path/'journal.db'); calls=[]
    def fail():
        calls.append(1);raise OSError('paper failure')
    assert not journal.perform('a',fail)
    assert not journal.perform('a',fail)
    assert journal.perform('b',lambda:calls.append(2))
    assert calls == [1,2]


def test_bootstrap_never_sends_credentials():
    api=Api('https://127.0.0.1:8443',token='secret',bootstrap=True)
    with pytest.raises(ValueError):api.request('/api/deployment/identity')
    with pytest.raises(ValueError):Api('https://127.0.0.1:8443',bootstrap=True).request('/api/native/print-job')


@pytest.mark.parametrize('mode,required,forbidden', [
    ('normal', set(), {'--start-fullscreen', '--kiosk'}),
    ('fullscreen', {'--start-fullscreen'}, {'--kiosk'}),
    ('kiosk', {'--kiosk', '--edge-kiosk-type=fullscreen', '--kiosk-idle-timeout-minutes=0'}, {'--start-fullscreen'}),
])
def test_browser_modes_use_dedicated_surface_profile(mode, required, forbidden):
    url = 'https://127.0.0.1:8443/mesario'
    args = browser_arguments(url, mode, 'mesario')
    assert ('--new-window' in args) is (mode != 'kiosk')
    assert url in args
    assert '--user-data-dir=' + str(APP_HOME / ('edge-mesario-' + mode)) in args
    assert required.issubset(args)
    assert forbidden.isdisjoint(args)


def test_browser_mode_and_surface_are_validated():
    with pytest.raises(ValueError):
        browser_arguments('https://127.0.0.1:8443', 'unknown', 'admin')
    with pytest.raises(ValueError):
        browser_arguments('https://127.0.0.1:8443', 'normal', 'unknown')


@pytest.mark.parametrize('value,expected', [('10', 10), (30, 30), ('80', 80)])
def test_cut_feed_accepts_safe_millimeter_range(value, expected):
    assert normalize_cut_feed_mm(value) == expected


@pytest.mark.parametrize('value', ['', 9, 81, 'abc', None])
def test_cut_feed_rejects_invalid_or_unsafe_values(value):
    with pytest.raises(ValueError):
        normalize_cut_feed_mm(value)


def test_escpos_advances_requested_distance_before_cut():
    job = PrintJob(printer='TEST', cut=True, cut_feed_mm=80)
    finish = _escpos_finish(job)
    assert finish.endswith(b'\x1dV\x01')
    feed = finish[:-3]
    steps = []
    while feed:
        assert feed[:2] == b'\x1bJ'
        steps.append(feed[2])
        feed = feed[3:]
    assert sum(steps) == round(80 * 203 / 25.4)
    assert len(steps) == 3
    assert _escpos_finish(PrintJob(printer='TEST', cut=False)) == b''


def test_local_cut_setting_overrides_old_server_payload(monkeypatch):
    captured = []

    class FakeAgent:
        class PrintJob:
            def __init__(self, **values):
                self.values = values

        @staticmethod
        def _print(job):
            captured.append(job.values)

    monkeypatch.setattr(native_runtime, 'renderer', lambda: FakeAgent)
    send_print({'text': 'teste', 'cut_feed_mm': 10}, 'Térmica', 'escpos', 45)
    assert captured[0]['cut_feed_mm'] == 45


@pytest.mark.parametrize('state',['SEALED','OPEN'])
def test_update_blocks_active_election(tmp_path,state):
    data=tmp_path/'Servidor';data.mkdir()
    with sqlite3.connect(data/'urna_escolar.db') as db:
        db.execute('CREATE TABLE elections (state TEXT)');db.execute('INSERT INTO elections VALUES (?)',(state,))
    with pytest.raises(RuntimeError):check_and_backup(tmp_path)
    assert not (tmp_path/'Backups').exists()


def test_update_backs_up_database_and_keys(tmp_path):
    data=tmp_path/'Servidor';data.mkdir();(data/'key.txt').write_text('test-key')
    with sqlite3.connect(data/'urna_escolar.db') as db:
        db.execute('CREATE TABLE elections (state TEXT)');db.execute("INSERT INTO elections VALUES ('CONFIG')")
    check_and_backup(tmp_path)
    backup=next((tmp_path/'Backups').iterdir())/'Servidor'
    assert (backup/'key.txt').read_text()=='test-key'
    with sqlite3.connect(backup/'urna_escolar.db') as db:
        assert db.execute('SELECT state FROM elections').fetchone()[0]=='CONFIG'
