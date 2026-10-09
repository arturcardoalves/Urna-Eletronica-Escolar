"""Create a source delivery using an allowlist, never copying live data.

Run from any directory: python installer/package_source.py --output <new.zip>.
The zip is read back and every file is checked against its SHA-256 manifest.
No data or original file is deleted. Existing packages are never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOP_FILES = {'.gitignore', 'README.md', 'SEGURANCA.md',
             'RESETAR_PC_CENTRAL_MESA.bat', 'RESETAR_PC_URNA.bat'}
TREES = {'.github', 'installer', 'tests', 'docs', 'URNA_ESCOLAR_SOURCE'}
EXTENSIONS = {'.py', '.js', '.css', '.html', '.md', '.txt', '.toml', '.ps1',
              '.spec', '.iss', '.yml', '.yaml', '.svg', '.mp3', '.json'}
SKIP_DIRS = {'__pycache__', '.pytest_cache', 'output', 'build', 'dist',
             'test-results', '.build-venv', 'node_modules'}
PRIVATE_KEY = re.compile(rb'-----BEGIN (?:RSA |EC |ENCRYPTED |OPENSSH )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=]{20}')


def source_files(root: Path):
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if any(part in SKIP_DIRS or part == '.git' for part in relative.parts):
            continue
        if not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'Arquivo externo ou link: {relative}')
        if len(relative.parts) == 1:
            if path.name not in TOP_FILES:
                continue
        elif relative.parts[0] not in TREES:
            continue
        # Even a tracked database, photo, key or archive must never be shipped.
        if 'data' in relative.parts or 'uploads' in relative.parts:
            if path.name != '.gitkeep':
                continue
        elif path.suffix.lower() not in EXTENSIONS:
            continue
        if path.name in {'build-log.txt'}:
            continue
        content = path.read_bytes()
        if content.startswith(b'SQLite format 3\0') or PRIVATE_KEY.search(content):
            raise ValueError(f'Dados privados encontrados: {relative}')
        yield relative.as_posix(), content


def create_package(root: Path, output: Path):
    files = dict(source_files(root))
    if 'README.md' not in files or 'installer/BUILD_WINDOWS.ps1' not in files:
        raise ValueError('Fonte incompleta; pacote nao criado.')
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        archive.writestr('MANIFEST_SHA256.json', json.dumps(manifest, indent=2) + '\n')
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(files) | {'MANIFEST_SHA256.json'}
        for name, expected in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256.txt').write_text(
        f'{checksum}  {output.name}\n', encoding='ascii')
    print(f'Pacote verificado: {len(files)} arquivos; SHA-256 {checksum}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    create_package(ROOT, args.output.resolve())
