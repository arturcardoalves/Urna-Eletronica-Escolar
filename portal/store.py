"""Transactional, append-only public document archive."""
import hmac
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
from publication_core.protocol import verify_package, digest, canonical, InvalidPackage


class Archive:
    def __init__(self, path, trust):
        self.path = path
        self.trust = trust
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, election TEXT NOT NULL, kind TEXT NOT NULL,
                    urn TEXT NOT NULL, revision INTEGER NOT NULL, digest TEXT NOT NULL,
                    hash TEXT NOT NULL, document TEXT NOT NULL, package BLOB NOT NULL,
                    receipt TEXT NOT NULL, received TEXT NOT NULL,
                    UNIQUE(election, kind, urn, revision));
                CREATE INDEX IF NOT EXISTS election_docs ON documents(election);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def authorize(self, token):
        token_hash = digest(token.encode())
        return {eid: entry for eid, entry in self.trust.items()
                if hmac.compare_digest(entry['token_sha256'], token_hash)}

    def accept(self, raw, authorized):
        p = verify_package(raw)
        doc = p['document']
        eid = doc['election']['id']
        entry = authorized.get(eid)
        if not entry or not hmac.compare_digest(entry['fingerprint'], p['fingerprint']):
            raise InvalidPackage('Eleição ou chave não autorizada pelo administrador do portal')
        if doc['election']['public_url'] != entry['public_url']:
            raise InvalidPackage('O endereço assinado não corresponde ao portal cadastrado')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM documents WHERE id=?', (doc['id'],)).fetchone()
            if old:
                if old['hash'] != p['package_hash']:
                    raise InvalidPackage('ID já recebido com conteúdo diferente')
                return json.loads(old['receipt'])
            previous = db.execute('SELECT * FROM documents WHERE election=? AND kind=? AND urn=? ORDER BY revision DESC LIMIT 1',
                                  (eid, doc['kind'], doc['urn_id'] or '')).fetchone()
            if previous:
                if doc['revision'] != previous['revision'] + 1 or doc['previous'] != previous['digest']:
                    raise InvalidPackage('Revisão fora de sequência')
                before = json.loads(previous['document'])
                # Retification is an explanatory signed note, never replacement of sealed votes.
                if any(before[k] != doc[k] for k in ('election', 'totals', 'configuration_digest', 'evidence')):
                    raise InvalidPackage('Retificação não pode modificar valores lacrados')
            elif doc['revision'] != 1:
                raise InvalidPackage('Envie primeiro as versões anteriores')
            if doc['kind'] != 'configuration':
                config = db.execute('SELECT document FROM documents WHERE election=? AND kind=? AND digest=?',
                                    (eid, 'configuration', doc['configuration_digest'])).fetchone()
                if not config or json.loads(config['document'])['election'] != doc['election']:
                    raise InvalidPackage('Envie a configuração correspondente antes deste documento')
            if doc['kind'] == 'result':
                zero = db.execute('SELECT document FROM documents WHERE election=? AND urn=? AND kind=? ORDER BY revision DESC LIMIT 1',
                                  (eid, doc['urn_id'], 'zero')).fetchone()
                if not zero:
                    raise InvalidPackage('Envie a Zerésima desta urna antes do boletim')
                if json.loads(zero['document'])['evidence']['zero_snapshot_hash'] != doc['evidence']['zero_snapshot_hash']:
                    raise InvalidPackage('Boletim não corresponde à Zerésima recebida')
                if datetime.fromisoformat(doc['evidence']['closed_at']) < datetime.fromisoformat(json.loads(zero['document'])['evidence']['zero_issued_at']):
                    raise InvalidPackage('Boletim anterior à Zerésima')
                others = db.execute('SELECT document FROM documents WHERE election=? AND kind=? AND urn!=? AND revision=(SELECT MAX(d2.revision) FROM documents d2 WHERE d2.election=documents.election AND d2.kind=documents.kind AND d2.urn=documents.urn)',
                                    (eid, 'result', doc['urn_id'])).fetchall()
                if doc['election']['identified']:
                    if any(json.loads(r['document'])['totals']['registered'] != doc['totals']['registered'] for r in others):
                        raise InvalidPackage('Boletins divergem sobre o cadastro final')
                    if doc['totals']['total'] + sum(json.loads(r['document'])['totals']['total'] for r in others) > doc['totals']['registered']:
                        raise InvalidPackage('Totalização excede eleitores cadastrados')
            received = datetime.now(timezone.utc).isoformat()
            receipt = {'protocol': str(uuid4()), 'received_at': received, 'document_id': doc['id'],
                       'election_id': eid, 'sha256': p['package_hash']}
            db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       (doc['id'], eid, doc['kind'], doc['urn_id'] or '', doc['revision'], p['digest'],
                        p['package_hash'], canonical(doc).decode(), raw, json.dumps(receipt), received))
            return receipt

    def rows(self, election=None):
        with self.connect() as db:
            if election:
                return db.execute('SELECT id,document,receipt,received FROM documents WHERE election=? ORDER BY received', (election,)).fetchall()
            return db.execute("SELECT id,document,receipt,received FROM documents WHERE kind='configuration' AND revision=1 ORDER BY received DESC").fetchall()

    def get(self, docid):
        with self.connect() as db:
            return db.execute('SELECT * FROM documents WHERE id=?', (docid,)).fetchone()

    def summary(self, eid):
        rows = self.rows(eid)
        if not rows:
            return None
        docs = [json.loads(r['document']) for r in rows]
        config = next(d for d in reversed(docs) if d['kind'] == 'configuration')
        latest = {(d['kind'], d['urn_id']): d for d in docs}
        election = config['election']
        results = [latest[('result', u['id'])] for u in election['urns'] if ('result', u['id']) in latest]
        totals = {'total': 0, 'blank': 0, 'null': 0, 'slates': {s['number']: 0 for s in election['slates']}}
        for result in results:
            for field in ('total', 'blank', 'null'):
                totals[field] += result['totals'][field]
            for s in result['totals']['slates']:
                totals['slates'][s['number']] += s['votes']
        return {'election': election, 'configuration': config, 'latest': latest, 'totals': totals,
                'registered': results[0]['totals']['registered'] if results else election['registered'],
                'status': 'Definitivo' if len(results) == len(election['urns']) else 'Parcial' if results else 'Aguardando resultados',
                'received_count': len(results), 'history': [{**dict(r), 'receipt': json.loads(r['receipt']), 'doc': json.loads(r['document'])} for r in rows]}
