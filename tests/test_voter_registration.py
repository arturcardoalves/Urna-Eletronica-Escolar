"""Isolated database tests; run directly or through pytest."""
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    runtime = ROOT / 'test-results' / 'registration'
    runtime.mkdir(parents=True, exist_ok=True)
    os.environ['URNA_DATA_DIR'] = str(runtime)
    os.environ['URNA_DB_PATH'] = str(runtime / 'unused.db')
    sys.path.insert(0, str(ROOT / 'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN'))
    sys.path.insert(0, str(ROOT / 'URNA_ESCOLAR_SOURCE/03_URNA'))
    sys.path.insert(0, str(ROOT / 'installer'))

from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from openpyxl import Workbook
from app.models import Base, Voter
from app.main import add_voter, import_voters
from app.services import get_election


def immediate(coroutine):
    # In-memory UploadFile.read completes synchronously, without a network loop.
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError('Unexpected external async operation')


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = SimpleNamespace(username='teste')

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add(self, name='Ana Silva', turma='101', enrollment='', shift=''):
        return add_voter(name=name, class_code=turma, enrollment=enrollment,
                         shift=shift, user=self.user, db=self.db)

    def upload(self, data, filename='alunos.csv'):
        with tempfile.SpooledTemporaryFile(max_size=1024 * 1024) as stream:
            stream.write(data)
            stream.seek(0)
            return immediate(import_voters(UploadFile(filename=filename, file=stream), self.user, self.db))

    def test_name_and_class_only(self):
        self.assertEqual(self.add().status_code, 303)
        voter = self.db.scalar(select(Voter))
        self.assertTrue(voter.enrollment.startswith('AUTO-'))
        self.assertEqual(len(voter.enrollment), 32)
        self.assertEqual(voter.shift, 'Não informado')
        self.assertEqual(voter.status, 'NOT_VOTED')

    def test_duplicate_and_homonyms(self):
        self.add()
        with self.assertRaises(HTTPException) as error:
            self.add(' ANA  SILVA ')
        self.assertEqual(error.exception.status_code, 409)
        self.add(enrollment='ALUNO-2')
        self.add(turma='102')
        self.assertEqual(len(self.db.scalars(select(Voter)).all()), 3)

    def test_existing_fields_preserved(self):
        self.add(enrollment='0012', shift='Manhã')
        voter = self.db.scalar(select(Voter))
        self.assertEqual((voter.enrollment, voter.shift), ('0012', 'Manhã'))

    def test_required_fields_and_seal(self):
        for name, turma in [('', '101'), ('Ana', '')]:
            with self.assertRaises(HTTPException) as error:
                self.add(name, turma)
            self.assertEqual(error.exception.status_code, 400)
        get_election(self.db).state = 'SEALED'
        self.db.commit()
        with self.assertRaises(HTTPException) as error:
            self.add()
        self.assertEqual(error.exception.status_code, 409)

    def test_csv_reimport_no_duplicates(self):
        data = b'Nome,Turma\nAna Silva,101\nBruno,101\nAna Silva,101\n'
        self.upload(data)
        self.upload(data)
        self.assertEqual(len(self.db.scalars(select(Voter)).all()), 2)

    def test_xlsx_only_name_uses_sheet_class(self):
        wb = Workbook()
        wb.active.title = 'Turma 101'
        wb.active.append(['Nome'])
        wb.active.append(['Ana Silva'])
        output = io.BytesIO()
        wb.save(output)
        wb.close()
        self.upload(output.getvalue(), 'alunos.xlsx')
        voter = self.db.scalar(select(Voter))
        self.assertEqual((voter.name, voter.class_code), ('Ana Silva', 'Turma 101'))


if __name__ == '__main__':
    unittest.main()
