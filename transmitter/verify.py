"""Verify independently: python -m transmitter.verify package.uepkg --fingerprint SHA256"""
import argparse
import json
from pathlib import Path
from .client import verify_package
from publication_core.protocol import verify_qr


def main():
    parser = argparse.ArgumentParser(description='Verificação offline de documento da Urna Escolar')
    parser.add_argument('package', type=Path)
    parser.add_argument('--fingerprint', required=True, help='SHA-256 da chave obtido da comissão por meio confiável')
    parser.add_argument('--election', help='UUID esperado da eleição')
    parser.add_argument('--qr', help='Texto ou URL do QR de verificação')
    args = parser.parse_args()
    raw = args.package.read_bytes()
    try:
        result = verify_package(raw, args.fingerprint.lower(), args.election)
        if args.qr:
            verify_qr(args.qr, args.fingerprint.lower(), raw)
    except ValueError as exc:
        parser.exit(1, 'NÃO VERIFICADO: ' + str(exc) + '\n')
    print('Assinatura e arquivos conferidos. Chave corresponde à referência informada.')
    print('Compare os dados abaixo com o documento impresso:')
    print(json.dumps(result['document'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
