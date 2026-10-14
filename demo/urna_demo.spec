from pathlib import Path
root=Path(SPECPATH).parent
source=root/'URNA_ESCOLAR_SOURCE'
a=Analysis([str(root/'demo/urna_demo.py')],pathex=[str(source/'03_URNA'),str(source/'01_SERVIDOR_ADMIN')],
    datas=[(str(source/'01_SERVIDOR_ADMIN/app/static/sounds/final.mp3'),'.')],
    hiddenimports=['win32print','win32ui','win32con','pywintypes','pythoncom','PIL.ImageTk'],
    excludes=['pytest'],binaries=[])
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='UrnaEscolar_Teste',console=False,upx=False)
