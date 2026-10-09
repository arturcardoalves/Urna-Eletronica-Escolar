"""Executed by the installer BEFORE replacing any application file."""
from contextlib import closing
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def _reject_links(root):
    """Never copy a junction/symlink outside the election data tree."""
    for directory, subdirs, files in os.walk(root, followlinks=False):
        for path in [Path(directory), *(Path(directory) / name for name in subdirs + files)]:
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise RuntimeError("Backup interrompido: a pasta de dados contém um link ou junção. Peça revisão ao responsável antes de atualizar.")


def _is_sqlite(path):
    with path.open("rb") as stream:
        return stream.read(16) == b"SQLite format 3\x00"


def check_and_backup(home):
    data=home/"Servidor"
    path=data/"urna_escolar.db"
    if not data.exists():
        return
    _reject_links(home)
    # Preserve keys/archives even if setup was interrupted before creating a DB.
    if not path.exists():
        target=home/"Backups"/datetime.now().strftime("antes-2.3.0-%Y%m%d-%H%M%S-%f")
        shutil.copytree(data, target/"Servidor")
        return
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True)) as db:
        table=db.execute("SELECT name FROM sqlite_master WHERE name='elections'").fetchone()
        if table:
            row=db.execute("SELECT state FROM elections LIMIT 1").fetchone()
            if row and row[0] in ("SEALED","OPEN"):
                raise RuntimeError("Existe uma eleição lacrada ou aberta. Termine e arquive essa eleição na versão atual antes de atualizar. Nenhum arquivo foi substituído.")
        target=home/"Backups"/datetime.now().strftime("antes-2.3.0-%Y%m%d-%H%M%S-%f")
        target.mkdir(parents=True,exist_ok=False)
        # Copy every auxiliary/archive file. Each SQLite DB is copied through
        # SQLite's backup API, including committed pages still in its WAL.
        for directory, _, files in os.walk(data):
            destination=target/"Servidor"/Path(directory).relative_to(data)
            destination.mkdir(parents=True, exist_ok=True)
            for filename in files:
                source=Path(directory)/filename
                if filename.endswith(("-wal", "-shm", "-journal")):
                    base=source.with_name(filename.rsplit("-", 1)[0])
                    if base.is_file() and _is_sqlite(base):
                        continue
                if _is_sqlite(source):
                    with closing(sqlite3.connect(source.resolve().as_uri()+"?mode=ro", uri=True)) as original:
                        with closing(sqlite3.connect(destination/filename)) as copy:
                            original.backup(copy)
                            if copy.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                                raise RuntimeError("O banco copiado não passou na verificação de integridade. Atualização cancelada.")
                else:
                    shutil.copy2(source, destination/filename)


if __name__=="__main__":
    result=Path(sys.argv[1])
    try:
        import psutil
        if any(p.info['name'] and p.info['name'].lower() in ('urnaescolar.exe', 'urnaescolarservidor.exe') for p in psutil.process_iter(['name'])):
            raise RuntimeError("Feche a Central e a Urna antes de atualizar para que o backup seja feito sem alterações em andamento.")
        check_and_backup(Path(os.environ["PROGRAMDATA"])/"UrnaEscolar")
        result.write_text("OK",encoding="utf-8")
    except Exception as exc:
        result.write_text(str(exc),encoding="utf-8")
        sys.exit(1)
