"""Real TLS handshakes in memory; no router, listener or external server needed."""
import ssl
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from native_runtime import Api
from scripts import generate_tls


def certificates(tmp_path, monkeypatch, legacy=False):
    for constant, filename in [('CA_KEY', 'ca.key'), ('CA_CERT', 'ca.crt'),
                               ('SERVER_KEY', 'server.key'), ('SERVER_CERT', 'server.crt')]:
        monkeypatch.setattr(generate_tls, constant, tmp_path / filename)
    monkeypatch.setattr(generate_tls, 'private_ipv4s', lambda: ['127.0.0.1'])
    key, ca = generate_tls.make_ca()
    if legacy:
        now = datetime.now(timezone.utc)
        ca = (x509.CertificateBuilder().subject_name(ca.subject).issuer_name(ca.subject)
              .public_key(key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=30))
              .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
              .add_extension(x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True)
              .sign(key, hashes.SHA256()))
    generate_tls.make_server(key, ca)
    return ca.public_bytes(serialization.Encoding.PEM).decode('ascii')


def handshake(client_context, hostname='127.0.0.1'):
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(generate_tls.SERVER_CERT, generate_tls.SERVER_KEY)
    client_in, client_out = ssl.MemoryBIO(), ssl.MemoryBIO()
    server_in, server_out = ssl.MemoryBIO(), ssl.MemoryBIO()
    client = client_context.wrap_bio(client_in, client_out, server_hostname=hostname)
    server = server_context.wrap_bio(server_in, server_out, server_side=True)
    client_done = server_done = False
    for _ in range(20):
        try:
            client.do_handshake()
            client_done = True
        except ssl.SSLWantReadError:
            pass
        data = client_out.read()
        if data:
            server_in.write(data)
        try:
            server.do_handshake()
            server_done = True
        except ssl.SSLWantReadError:
            pass
        data = server_out.read()
        if data:
            client_in.write(data)
        if client_done and server_done:
            return
    pytest.fail('TLS handshake did not finish')


def test_new_certificates_pass_strict_tls(tmp_path, monkeypatch):
    pem = certificates(tmp_path, monkeypatch)
    context = Api('https://127.0.0.1', ca=pem).context
    assert context.verify_flags & ssl.VERIFY_X509_STRICT
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    handshake(context)


def test_legacy_ca_compatibility_keeps_hostname_validation(tmp_path, monkeypatch):
    pem = certificates(tmp_path, monkeypatch, legacy=True)
    context = Api('https://127.0.0.1', ca=pem).context
    assert not (context.verify_flags & ssl.VERIFY_X509_STRICT)
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    handshake(context)
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(context, hostname='wrong-host.invalid')


def test_untrusted_issuer_is_rejected(tmp_path, monkeypatch):
    certificates(tmp_path, monkeypatch)
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Untrusted test CA')])
    now = datetime.now(timezone.utc)
    other_ca = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
                .public_key(other_key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=30))
                .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                .sign(other_key, hashes.SHA256()))
    context = Api('https://127.0.0.1', ca=other_ca.public_bytes(serialization.Encoding.PEM).decode()).context
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(context)
