from datetime import datetime, timedelta
from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Session as LoginSession, User
from .security import random_token, sha256_text

SESSION_HOURS = 4


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_session(db: Session, user: User) -> str:
    # O navegador recebe o token aleatório. O banco guarda somente o hash,
    # reduzindo o impacto de uma eventual cópia do arquivo SQLite.
    now = datetime.utcnow()
    db.execute(delete(LoginSession).where(LoginSession.expires_at < now))
    token = random_token(32)
    session = LoginSession(
        id=sha256_text(token),
        user_id=user.id,
        expires_at=now + timedelta(hours=SESSION_HOURS),
    )
    db.add(session)
    return token


def current_user(session_id: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
    if not session_id:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    session = db.get(LoginSession, sha256_text(session_id))
    if not session or session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Sessão inválida")
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="Usuário inválido")
    return user


def require_role(role: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role != role:
            raise HTTPException(status_code=403, detail="Sem permissão")
        return user
    return dep
