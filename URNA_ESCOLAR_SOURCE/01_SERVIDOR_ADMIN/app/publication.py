"""Build only allowlisted public snapshots inside the election transaction."""
from datetime import datetime,timezone
from pathlib import Path
from uuid import UUID,uuid5,uuid4
import io,json
from PIL import Image,ImageOps
from sqlalchemy import select,func
from .config import DATA_DIR,BASE_DIR,APP_VERSION
from .models import PublicationConfig,PublicationDocument,Urn,Slate,Voter,DevicePrintCommand
from .audit import append_audit
from publication_core.keys import signing_key
from publication_core.protocol import canonical,digest,sign_package,verify_package
from publication_core.schema import Document, Election as PublicElection
from publication_core.documents import links,render_pdf
from publication_core.media import export_package

def config(db,election_id):return db.get(PublicationConfig,election_id)

def seal_binding(db,election_id):
    row=config(db,election_id)
    return {'public_url':row.public_url,'key_fingerprint':row.fingerprint} if row else None

def configure(db,election,url,actor):
    from .services import DomainError
    if election.state!='CONFIG':raise DomainError('Configure a publicação antes da lacração.')
    url=PublicElection.url(url.strip())
    key=signing_key(DATA_DIR/'publication_keys',election.election_uuid)
    fp=digest(key.public_key().public_bytes_raw())
    row=config(db,election.election_uuid)
    if row:row.public_url=url;row.fingerprint=fp
    else:db.add(PublicationConfig(election_id=election.election_uuid,public_url=url,fingerprint=fp))
    append_audit(db,'PUBLICATION_CONFIGURED',actor,{'fingerprint':fp,'url':url})
    db.flush()

def latest(db,eid,kind,urn_code=''):
    return db.scalar(select(PublicationDocument).where(PublicationDocument.election_id==eid,PublicationDocument.kind==kind,PublicationDocument.urn_code==urn_code).order_by(PublicationDocument.revision.desc()).limit(1))

def _public_snapshot(db,election,cfg):
    photos={};slates=[]
    for s in db.scalars(select(Slate).where(Slate.active==True).order_by(Slate.number)):
        photo=None
        if s.logo_path:
            rel=s.logo_path.lstrip('/')
            if rel.startswith('user-static/'):
                base=DATA_DIR/'user_static';path=base/rel[len('user-static/'):]
            elif rel.startswith('static/'):
                base=BASE_DIR/'app/static';path=base/rel[len('static/'):]
            else:raise ValueError('Caminho de foto inválido')
            if not path.resolve().is_relative_to(base.resolve()):raise ValueError('Foto fora da pasta permitida')
            with Image.open(path) as im:
                if im.width*im.height>20_000_000:raise ValueError('Foto muito grande')
                im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((800,800))
                # New raster discards EXIF, comments and other source metadata.
                clean=Image.new('RGB',im.size);clean.paste(im)
                out=io.BytesIO();clean.save(out,'PNG');photo=f'photo-{s.number}.png';photos[photo]=out.getvalue()
        slates.append({'number':s.number,'name':s.name,'photo':photo,'members':[{'role':m.role_name,'name':m.person_name} for m in sorted(s.members,key=lambda x:(x.display_order,x.id))]})
    urns=[{'id':str(uuid5(UUID(election.election_uuid),'urn:'+u.code)),'code':u.code,'name':u.name} for u in db.scalars(select(Urn).order_by(Urn.code))]
    public={'id':election.election_uuid,'name':election.name,'school':election.institution_name or '',
            'public_url':cfg.public_url,'identified':bool(election.voter_identification_enabled),
            'registered':int(db.scalar(select(func.count()).select_from(Voter))) if election.voter_identification_enabled else None,
            'allow_blank':bool(election.allow_blank),'sealed_at':election.sealed_at.replace(tzinfo=timezone.utc).isoformat(),
            'config_hash':election.config_hash,'slates':slates,'urns':urns}
    return public,photos

