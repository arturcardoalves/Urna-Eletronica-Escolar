"""Windows deployment: explicit pairing, native print worker and visible health.

The discovery packet is not trusted. Pairing is approved by an administrator,
with the same certificate-bound code visibly confirmed on both computers.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import socket
import threading
import uuid
from datetime import datetime, timedelta

from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .audit import append_audit
from .auth import get_db, require_role
from .config import APP_VERSION, DATA_DIR, MAX_URNS
from .device_auth import create_urn_session, set_urn_session_cookie
from .models import (BrowserLaunch, DevicePrintCommand, ElectionState, NativeVoteState,
                     PairedComputer, PairingRequest, Setting, Urn, UrnStatus, User)
from .security import hash_device_secret, sha256_text
from .services import DomainError, get_election

router = APIRouter()
admin_only = require_role("ADMIN")
write_lock = threading.RLock()
stop_server = None


def identity():
    pem = (DATA_DIR / "tls" / "urna_escolar_ca.crt").read_text("ascii")
    fingerprint = x509.load_pem_x509_certificate(pem.encode()).fingerprint(hashes.SHA256()).hex()
    return {"id": fingerprint, "ca_pem": pem, "name": socket.gethostname(), "version": APP_VERSION}


def pairing_code(token_hash):
    code = hashlib.sha256((identity()["id"] + token_hash).encode()).hexdigest()[:8].upper()
    return code[:4] + "-" + code[4:]


def _fernet():
    path = DATA_DIR / "native_print.key"
    with write_lock:
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(Fernet.generate_key())
        return Fernet(path.read_bytes())


def native_online(urn):
    return bool(urn.native_seen_at and (datetime.utcnow() - urn.native_seen_at).total_seconds() < 15)


def require_ready(urn, election):
    if urn.status != UrnStatus.AVAILABLE.value:
        raise DomainError("A urna está ocupada ou aguarda solução de uma impressão.")
    if urn.managed_print and not native_online(urn):
        raise DomainError("O aplicativo da urna está desconectado. Abra-o no computador da urna.")
    if urn.managed_print and election.paper_enabled and urn.print_enabled and not urn.printer_ready:
        raise DomainError("Confira a impressora e o teste no aplicativo da urna.")


def clear_previous_vote(db, urn):
    state = db.get(NativeVoteState, urn.id)
    if state:
        state.encrypted_payload = ""
    urn.pending_reprint_ballot_id = None
    urn.reprint_authorized = False


def record_vote(db, urn, token, paper):
    """Called in the SAME transaction as cast_vote; never enqueue after commit."""
    state = db.get(NativeVoteState, urn.id)
    if state:
        db.delete(state)
        db.flush()
    enabled = paper["enabled"]
    payload = {"layout": "ballot", "paper": paper, "text": "", "title": "Cédula",
               "copies": 1, "cut": True, "paper_width_mm": 80}
    state = NativeVoteState(urn_id=urn.id, token_hash=sha256_text(token), job_id=str(uuid.uuid4()),
                            encrypted_payload=_fernet().encrypt(json.dumps(payload, ensure_ascii=False).encode()).decode() if enabled else "",
                            state="PENDING" if enabled else "DONE")
    db.add(state)
    urn.status = UrnStatus.PRINTING.value if enabled else UrnStatus.AVAILABLE.value


def vote_receipt(db, urn, token):
    state = db.get(NativeVoteState, urn.id)
    if state and hmac.compare_digest(state.token_hash, sha256_text(token)):
        return {"ok": True, "recorded": True, "managed_print": True, "print_state": state.state}
    return None


def reprint_vote(db, urn):
    state = db.get(NativeVoteState, urn.id)
    if not state or not state.encrypted_payload or state.state == "PENDING":
        raise HTTPException(409, "Não há cédula disponível para reimpressão.")
    state.job_id = str(uuid.uuid4())  # An explicit authorization creates a NEW physical job.
    state.state = "PENDING"
    urn.status = UrnStatus.PRINTING.value
    urn.reprint_authorized = False


def native_device(request: Request, db: Session = Depends(get_db)):
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer ") or len(header) > 200:
        raise HTTPException(401, "Abra o aplicativo da urna e conecte-o à Central.")
    device = db.execute(select(PairedComputer).where(PairedComputer.token_hash == sha256_text(header[7:]))).scalar_one_or_none()
    if not device:
        raise HTTPException(401, "Este computador precisa ser conectado novamente pela Central.")
    return db.get(Urn, device.urn_id)


@router.get("/api/deployment/identity")
def public_identity():
    return identity()


@router.post("/api/deployment/pair")
def request_pair(token_hash: str = Form(...), computer_name: str = Form(...), db: Session = Depends(get_db)):
    if not re.fullmatch(r"[0-9a-f]{64}", token_hash):
        raise HTTPException(400, "Identificador inválido.")
    with write_lock:
        now = datetime.utcnow()
        window = db.get(Setting, "pairing_until")
        if not window or datetime.fromisoformat(window.value) < now:
            raise HTTPException(409, "Na Central, abra Conectar urna e habilite a conexão.")
        db.execute(delete(PairingRequest).where(PairingRequest.expires_at < now))
        existing = db.execute(select(PairingRequest).where(PairingRequest.token_hash == token_hash)).scalar_one_or_none()
        if existing:
            return {"id": existing.id}
        if db.scalar(select(func.count()).select_from(PairingRequest)) >= 10:
            raise HTTPException(429, "Há muitas solicitações. Aguarde cinco minutos.")
        item = PairingRequest(token_hash=token_hash, computer_name=computer_name.strip()[:80], expires_at=now + timedelta(minutes=5))
        db.add(item)
        db.commit()
        return {"id": item.id}


@router.get("/api/deployment/pair/{pair_id}")
def pair_status(pair_id: str, db: Session = Depends(get_db)):
    item = db.get(PairingRequest, pair_id)
    if not item or item.expires_at < datetime.utcnow():
        raise HTTPException(410, "A conexão expirou. Procure a Central novamente.")
    urn = db.get(Urn, item.urn_id) if item.urn_id else None
    return {"approved": bool(urn), "urn_code": urn.code if urn else None}


@router.post("/api/deployment/pairing/open")
def open_pairing(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    if get_election(db).state != ElectionState.CONFIG.value:
        raise HTTPException(409, "Conecte os computadores antes de lacrar a eleição.")
    setting = db.get(Setting, "pairing_until")
    until = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
    if setting:
        setting.value = until
    else:
        db.add(Setting(key="pairing_until", value=until))
    db.commit()
    return {"ok": True}


@router.get("/api/deployment/pairing/pending")
def pending_pairings(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    items = db.scalars(select(PairingRequest).where(PairingRequest.expires_at > datetime.utcnow(), PairingRequest.urn_id.is_(None))).all()
    return {"requests": [{"id": p.id, "name": p.computer_name, "code": pairing_code(p.token_hash)} for p in items]}


@router.post("/api/deployment/pairing/{pair_id}/approve")
def approve_pairing(pair_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    with write_lock:
        if get_election(db).state != ElectionState.CONFIG.value:
            raise HTTPException(409, "A eleição já foi lacrada.")
        item = db.get(PairingRequest, pair_id)
        if not item or item.expires_at < datetime.utcnow():
            raise HTTPException(410, "Solicitação expirada.")
        if item.urn_id:
            return {"ok": True, "urn_code": db.get(Urn, item.urn_id).code}
        paired_ids = list(db.scalars(select(PairedComputer.urn_id)))
        urn = db.scalars(select(Urn).where(Urn.id.not_in(paired_ids)).order_by(Urn.id)).first()
        if not urn:
            if db.scalar(select(func.count()).select_from(Urn)) >= MAX_URNS:
                raise HTTPException(409, "As três urnas já estão conectadas.")
            codes = set(db.scalars(select(Urn.code)))
            number = next(i for i in range(1, 100) if f"URNA{i:02}" not in codes)
            urn = Urn(code=f"URNA{number:02}", name=f"Urna {number:02}", device_secret_hash=hash_device_secret(secrets.token_urlsafe(32)), printer_mode="windows")
            db.add(urn)
            db.flush()
        db.add(PairedComputer(urn_id=urn.id, token_hash=item.token_hash, computer_name=item.computer_name))
        urn.managed_print = True
        urn.printer_ready = False
        item.urn_id = urn.id
        append_audit(db, "COMPUTER_PAIRED", user.username, {"urn": urn.code, "computer": item.computer_name})
        db.commit()
        return {"ok": True, "urn_code": urn.code}


@router.post("/api/native/heartbeat")
def native_heartbeat(printer_name: str = Form(""), printer_mode: str = Form("windows"), printer_ready: bool = Form(False), urn: Urn = Depends(native_device), db: Session = Depends(get_db)):
    urn.native_seen_at = datetime.utcnow()
    urn.agent_online = True
    urn.printer_ready = printer_ready and bool(printer_name)
    urn.printer_name = printer_name[:220] or None
    urn.printer_mode = printer_mode if printer_mode in ("windows", "escpos") else "windows"
    election = get_election(db)
    db.commit()
    return {"ok": True, "urn_code": urn.code, "status": urn.status, "election_state": election.state,
            "print_required": bool(urn.print_enabled and election.paper_enabled), "version": APP_VERSION}


@router.post("/api/native/browser-ticket")
def browser_ticket(urn: Urn = Depends(native_device), db: Session = Depends(get_db)):
    token = secrets.token_urlsafe(32)
    db.execute(delete(BrowserLaunch).where(BrowserLaunch.expires_at < datetime.utcnow()))
    db.add(BrowserLaunch(token_hash=sha256_text(token), urn_id=urn.id, expires_at=datetime.utcnow() + timedelta(seconds=60)))
    db.commit()
    return {"path": "/native/launch?ticket=" + token}


@router.get("/native/launch")
def launch_browser(ticket: str, request: Request, db: Session = Depends(get_db)):
    with write_lock:
        item = db.get(BrowserLaunch, sha256_text(ticket))
        if not item or item.expires_at < datetime.utcnow():
            raise HTTPException(401, "Clique Iniciar urna novamente no aplicativo.")
        urn = db.get(Urn, item.urn_id)
        session = create_urn_session(db, urn)
        db.delete(item)
        db.commit()
        response = RedirectResponse("/urna/" + urn.code, status_code=303)
        set_urn_session_cookie(response, request, urn.code, session)
        response.headers["Cache-Control"] = "no-store"
        return response


@router.get("/api/native/print-job")
def next_print_job(urn: Urn = Depends(native_device), db: Session = Depends(get_db)):
    state = db.get(NativeVoteState, urn.id)
    if state and state.state == "PENDING":
        payload = json.loads(_fernet().decrypt(state.encrypted_payload.encode()))
        return {"pending": True, "id": state.job_id, "kind": "ballot", "payload": payload}
    job = db.scalars(select(DevicePrintCommand).where(DevicePrintCommand.urn_id == urn.id, DevicePrintCommand.completed_at.is_(None)).order_by(DevicePrintCommand.created_at)).first()
    if job:
        return {"pending": True, "id": job.id, "kind": job.kind, "payload": json.loads(job.payload_json)}
    return {"pending": False}


@router.post("/api/native/print-job/{job_id}/complete")
def complete_job(job_id: str, success: bool = Form(...), urn: Urn = Depends(native_device), db: Session = Depends(get_db)):
    with write_lock:
        state = db.get(NativeVoteState, urn.id)
        if state and state.job_id == job_id:
            if state.state == "PENDING":
                state.state = "DONE" if success else "FAILED"
                urn.status = UrnStatus.AVAILABLE.value if success else UrnStatus.PRINT_ERROR.value
                # Keep the last payload for an explicit mesario paper-failure report;
                # erase it before authorizing the next voter. Never audit vote times.
        else:
            job = db.get(DevicePrintCommand, job_id)
            if not job or job.urn_id != urn.id:
                raise HTTPException(404, "Impressão não encontrada.")
            if job.completed_at is None:
                job.success = success
                job.completed_at = datetime.utcnow()
                if not success:
                    urn.status = UrnStatus.PRINT_ERROR.value
                elif urn.status == UrnStatus.PRINT_ERROR.value and (not state or state.state == "DONE"):
                    urn.status = UrnStatus.AVAILABLE.value
                append_audit(db, "URN_DOCUMENT_PRINT_OK" if success else "URN_DOCUMENT_PRINT_FAILED", f"URN:{urn.code}", {"document": job.kind})
        db.commit()
        return {"ok": True}


def local_control(request: Request):
    if not request.client or request.client.host not in ("127.0.0.1", "::1", "testclient"):
        raise HTTPException(403, "Operação local.")
    key_path = DATA_DIR / "control.key"
    expected = key_path.read_text("ascii") if key_path.exists() else ""
    if not expected or not hmac.compare_digest(expected, request.headers.get("x-local-control", "")):
        raise HTTPException(403, "Controle local não autorizado.")


@router.get("/api/local/status", dependencies=[Depends(local_control)])
def local_status(db: Session = Depends(get_db)):
    election = get_election(db)
    urns = db.scalars(select(Urn).order_by(Urn.code)).all()
    return {"ok": True, "database": True, "state": election.state, "version": APP_VERSION,
            "urns": [{"code": u.code, "connected": native_online(u), "printer_ready": native_online(u) and u.printer_ready,
                      "printer": u.printer_name or "", "status": u.status} for u in urns]}


@router.post("/api/local/stop", dependencies=[Depends(local_control)])
def local_stop(db: Session = Depends(get_db)):
    if get_election(db).state == ElectionState.OPEN.value:
        raise HTTPException(409, "Encerre a votação na Mesa antes de desligar a Central.")
    if stop_server:
        stop_server()
    return {"ok": True}


def register(app, templates):
    app.include_router(router)

    @app.get("/admin/pairing")
    def pairing_page(request: Request, user: User = Depends(admin_only)):
        return templates.TemplateResponse(request=request, name="pairing.html", context={"user": user})
