# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(os.environ['URNA_BUILD_ROOT']).resolve()
srv = root / 'URNA_ESCOLAR_SOURCE' / '01_SERVIDOR_ADMIN'
if not (srv / 'app' / 'main.py').exists():
    raise RuntimeError(f'Fonte do servidor nao encontrada em {srv}')

sys.path.insert(0,str(root/'installer'))
from build_assets import web_assets
datas = web_assets(srv/'app')
binaries = []
hiddenimports = ['app.main', 'scripts.generate_tls', 'win32crypt']

for pkg in ['uvicorn','fastapi','starlette','sqlalchemy','cryptography','argon2','reportlab','openpyxl','jinja2','multipart','PIL']:
    # Missing required packages must stop the build, not create an incomplete EXE.
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(root / 'installer' / 'server_launcher.py')],
    pathex=[str(srv), str(root), str(root / "installer")],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='UrnaEscolarServidor', console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='UrnaEscolarServidor')
