"""Real local TLS transport and lost-response recovery, with synthetic documents."""
import copy
import http.client
import json
import socket
import ssl
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer
from uuid import uuid4
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from test_publication import packets
from portal.store import Archive
from publication_core.protocol import digest, InvalidPackage
from transmitter.client import transmit


def tls_pair(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, 'localhost')])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1))
            .not_valid_after(datetime.now(timezone.utc)+timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), False).sign(key, hashes.SHA256()))
    crt = tmp_path/'local.crt'; private = tmp_path/'local.key'
    crt.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); server.load_cert_chain(crt, private)
    return server, ssl.create_default_context(cafile=str(crt))


def test_transmitter_real_https_lost_reply_and_same_receipt(packets, tmp_path):
    server_context, client_context = tls_pair(tmp_path)
    state = {'drop': True, 'receipt': None, 'redirect': False}
    archive = Archive(tmp_path/'portal.sqlite3', packets['trust'])
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            if state['redirect']:
                self.send_response(307); self.send_header('Location', 'https://other.example'); self.end_headers(); return
            assert self.path == '/api/transmissions'
            raw = self.rfile.read(int(self.headers['Content-Length']))
            try:
                receipt = archive.accept(raw, archive.authorize(self.headers['Authorization'][7:]))
            except InvalidPackage:
                self.send_response(409); self.end_headers(); return
            state['receipt'] = receipt
            if state['drop']:
                state['drop'] = False
                self.close_connection = True
                self.connection.shutdown(socket.SHUT_RDWR)
                return
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(receipt).encode())
    class Server(ThreadingHTTPServer):
        def server_bind(self):
            TCPServer.server_bind(self)
            self.server_name, self.server_port = self.server_address
    server = Server(('127.0.0.1', 0), Handler)
    server.socket = server_context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        url = f'https://localhost:{server.server_port}'
        packets['trust'][packets['eid']]['public_url'] = url
        doc = copy.deepcopy(packets['docs'][0]); doc['election']['public_url'] = url
        raw = packets['build'](doc)
        args = (raw, url, 'test-only-token', packets['fp'], packets['eid'])
        with pytest.raises((http.client.RemoteDisconnected, OSError)):
            transmit(*args, context=client_context)
        receipt = transmit(*args, context=client_context)
        assert receipt == state['receipt']
        assert len(archive.rows(packets['eid'])) == 1
        assert transmit(*args, context=client_context) == receipt
        with pytest.raises(ValueError, match='Portal escolhido'):
            transmit(raw, 'https://other.example', 'test-only-token', packets['fp'], packets['eid'], context=client_context)
        state['redirect'] = True
        with pytest.raises(ValueError, match='Redirecionamento'):
            transmit(*args, context=client_context)
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_concurrent_same_package_is_one_publication(packets, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    archive = Archive(tmp_path/'portal.sqlite3', packets['trust'])
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(lambda _: archive.accept(packets['raw'][0], packets['trust']), range(4)))
    assert all(r == receipts[0] for r in receipts)
    assert len(archive.rows(packets['eid'])) == 1


def test_other_election_and_key_are_rejected(packets, tmp_path):
    archive = Archive(tmp_path/'portal.sqlite3', packets['trust'])
    doc = copy.deepcopy(packets['docs'][0]); doc['election']['id'] = str(uuid4())
    with pytest.raises(InvalidPackage): archive.accept(packets['build'](doc), packets['trust'])
    wrong = copy.deepcopy(packets['trust']); wrong[packets['eid']]['fingerprint'] = '0'*64
    with pytest.raises(InvalidPackage): archive.accept(packets['raw'][0], wrong)


def test_usb_write_failure_does_not_mark_document_exported(packets, tmp_path, monkeypatch):
    from publication_core import media
    def fail(*args): raise OSError('Mídia removida')
    monkeypatch.setattr(media.os, 'rename', fail)
    with pytest.raises(OSError): media.export_package(packets['raw'][0], tmp_path, [tmp_path])
    assert not list(tmp_path.rglob('*.uepkg'))
    assert not list(tmp_path.rglob('*.tmp'))


def test_usb_parent_junction_cannot_create_directories_outside_media(packets,tmp_path):
    import os,subprocess
    from publication_core.media import export_package
    root=tmp_path/'usb';outside=tmp_path/'outside'
    root.mkdir();outside.mkdir();link=root/'UrnaEscolar_Publicacao'
    if os.name=='nt':
        quote=lambda path:"'"+str(path).replace("'","''")+"'"
        command='New-Item -ItemType Junction -Path '+quote(link)+' -Value '+quote(outside)+' | Out-Null'
        result=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True)
        assert result.returncode==0,result.stderr
    else:link.symlink_to(outside,target_is_directory=True)
    try:
        with pytest.raises(ValueError,match='Destino USB'):
            export_package(packets['raw'][0],root,[root])
        assert list(outside.iterdir())==[]
    finally:
        if os.name=='nt':os.rmdir(link)
        else:link.unlink()
