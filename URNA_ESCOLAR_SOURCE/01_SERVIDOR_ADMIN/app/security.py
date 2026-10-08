import base64
import hashlib
import hmac
import json
import secrets
from pathlib import Path
from argon2 import PasswordHasher
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

# Parâmetros seguros e razoáveis para um computador escolar atual. A biblioteca
# mantém os parâmetros junto do próprio hash, permitindo rehash futuro.
ph = PasswordHasher()


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except Exception:
        return False


def password_is_acceptable(password: str) -> bool:
    # Evita senhas excessivamente curtas sem impor regras artificiais de
    # maiúsculas/símbolos. Frases-senha também são aceitas.
    return len(password or "") >= 10


def hash_device_secret(secret: str) -> str:
    return ph.hash(secret)


def verify_device_secret(stored_hash: str, secret: str) -> tuple[bool, str | None]:
    """Verifica segredo da urna e migra hashes SHA-256 antigos para Argon2id.

    Retorna (ok, upgraded_hash). upgraded_hash é preenchido apenas quando um
    cadastro antigo é autenticado com sucesso.
    """
    if not stored_hash or not secret:
        return False, None
    if stored_hash.startswith("$argon2"):
        try:
            ok = ph.verify(stored_hash, secret)
            upgraded = ph.hash(secret) if ok and ph.check_needs_rehash(stored_hash) else None
            return bool(ok), upgraded
        except Exception:
            return False, None
    # Compatibilidade com urnas cadastradas nas versões <= 1.1.
    legacy = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    if hmac.compare_digest(legacy, stored_hash):
        return True, ph.hash(secret)
    return False, None


def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def encrypt_ballot(public_key_pem: bytes, payload: dict) -> str:
    public_key = serialization.load_pem_public_key(public_key_pem)
    plaintext = canonical_json(payload).encode("utf-8")
    ciphertext = public_key.encrypt(
        plaintext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return base64.b64encode(ciphertext).decode("ascii")


def decrypt_ballot(private_key_pem: bytes, password: str, ciphertext_b64: str) -> dict:
    private_key = serialization.load_pem_private_key(
        private_key_pem,
        password=password.encode("utf-8") if password else None,
    )
    ciphertext = base64.b64decode(ciphertext_b64)
    plaintext = private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return json.loads(plaintext.decode("utf-8"))



def generate_keypair(public_path: Path, private_path: Path, password: str) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    enc = serialization.BestAvailableEncryption(password.encode("utf-8"))
    private_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=enc,
        )
    )
