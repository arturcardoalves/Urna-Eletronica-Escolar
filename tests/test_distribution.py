import json
from pathlib import Path
import zipfile

import pytest
from package_source import create_package, source_files


def test_package_excludes_election_data_even_when_extension_looks_like_source(tmp_path):
    fixtures = {
        'README.md': 'Source', 'installer/BUILD_WINDOWS.ps1': '# build',
        'tests/test_demo.py': '# isolated fixture',
        'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/data/.gitkeep': '',
        'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/data/history/private.json': 'personal',
        'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/data/private.db-wal': 'personal',
        'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/static/uploads/slates/photo.svg': 'personal',
        'installer/output/log.txt': 'runtime', '.build-venv/secret.py': 'runtime',
        'tests/__pycache__/test.py': 'cache', 'old.zip': 'old',
    }
    for name, content in fixtures.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    package = tmp_path / 'release.zip'
    create_package(tmp_path, package)
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read('MANIFEST_SHA256.json'))
    assert set(manifest) == {'README.md', 'installer/BUILD_WINDOWS.ps1',
                             'tests/test_demo.py', 'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/data/.gitkeep'}
    assert (tmp_path / 'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/data/history/private.json').exists()
    with pytest.raises(FileExistsError):
        create_package(tmp_path, package)


def test_package_rejects_embedded_private_key(tmp_path):
    path = tmp_path / 'docs' / 'accidental.txt'
    path.parent.mkdir()
    path.write_text('-----BEGIN PRIVATE KEY-----\n' + 'A' * 40)
    with pytest.raises(ValueError, match='privados'):
        list(source_files(tmp_path))
