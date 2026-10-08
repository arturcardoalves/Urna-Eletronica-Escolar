from __future__ import annotations

import hashlib
from contextlib import contextmanager
import http.cookiejar
import json
import os
import sqlite3
import ssl
import subprocess
import sys
import threading
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes

VERSION = "2.3.0"
APP_HOME = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "UrnaEscolar"
MACHINE_HOME = Path(os.environ.get("PROGRAMDATA", str(Path.home()))) / "UrnaEscolar"
CREATE_FLAGS = 0x08000000 if os.name == "nt" else 0
print_lock = threading.Lock()


class ConnectionError(RuntimeError):
    pass


class Api:
    def __init__(self, url, ca=None, token=None, control=None, bootstrap=False):
        self.url = url.rstrip("/")
        self.token, self.control = token, control
        if bootstrap:
            # ONLY the public identity endpoint may use this instance.
            self.context = ssl._create_unverified_context()
        else:
            self.context = ssl.create_default_context(cadata=ca) if ca else ssl.create_default_context()
            if ca:
                certificate = x509.load_pem_x509_certificate(ca.encode())
                try:
                    certificate.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
                except x509.ExtensionNotFound:
                    # Older project CAs/leaf certificates lack SKI/AKI. Keep
                    # certificate-chain, signature, expiry and hostname checks,
                    # using the pre-3.13 compatibility rules only for that CA.
                    # Do not replace a paired Central's identity or private key.
                    self.context.verify_flags &= ~ssl.VERIFY_X509_STRICT
        self.bootstrap = bootstrap
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=self.context))

    def request(self, path, data=None):
        if self.bootstrap and (path != "/api/deployment/identity" or data is not None or self.token):
            raise ValueError("Bootstrap permits only the public identity")
        headers = {}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if self.control:
            headers["X-Local-Control"] = self.control
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(self.url + path, body, headers=headers)
        try:
            with self.opener.open(req, timeout=4) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                detail = json.load(exc).get("detail", "Falha na solicitação.")
            except Exception:
                detail = "Falha na solicitação."
            raise ConnectionError(str(detail)) from exc
        except (OSError, urllib.error.URLError) as exc:
            if "CERTIFICATE_VERIFY_FAILED" in str(exc):
                raise ConnectionError("Confira data e hora do Windows. O certificado da Central não pôde ser validado.") from exc
            raise ConnectionError("Servidor desconectado. Confira se a Central está aberta e os cabos estão conectados.") from exc


def certificate_id(pem):
    return x509.load_pem_x509_certificate(pem.encode()).fingerprint(hashes.SHA256()).hex()


