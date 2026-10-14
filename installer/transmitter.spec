# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all
root = Path(os.environ['URNA_BUILD_ROOT']).resolve()
datas = []; binaries = []; hidden = []
for package in ['cryptography', 'PIL', 'pydantic']:
    d, b, h = collect_all(package)
    datas += d; binaries += b; hidden += h
a = Analysis([str(root/'transmitter/app.py')], pathex=[str(root), str(root/'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN')], datas=datas, binaries=binaries, hiddenimports=hidden+['tkinter'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='TransmissorEleitoral', console=False, upx=False)
