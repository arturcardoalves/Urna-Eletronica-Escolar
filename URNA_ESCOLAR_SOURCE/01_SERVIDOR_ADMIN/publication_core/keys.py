"""Private signing keys never leave the Central. Windows: current-user DPAPI."""
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

def signing_key(directory,election_id):
    from uuid import UUID
    if str(UUID(election_id))!=election_id:raise ValueError('Eleição inválida')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    path=directory/(election_id+'.key')
    if os.name=='nt':
        import win32crypt
        if path.exists():raw=win32crypt.CryptUnprotectData(path.read_bytes(),None,None,None,0)[1]
        else:
            key=Ed25519PrivateKey.generate();raw=key.private_bytes_raw()
            protected=win32crypt.CryptProtectData(raw,'Urna Escolar - assinatura publica',None,None,None,0)
            with path.open('xb') as f:f.write(protected);f.flush();os.fsync(f.fileno())
        return Ed25519PrivateKey.from_private_bytes(raw)
    password=os.environ.get('URNA_PUBLICATION_KEY_PASSWORD','').encode()
    if len(password)<16:raise ValueError('Configure URNA_PUBLICATION_KEY_PASSWORD (mínimo 16 caracteres) fora do Windows.')
    if path.exists():return serialization.load_pem_private_key(path.read_bytes(),password)
    key=Ed25519PrivateKey.generate()
    raw=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.BestAvailableEncryption(password))
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return key
