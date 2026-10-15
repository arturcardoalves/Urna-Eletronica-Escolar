from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives import serialization

from .config import BASE_DIR, PUBLIC_KEY_PATH
from .models import AuditEvent, Election, Setting
from .security import canonical_json, sha256_text

GENESIS = "0" * 64


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def software_manifest() -> dict:
    """Gera a impressão digital dos componentes executáveis da instalação.

    Em desenvolvimento, usa os arquivos-fonte. No pacote PyInstaller, o código
    Python fica empacotado no executável; por isso o hash inclui o EXE do
    servidor e o aplicativo Central/Urna, além dos recursos
    web relevantes. Dados de eleição, chaves, uploads e sons personalizados
    continuam fora do hash por serem mutáveis.
    """
    entries: list[dict] = []

    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        app_root = exe.parent.parent
        deployed = [
            (exe, "Servidor/UrnaEscolarServidor.exe"),
            (app_root / "Aplicativo" / "UrnaEscolar.exe", "Aplicativo/UrnaEscolar.exe"),
        ]
        for path, label in deployed:
            if path.exists() and path.is_file():
                entries.append({"path": label, "sha256": _sha256_file(path)})

        # Recursos web ficam como arquivos na distribuição onedir.
        allowed_suffixes = {".html", ".js", ".css"}
        static_roots = [BASE_DIR / "app" / "templates", BASE_DIR / "app" / "static"]
        for root in static_roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
                    continue
                if "sounds" in path.parts:
                    continue
                entries.append({"path": path.relative_to(BASE_DIR).as_posix(), "sha256": _sha256_file(path)})
    else:
        roots = [BASE_DIR / "app", BASE_DIR / "print_agent", BASE_DIR / "scripts"]
        allowed_suffixes = {".py", ".html", ".js", ".css"}
        excluded_parts = {"__pycache__", "sounds"}
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
                    continue
                rel = path.relative_to(BASE_DIR)
                if any(part in excluded_parts for part in rel.parts):
                    continue
                entries.append({"path": rel.as_posix(), "sha256": _sha256_file(path)})
        for name in ("requirements.txt", "pyproject.toml"):
            path = BASE_DIR / name
            if path.exists():
                entries.append({"path": name, "sha256": _sha256_file(path)})

    entries.sort(key=lambda x: x["path"])
    root_hash = sha256_text(canonical_json({"files": entries}))
    return {"root_hash": root_hash, "files": entries}


def current_software_hash() -> str:
    return software_manifest()["root_hash"]


def public_key_fingerprint(path: Path | None = None) -> str | None:
    path = path or PUBLIC_KEY_PATH
    if not path.exists():
        return None
    key = serialization.load_pem_public_key(path.read_bytes())
    der = key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()


def audit_head(db: Session) -> str:
    last = db.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)).scalar_one_or_none()
    return last.entry_hash if last else GENESIS


def ballot_head(db: Session) -> str:
    setting = db.get(Setting, "ballot_head_hash")
    return setting.value if setting else GENESIS


def verify_audit_chain(db: Session) -> tuple[bool, str]:
    current = GENESIS
    events = db.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars().all()
    for event in events:
        if event.previous_hash != current:
            return False, current
        try:
            details = json.loads(event.details_json or "{}")
        except Exception:
            return False, current
        payload = {
            "event_type": event.event_type,
            "actor": event.actor,
            "details": details,
            "previous_hash": event.previous_hash,
            "created_at": event.created_at.isoformat(timespec="microseconds"),
        }
        expected = sha256_text(canonical_json(payload))
        if expected != event.entry_hash:
            return False, current
        current = event.entry_hash
    return True, current


def security_status(db: Session) -> dict:
    election = db.execute(select(Election).limit(1)).scalar_one_or_none()
    current_sw = current_software_hash()
    current_key = public_key_fingerprint()
    audit_ok, current_audit_head = verify_audit_chain(db)
    return {
        "software_current": current_sw,
        "software_sealed": election.software_hash if election else None,
        "software_ok": (not election or not election.software_hash or election.software_hash == current_sw),
        "public_key_current": current_key,
        "public_key_sealed": election.public_key_fingerprint if election else None,
        "public_key_ok": (not election or not election.public_key_fingerprint or election.public_key_fingerprint == current_key),
        "config_sealed": election.config_hash if election else None,
        "audit_ok": audit_ok,
        "audit_head": current_audit_head,
        "ballot_head": ballot_head(db),
    }
