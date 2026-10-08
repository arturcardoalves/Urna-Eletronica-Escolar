import os
from pathlib import Path
root=Path(os.environ['URNA_BUILD_ROOT']).resolve()
a=Analysis([str(root/'installer/upgrade_guard.py')],pathex=[str(root/'installer')])
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,name='VerificarAtualizacao',console=False,upx=False)