def prepare(db,kind,actor,correction='',urn_code=None):
    from .services import get_election,verify_sealed_integrity,DomainError
    from .tally_service import verify_final_tally_integrity
    election=get_election(db);cfg=config(db,election.election_uuid)
    if not cfg:return []
    if election.state=='CONFIG':raise DomainError('Lacre a eleição antes de emitir documentos públicos.')
    verify_sealed_integrity(db)
    key=signing_key(DATA_DIR/'publication_keys',election.election_uuid)
    if digest(key.public_key().public_bytes_raw())!=cfg.fingerprint:raise DomainError('A chave de publicação não corresponde à lacração.')
    if kind=='configuration':
        public,photos=_public_snapshot(db,election,cfg);base_digest=None;urn_list=[None]
    else:
        base=latest(db,election.election_uuid,'configuration')
        if not base:raise DomainError('Pacote de configuração ausente.')
        prior=verify_package(base.package,cfg.fingerprint,election.election_uuid)
        public=prior['document']['election'];photos={n:v for n,v in prior['assets'].items() if n!='document.pdf'}
        base_digest=base.digest;urn_list=public['urns']
    if kind=='zero':
        if not election.zero_snapshot_json:raise DomainError('A zerésima ainda não foi emitida.')
        if not all(latest(db,election.election_uuid,'zero',u['code']) for u in urn_list) and election.state not in ('SEALED',):
            raise DomainError('Zerésimas devem ser emitidas antes da abertura.')
    result=verify_final_tally_integrity(db) if kind=='result' else None
    if result and result.get('invalid',0):raise DomainError('Há registros inválidos na apuração. Não publique como votos nulos.')
    rows=[]
    def utc(value):
        if not value:return None
        parsed=datetime.fromisoformat(value) if isinstance(value,str) else value
        return parsed.replace(tzinfo=timezone.utc).isoformat() if parsed.tzinfo is None else parsed.isoformat()
    snapshot=json.loads(election.zero_snapshot_json) if election.zero_snapshot_json else {}
    evidence={'software_version':APP_VERSION,'zero_issued_at':utc(snapshot.get('issued_at')) if kind!='configuration' else None,
              'opened_at':utc(election.opened_at) if kind=='result' else None,'closed_at':utc(election.closed_at) if kind=='result' else None,
              'zero_snapshot_hash':election.zero_snapshot_hash if kind!='configuration' else None,
              'ballot_set_hash':result.get('ballot_head_hash') if result else None}
    for urn in urn_list:
        code=urn['code'] if urn else ''
        if urn_code is not None and code!=urn_code:continue
        old=latest(db,election.election_uuid,kind,code)
        if old and not correction:rows.append(old);continue
        if correction and not old:raise DomainError('Não há documento anterior para retificar.')
        # A retification adds an authenticated explanatory note; sealed values remain unchanged.
        totals=None
        if urn:
            counts=(result.get('per_urn') or {}).get(code,{}) if result else {}
            by_number={s['number']:s['votes'] for s in counts.get('slates',[])}
            total=int(counts.get('total',0))
            totals={'registered':int(db.scalar(select(func.count()).select_from(Voter))) if public['identified'] else None,'slates':[{'number':s['number'],'votes':int(by_number.get(s['number'],0))} for s in public['slates']],
                    'blank':int(counts.get('blank',0)),'null':0,'total':total,
                    'attendance':total if public['identified'] else None}
        doc={'schema_version':1,'id':str(uuid4()),'kind':kind,'revision':old.revision+1 if old else 1,
             'previous':old.digest if old else None,'correction':correction,'created_at':datetime.now(timezone.utc).isoformat(),
             'election':public,'urn_id':urn['id'] if urn else None,'configuration_digest':base_digest,'totals':totals,'evidence':evidence}
        if old and correction:
            old_doc=verify_package(old.package,cfg.fingerprint)['document']
            doc['election']=old_doc['election'];doc['totals']=old_doc['totals'];doc['configuration_digest']=old_doc['configuration_digest'];doc['evidence']=old_doc['evidence']
        doc=Document.model_validate(doc).model_dump();qr=links(doc,key)
        pdf=render_pdf(doc,qr,photos);package=sign_package(doc,{'document.pdf':pdf,**photos},key)
        row=PublicationDocument(id=doc['id'],election_id=election.election_uuid,kind=kind,urn_code=code,revision=doc['revision'],digest=digest(canonical(doc)),package_hash=digest(package),package=package,qr_json=json.dumps(qr))
        db.add(row);db.flush();rows.append(row)
        append_audit(db,'PUBLIC_DOCUMENT_SIGNED',actor,{'id':row.id,'kind':kind,'urn':code,'revision':row.revision,'digest':row.digest})
    return rows

def qr_for(db,kind,urn):
    from .services import get_election
    row=latest(db,get_election(db).election_uuid,kind,urn.code) if urn else None
    return json.loads(row.qr_json) if row else None

def ready_to_export(db,row):
    if row.kind=='configuration':return True
    urn=db.scalar(select(Urn).where(Urn.code==row.urn_code))
    if not urn:return False
    commands=db.scalars(select(DevicePrintCommand).where(DevicePrintCommand.urn_id==urn.id,DevicePrintCommand.kind==row.kind,DevicePrintCommand.success==True,DevicePrintCommand.completed_at.is_not(None)))
    for cmd in commands:
        payload=json.loads(cmd.payload_json)
        if ((payload.get('paper') or {}).get('publication') or {}).get('document_id')==row.id:
            return True
    return False

def pending(db):
    from .services import get_election
    eid=get_election(db).election_uuid
    return [r for r in db.scalars(select(PublicationDocument).where(PublicationDocument.election_id==eid,PublicationDocument.exported==False)) if ready_to_export(db,r)]

def export_rows(db,rows,drive,actor):
    written=[]
    for row in rows:
        path=export_package(row.package,drive)
        row.exported=True;written.append(path.name)
        append_audit(db,'PUBLIC_DOCUMENT_EXPORTED',actor,{'id':row.id,'sha256':row.package_hash})
    db.commit()
    return written
