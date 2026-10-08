"""Executed by the installer BEFORE replacing any application file."""
import json
from contextlib import closing
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def check_and_backup(home):
    data=home/"Servidor"
    path=data/"urna_escolar.db"
    if not path.exists():return
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True)) as db:
        table=db.execute("SELECT name FROM sqlite_master WHERE name='elections'").fetchone()
        if table:
            row=db.execute("SELECT state FROM elections LIMIT 1").fetchone()
            if row and row[0] in ("SEALED","OPEN"):
                raise RuntimeError("Existe uma eleição lacrada ou aberta. Termine e arquive essa eleição na versão atual antes de atualizar. Nenhum arquivo foi substituído.")
        target=home/"Backups"/datetime.now().strftime("antes-2.3.0-%Y%m%d-%H%M%S-%f")
        target.mkdir(parents=True,exist_ok=False)
        shutil.copytree(data,target/"Servidor",ignore=shutil.ignore_patterns("*.db","*.db-wal","*.db-shm"))
        with closing(sqlite3.connect(target/"Servidor/urna_escolar.db")) as copy:
            db.backup(copy)


if __name__=="__main__":
    result=Path(sys.argv[1])
    try:
        check_and_backup(Path(os.environ["PROGRAMDATA"])/"UrnaEscolar")
        result.write_text("OK",encoding="utf-8")
    except Exception as exc:
        result.write_text(str(exc),encoding="utf-8")
        sys.exit(1)