def verification_code(server_id, token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    code = hashlib.sha256((server_id + token_hash).encode()).hexdigest()[:8].upper()
    return code[:4] + "-" + code[4:]


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        json.dump(dict(data), stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_config():
    try:
        return json.loads((APP_HOME / "desktop.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(config):
    atomic_json(APP_HOME / "desktop.json", config)


def store_token(token):
    import win32crypt
    APP_HOME.mkdir(parents=True, exist_ok=True)
    path = APP_HOME / "device.credential"
    temp = path.with_suffix(".tmp")
    temp.write_bytes(win32crypt.CryptProtectData(token.encode(), "Urna Escolar", None, None, None, 0))
    os.replace(temp, path)


def load_token():
    import win32crypt
    return win32crypt.CryptUnprotectData((APP_HOME / "device.credential").read_bytes(), None, None, None, 0)[1].decode()


def install_certificate(pem):
    path = APP_HOME / "central.crt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pem, "ascii")
    result = subprocess.run(["certutil.exe", "-user", "-addstore", "Root", str(path)], capture_output=True, creationflags=CREATE_FLAGS, timeout=30)
    if result.returncode:
        raise RuntimeError("O Windows não permitiu preparar o certificado. Peça ao responsável pela conta do computador para liberar essa instalação.")


def edge_path():
    for root in [os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", ""), os.environ.get("LOCALAPPDATA", "")]:
        path = Path(root) / "Microsoft/Edge/Application/msedge.exe"
        if path.is_file():
            return path
    raise RuntimeError("Microsoft Edge não encontrado. Instale o Edge antes de usar este computador.")


def browser_arguments(url, mode="normal", surface=None):
    """Build the Edge command for the requested visible operating mode."""
    if mode not in ("normal", "fullscreen", "kiosk"):
        raise ValueError("Modo de abertura inválido.")
    if surface not in (None, "admin", "mesario", "urna"):
        raise ValueError("Área do navegador inválida.")
    if surface is None:
        path = urllib.parse.urlparse(url).path
        surface = "mesario" if path == "/mesario" else "admin"
    # A dedicated profile per mode forces Edge to start a distinct process.
    # Otherwise an already-open normal window may absorb a kiosk/fullscreen
    # request and silently ignore the requested display mode.
    profile = APP_HOME / ("edge-" + surface + "-" + mode)
    args = ["--no-first-run", "--user-data-dir=" + str(profile)]
    if mode == "fullscreen":
        args += ["--new-window", "--start-fullscreen", url]
    elif mode == "kiosk":
        args += ["--kiosk", url, "--edge-kiosk-type=fullscreen", "--kiosk-idle-timeout-minutes=0"]
    else:
        args += ["--new-window", url]
    return args


def open_browser(url, mode="normal", surface=None):
    args = [str(edge_path()), *browser_arguments(url, mode, surface)]
    return subprocess.Popen(args, creationflags=CREATE_FLAGS)


def renderer():
    from print_agent import agent
    return agent


def font_ready():
    regular = bold = False
    dirs = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts", Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts"]
    for directory in dirs:
        if directory.exists():
            for font in directory.iterdir():
                name = font.name.lower().replace("-", "").replace("_", "")
                if "atkinsonhyperlegible" in name:
                    regular |= "regular" in name
                    bold |= "bold" in name
    return regular and bold


def list_printers():
    return renderer().printers()["printers"]


def printer_available(name):
    if not name:
        return False
    agent = renderer()
    try:
        handle = agent.win32print.OpenPrinter(name)
        try:
            info = agent.win32print.GetPrinter(handle, 2)
            # Many drivers return 0 even without paper; this is not a physical guarantee.
            error_flags = 0x1 | 0x2 | 0x8 | 0x10 | 0x20 | 0x40 | 0x80 | 0x400 | 0x1000 | 0x100000 | 0x400000
            return not bool(info.get("Status", 0) & error_flags) and not bool(info.get("Attributes", 0) & 0x400)
        finally:
            agent.win32print.ClosePrinter(handle)
    except Exception:
        return False


def send_print(payload, printer_name, mode):
    agent = renderer()
    job = agent.PrintJob(**{**payload, "printer": printer_name, "mode": mode})
    with print_lock:
        agent._print(job)


class PrintJournal:
    """Only opaque job IDs and outcomes. Never save ballot choices or timestamps.

    STARTED is durable before touching the spooler. A crash in that interval is
    ambiguous and requires mesario action, even if the paper might have printed.
    """
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, state TEXT NOT NULL)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            # sqlite3's transaction context commits/rolls back but does not
            # close the connection. Windows keeps the database file locked.
            db.close()

    def perform(self, job_id, operation):
        with self.connect() as db:
            row = db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row:
                return row[0] == "SENT"
            db.execute("INSERT INTO jobs VALUES (?, 'STARTED')", (job_id,))
        try:
            operation()
            success = True
        except Exception:
            success = False
        with self.connect() as db:
            db.execute("UPDATE jobs SET state=? WHERE id=?", ("SENT" if success else "FAILED", job_id))
        return success


def acquire_instance(role):
    APP_HOME.mkdir(parents=True, exist_ok=True)
    handle = (APP_HOME / (role + ".lock")).open("a+b")
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        if handle.read(1) == b"":
            handle.write(b"0"); handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    return handle
