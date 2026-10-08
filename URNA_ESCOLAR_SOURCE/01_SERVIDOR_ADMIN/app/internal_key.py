from __future__ import annotations
import base64
import os
import secrets
from pathlib import Path

from .config import PRIVATE_KEY_PASSWORD_PATH, PRIVATE_KEY_PATH, PUBLIC_KEY_PATH
from .security import generate_keypair


def _restrict(path: Path) -> None:
    """Best effort: owner-only on POSIX. Windows ACL remains inherited from data/."""
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def ensure_internal_keypair() -> None:
    """Create the election keypair inside the server when it does not exist.

    The private key stays encrypted at rest. Its randomly generated password is
    stored locally beside it because this project explicitly favors a completely
    local/offline workflow with no external key media. This protects against
    accidental disclosure but does not protect against an attacker who already
    has full administrative access to the server computer.
    """
    if PUBLIC_KEY_PATH.exists() and PRIVATE_KEY_PATH.exists() and PRIVATE_KEY_PASSWORD_PATH.exists():
        return
    PUBLIC_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    password = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('ascii').rstrip('=')
    generate_keypair(PUBLIC_KEY_PATH, PRIVATE_KEY_PATH, password)
    PRIVATE_KEY_PASSWORD_PATH.write_text(password, encoding='utf-8')
    _restrict(PRIVATE_KEY_PATH)
    _restrict(PRIVATE_KEY_PASSWORD_PATH)


def load_internal_private_key() -> tuple[bytes, str]:
    if not (PRIVATE_KEY_PATH.exists() and PRIVATE_KEY_PASSWORD_PATH.exists()):
        raise FileNotFoundError('A chave privada interna da eleição não foi encontrada.')
    return PRIVATE_KEY_PATH.read_bytes(), PRIVATE_KEY_PASSWORD_PATH.read_text(encoding='utf-8').strip()
