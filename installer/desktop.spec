# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all
root=Path(os.environ['URNA_BUILD_ROOT']).resolve()
srv=root/'URNA_ESCOLAR_SOURCE'/'01_SERVIDOR_ADMIN'
urn=root/'URNA_ESCOLAR_SOURCE'/'03_URNA'
datas=[];binaries=[];hidden=[]
for package in ['PIL','cryptography','fastapi','psutil']:
    d,b,h=collect_all(package);datas+=d;binaries+=b;hidden+=h
hidden+=['tkinter','win32print','win32ui','win32con','win32crypt','pythoncom','pywintypes','print_agent.agent']
# print_agent is a namespace package without __init__.py; its parent must be
# explicit or the frozen desktop self-test cannot import the printer backend.
a=Analysis([str(root/'installer/desktop_app.py')],pathex=[str(root/'installer'),str(srv),str(urn)],datas=datas,binaries=binaries,hiddenimports=hidden)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='UrnaEscolar',console=False,upx=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='UrnaEscolar')
