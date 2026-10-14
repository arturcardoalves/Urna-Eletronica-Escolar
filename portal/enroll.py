"""Local portal operator enrollment. No HTTP enrollment or universal credential."""
import argparse
import getpass
import json
import os
import secrets
import sys
from pathlib import Path
from uuid import UUID
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN'))
from publication_core.protocol import digest
from publication_core.schema import Election


def main():
    parser = argparse.ArgumentParser(description='Cadastrar chave confiável e credencial de transmissão no servidor do portal')
    parser.add_argument('--file', type=Path, required=True, help='Arquivo fora do repositório, protegido pelo administrador do servidor')
    parser.add_argument('--election', required=True)
    parser.add_argument('--fingerprint', required=True)
    parser.add_argument('--url', required=True)
    args = parser.parse_args()
    UUID(args.election)
    if len(args.fingerprint) != 64 or any(c not in '0123456789abcdef' for c in args.fingerprint):
        parser.error('Impressão digital deve ser SHA-256 em hexadecimal minúsculo')
    url = Election.url(args.url)
    entries = json.loads(args.file.read_text('utf-8')) if args.file.exists() else {}
    if args.election in entries:
        parser.error('Eleição já cadastrada. Para revogar ou trocar a credencial, edite o cadastro protegido e reinicie o portal; não substitua a chave de uma eleição lacrada.')
    token = secrets.token_urlsafe(32)
    entries[args.election] = {'fingerprint': args.fingerprint, 'public_url': url, 'token_sha256': digest(token.encode())}
    args.file.parent.mkdir(parents=True, exist_ok=True)
    # File contains hashes, but its integrity determines trusted keys; restrict access.
    temp = args.file.with_suffix('.new')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(entries, f, indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(temp, args.file)
    finally:
        temp.unlink(missing_ok=True)
    print('Cadastro salvo. Reinicie o portal para carregar as referências.')
    print('Credencial exibida apenas nesta criação; entregue ao operador por canal reservado:')
    print(token)


if __name__ == '__main__':
    main()
