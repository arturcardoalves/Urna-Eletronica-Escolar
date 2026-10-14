"""Collect web resources without bundling legacy election uploads or runtime data."""
from pathlib import Path

STATIC_EXTENSIONS={'.js','.css','.svg','.mp3','.wav','.png','.jpg','.jpeg','.gif','.webp',
                   '.ttf','.otf','.woff','.woff2','.ico','.txt'}

def web_assets(app_directory):
    app_directory=Path(app_directory).resolve()
    result=[]
    for folder,extensions in [('templates',{'.html','.txt'}),('static',STATIC_EXTENSIONS)]:
        base=app_directory/folder
        for path in sorted(base.rglob('*')):
            relative=path.relative_to(base)
            if any(part in {'uploads','__pycache__'} for part in relative.parts):continue
            if not path.is_file() or path.suffix.lower() not in extensions:continue
            if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
                raise ValueError('Recurso web fora da pasta permitida: '+relative.as_posix())
            destination=(Path('app')/folder/relative.parent).as_posix()
            result.append((str(path),destination))
    return result
