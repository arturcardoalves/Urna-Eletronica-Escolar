from __future__ import annotations

import os
import secrets
import socket
import sys
import threading
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psutil
import uvicorn
from cryptography import x509
from cryptography.x509.oid import ExtensionOID

import lan_runtime

VERSION="2.3.0"
ROOT=Path(sys.executable).resolve().parent if getattr(sys,"frozen",False) else Path(__file__).resolve().parent.parent/"URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN"
os.chdir(ROOT)
sys.path.insert(0,str(ROOT))
PROGRAMDATA=Path(os.environ["URNA_BUILD_DATA_DIR"]) if os.environ.get("URNA_BUILD_DATA_DIR") else Path(os.environ.get("PROGRAMDATA",str(ROOT)))/"UrnaEscolar"
SERVER_DATA=PROGRAMDATA/"Servidor"
LOG_DIR=PROGRAMDATA/"logs"
SERVER_DATA.mkdir(parents=True,exist_ok=True)
LOG_DIR.mkdir(parents=True,exist_ok=True)
os.environ["URNA_DATA_DIR"]=str(SERVER_DATA)
os.environ["URNA_DB_PATH"]=str(SERVER_DATA/"urna_escolar.db")
from scripts.generate_tls import make_ca,make_server,SERVER_CERT,SERVER_KEY,private_ipv4s


def log(message):
    with (LOG_DIR/"server.log").open("a",encoding="utf-8") as f:
        f.write(datetime.now().isoformat(timespec="seconds")+" "+message+"\n")


def ensure_tls():
    ca_key,ca_cert=make_ca()
    now=datetime.now(timezone.utc)
    if ca_cert.not_valid_after_utc<=now:
        raise RuntimeError("Certificado da Central expirado. Necessário renovar e reconectar as urnas.")
    required=set(private_ipv4s())|{"127.0.0.1"}
    needs=True
    if SERVER_CERT.exists() and SERVER_KEY.exists():
        cert=x509.load_pem_x509_certificate(SERVER_CERT.read_bytes())
        san=cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        ips={str(value) for value in san.get_values_for_type(x509.IPAddress)}
        dns=set(san.get_values_for_type(x509.DNSName))
        needs=not required.issubset(ips) or socket.gethostname() not in dns or cert.not_valid_after_utc<now+timedelta(days=7)
    if needs:
        make_server(ca_key,ca_cert)
        log("Certificado HTTPS preparado para os endereços locais.")
    return needs


def main():
    log("Iniciando servidor "+VERSION)
    ensure_tls()
    control=SERVER_DATA/"control.key"
    if not control.exists():control.write_text(secrets.token_urlsafe(32),"ascii")
    config=uvicorn.Config("app.main:app",host="0.0.0.0",port=8443,ssl_keyfile=str(SERVER_KEY),ssl_certfile=str(SERVER_CERT),log_level="warning",log_config=None,access_log=False)
    config.load()
    server=uvicorn.Server(config)
    from app import deployment
    deployment.stop_server=lambda:setattr(server,"should_exit",True)
    stop=threading.Event()
    def discovery():
        try:lan_runtime.serve_discovery(stop,deployment.identity)
        except Exception:log("Descoberta de rede indisponível. Confira porta UDP 38443 e firewall.")
    def monitor():
        while not stop.wait(5):
            try:
                if ensure_tls():config.ssl.load_cert_chain(str(SERVER_CERT),str(SERVER_KEY))
                parent=os.environ.get("URNA_PARENT_PID")
                if parent and not psutil.pid_exists(int(parent)):
                    log("Central foi fechada. Encerrando servidor.")
                    server.should_exit=True
                    return
            except Exception:
                log("Falha ao conferir rede/certificado. Confira data e hora do Windows.")
    threading.Thread(target=discovery,daemon=True).start()
    threading.Thread(target=monitor,daemon=True).start()
    try:server.run()
    finally:stop.set();log("Servidor encerrado.")


if __name__=="__main__":
    try:main()
    except Exception:
        log("Falha ao iniciar:\n"+traceback.format_exc())
        sys.exit(1)
