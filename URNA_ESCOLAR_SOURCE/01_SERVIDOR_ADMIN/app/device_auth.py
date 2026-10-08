from __future__ import annotations

from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Urn, UrnDeviceSession
from .security import random_token, sha256_text, verify_device_secret

URN_SESSION_HOURS = 12


def urn_cookie_name(urn_code: str) -> str:
    safe = ''.join(ch.lower() for ch in urn_code if ch.isalnum() or ch in ('-', '_'))
    return f"urn_session_{safe}"


def authenticate_device_secret(db: Session, urn_code: str, secret: str) -> Urn:
    urn = db.execute(select(Urn).where(Urn.code == urn_code.upper())).scalar_one_or_none()
    if not urn:
        raise HTTPException(404, "Urna não configurada")
    ok, upgraded = verify_device_secret(urn.device_secret_hash, secret or "")
    if not ok:
        raise HTTPException(401, "Senha da urna inválida")
    if upgraded:
        urn.device_secret_hash = upgraded
    return urn


def create_urn_session(db: Session, urn: Urn) -> str:
    now = datetime.utcnow()
    db.execute(delete(UrnDeviceSession).where(UrnDeviceSession.expires_at < now))
    # Mantém no máximo algumas sessões válidas por urna, útil em testes e troca de navegador.
    token = random_token(32)
    db.add(UrnDeviceSession(
        id_hash=sha256_text(token),
        urn_id=urn.id,
        created_at=now,
        expires_at=now + timedelta(hours=URN_SESSION_HOURS),
        last_seen_at=now,
    ))
    return token


def set_urn_session_cookie(response: Response, request: Request, urn_code: str, token: str) -> None:
    response.set_cookie(
        urn_cookie_name(urn_code), token,
        max_age=URN_SESSION_HOURS * 3600,
        httponly=True,
        secure=(request.url.scheme == "https"),
        samesite="strict",
        path="/",
    )


def clear_urn_session_cookie(response: Response, urn_code: str) -> None:
    response.delete_cookie(urn_cookie_name(urn_code), path="/")


def authenticate_urn_request(db: Session, urn_code: str, request: Request, legacy_secret: str | None = None) -> Urn:
    urn = db.execute(select(Urn).where(Urn.code == urn_code.upper())).scalar_one_or_none()
    if not urn:
        raise HTTPException(404, "Urna não configurada")

    # A v1.5 deliberadamente não aceita mais a senha da urna em headers.
    # A senha só é usada no login inicial; depois, utiliza-se um token aleatório
    # de sessão em cookie HttpOnly, cujo hash é o único valor persistido no banco.
    raw = request.cookies.get(urn_cookie_name(urn_code))
    if not raw:
        raise HTTPException(401, "Urna não autenticada")
    session = db.get(UrnDeviceSession, sha256_text(raw))
    now = datetime.utcnow()
    if not session or session.urn_id != urn.id or session.expires_at < now:
        raise HTTPException(401, "Sessão da urna inválida ou expirada")
    session.last_seen_at = now
    urn.last_seen_at = now
    return urn
