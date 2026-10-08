from __future__ import annotations

import ipaddress
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

BASE = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("URNA_DATA_DIR", str(BASE / "data"))).expanduser().resolve()
TLS = DATA / "tls"
TLS.mkdir(parents=True, exist_ok=True)

CA_KEY = TLS / "urna_escolar_ca.key"
CA_CERT = TLS / "urna_escolar_ca.crt"
SERVER_KEY = TLS / "server.key"
SERVER_CERT = TLS / "server.crt"


def private_ipv4s() -> list[str]:
    found = {"127.0.0.1"}
    import psutil
    for addresses in psutil.net_if_addrs().values():
        for address in addresses:
            if address.family == socket.AF_INET:
                ip = ipaddress.ip_address(address.address)
                if ip.is_private and not ip.is_link_local:
                    found.add(address.address)
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None, family=socket.AF_INET):
            ip = info[4][0]
            try:
                addr = ipaddress.ip_address(ip)
                if addr.is_private or addr.is_loopback:
                    found.add(ip)
            except ValueError:
                pass
    except Exception:
        pass
    # UDP connect does not send data; it only asks the OS which local interface
    # would be used. This often finds the LAN address more reliably.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))
        found.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return sorted(found)


def make_ca():
    if CA_KEY.exists() and CA_CERT.exists():
        key = serialization.load_pem_private_key(CA_KEY.read_bytes(), password=None)
        cert = x509.load_pem_x509_certificate(CA_CERT.read_bytes())
        return key, cert
    if CA_KEY.exists() or CA_CERT.exists():
        raise RuntimeError("Certificado da Central incompleto. Restaure o backup antes de iniciar.")
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Urna Escolar Local"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Urna Escolar CA Local"),
    ])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False,
        ), critical=True)
        .sign(key, hashes.SHA256())
    )
    CA_KEY.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ))
    CA_CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key, cert


def make_server(ca_key, ca_cert):
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    hostname = socket.gethostname()
    san = [x509.DNSName("localhost"), x509.DNSName(hostname)]
    for ip in private_ipv4s():
        san.append(x509.IPAddress(ipaddress.ip_address(ip)))
    now = datetime.now(timezone.utc)
    subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Urna Escolar Local"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    SERVER_KEY.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ))
    SERVER_CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return hostname, private_ipv4s()


if __name__ == "__main__":
    ca_key, ca_cert = make_ca()
    hostname, ips = make_server(ca_key, ca_cert)
    print("HTTPS preparado.")
    print(f"Certificado da CA: {CA_CERT}")
    print(f"Servidor: https://127.0.0.1:8443")
    for ip in ips:
        if ip != "127.0.0.1":
            print(f"Rede local: https://{ip}:8443")
    print("Nos computadores clientes, instale urna_escolar_ca.crt como autoridade confiável do usuário.")
