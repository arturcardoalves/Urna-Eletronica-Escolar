"""Only removable drives are export targets. Never execute files from media."""
import ctypes,os,string,tempfile
from pathlib import Path
from .protocol import digest,verify_package,MAX_PACKAGE

def removable_drives():
    if os.name!='nt':return []
    return [Path(letter+':/') for letter in string.ascii_uppercase if ctypes.windll.kernel32.GetDriveTypeW(letter+':\\')==2]

def export_package(raw,drive,allowed_drives=None):
    validated=verify_package(raw);root=Path(drive).resolve()
    allowed=removable_drives() if allowed_drives is None else allowed_drives
    if root not in [Path(d).resolve() for d in allowed]:raise ValueError('Selecione uma mídia removível detectada')
    folder=root/'UrnaEscolar_Publicacao'/validated['document']['election']['id']
    # Check existing parent links before mkdir; a hostile junction must not even
    # create an empty directory outside the removable media.
    if not folder.resolve().is_relative_to(root):raise ValueError('Destino USB inválido')
    folder.mkdir(parents=True,exist_ok=True)
    if not folder.resolve().is_relative_to(root):raise ValueError('Destino USB inválido')
    target=folder/(validated['document']['id']+'.uepkg')
    if target.is_symlink() or not target.resolve().is_relative_to(root):raise ValueError('Arquivo USB aponta para fora da mídia')
    if target.exists():
        if digest(target.read_bytes())!=digest(raw):raise ValueError('Arquivo de mesmo ID com conteúdo diferente na mídia')
        return target
    fd,name=tempfile.mkstemp(prefix='.export-',suffix='.tmp',dir=folder)
    try:
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if digest(Path(name).read_bytes())!=digest(raw):raise ValueError('Falha na conferência da mídia')
        # Atomic rename on Windows, without replacing an existing signed file.
        if target.exists():raise ValueError('Arquivo criado por outro processo; repita a conferência')
        os.rename(name,target)
    finally:
        Path(name).unlink(missing_ok=True)
    return target

def find_packages(drives=None):
    result=[]
    for drive in removable_drives() if drives is None else drives:
        root=Path(drive).resolve();base=root/'UrnaEscolar_Publicacao'
        if not base.exists() or not base.resolve().is_relative_to(root):continue
        for p in sorted(base.glob('*/*.uepkg')):
            if len(result)>=300:break
            if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root) and p.stat().st_size<=MAX_PACKAGE:result.append(p)
    return result
