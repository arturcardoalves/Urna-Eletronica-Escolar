"""Ed25519 signatures over canonical ASCII JSON and bounded ZIP containers."""
import base64,hashlib,io,json,re,zipfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .schema import Document

MAX_PACKAGE=8*1024*1024
MAX_ENTRY=8*1024*1024
DOMAIN=b'URNA-PUBLICATION-V1\0'
QR_DOMAIN=b'URNA-QR-V1\0'
class InvalidPackage(ValueError): pass

def canonical(obj): return json.dumps(obj,ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')
def digest(data): return hashlib.sha256(data).hexdigest()
def b64(data): return base64.urlsafe_b64encode(data).decode().rstrip('=')
def unb64(text):
    if not isinstance(text,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',text): raise InvalidPackage('Base64 inválido')
    return base64.urlsafe_b64decode(text+'='*((-len(text))%4))
def load_json(raw):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d: raise InvalidPackage('Campos JSON repetidos')
            d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(InvalidPackage('Número inválido')))

def sign_package(document,assets,key):
    doc=Document.model_validate(document).model_dump()
    expected={'document.pdf'}|{s['photo'] for s in doc['election']['slates'] if s['photo']}
    if set(assets)!=expected: raise InvalidPackage('Arquivos incompletos')
    public=b64(key.public_key().public_bytes_raw())
    manifest={'document':doc,'public_key':public,'assets':{n:{'sha256':digest(v),'size':len(v)} for n,v in sorted(assets.items())}}
    envelope={'manifest':manifest,'signature':b64(key.sign(DOMAIN+canonical(manifest)))}
    out=io.BytesIO()
    # Stored entries keep verification inexpensive on the Cloudflare Free CPU budget.
    # PDF and PNG already compress their internal content. Bytes remain deterministic.
    with zipfile.ZipFile(out,'w',zipfile.ZIP_STORED) as z:
        for n,data in [('manifest.json',canonical(envelope)),*sorted(assets.items())]:
            info=zipfile.ZipInfo(n,date_time=(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_STORED
            z.writestr(info,data)
    raw=out.getvalue();verify_package(raw)
    return raw

def verify_package(raw,expected_fingerprint=None,expected_election=None):
    try:
        if len(raw)>MAX_PACKAGE: raise InvalidPackage('Pacote excede o limite')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos=z.infolist();names=[x.filename for x in infos]
            if len(names)!=len(set(names)) or not 2<=len(names)<=102: raise InvalidPackage('Arquivos repetidos ou em excesso')
            if sum(i.file_size for i in infos)>MAX_PACKAGE or any(i.file_size>MAX_ENTRY or i.flag_bits&1 for i in infos): raise InvalidPackage('Conteúdo excessivo ou criptografado')
            if any(not re.fullmatch(r'(manifest\.json|document\.pdf|photo-[0-9]{1,2}\.png)',n) for n in names): raise InvalidPackage('Arquivo não permitido')
            content={n:z.read(n) for n in names}
        envelope=load_json(content.pop('manifest.json'))
        if set(envelope)!={'manifest','signature'}: raise InvalidPackage('Envelope inválido')
        m=envelope['manifest']
        if set(m)!={'document','public_key','assets'}: raise InvalidPackage('Manifesto inválido')
        doc=Document.model_validate(m['document']).model_dump()
        if canonical(doc)!=canonical(m['document']): raise InvalidPackage('Documento não canônico')
        pub=unb64(m['public_key']);fp=digest(pub)
        if expected_fingerprint and fp!=expected_fingerprint: raise InvalidPackage('Chave não reconhecida')
        if expected_election and doc['election']['id']!=expected_election: raise InvalidPackage('Eleição diferente')
        Ed25519PublicKey.from_public_bytes(pub).verify(unb64(envelope['signature']),DOMAIN+canonical(m))
        expected={'document.pdf'}|{s['photo'] for s in doc['election']['slates'] if s['photo']}
        if set(content)!=expected or set(m['assets'])!=expected: raise InvalidPackage('Arquivos extras ou ausentes')
        for n,v in content.items():
            if m['assets'][n]!={'size':len(v),'sha256':digest(v)}: raise InvalidPackage('Arquivo adulterado: '+n)
            if n.endswith('.pdf') and not v.startswith(b'%PDF-'): raise InvalidPackage('PDF inválido')
            if n.endswith('.png'):
                from PIL import Image
                with Image.open(io.BytesIO(v)) as im:
                    if im.format!='PNG' or im.width>1600 or im.height>1600: raise InvalidPackage('Foto inválida')
                    im.verify()
        return {'envelope':envelope,'document':doc,'assets':content,'fingerprint':fp,'digest':digest(canonical(doc)),'package_hash':digest(raw)}
    except InvalidPackage: raise
    except Exception as exc: raise InvalidPackage('Pacote inválido ou assinatura não confere') from exc

def qr_text(doc,key):
    # Carries a signed digest; compare the full document/PDF with the package offline.
    parts=['UE1',doc['election']['id'],doc['id'],doc['urn_id'] or '-',doc['kind'],str(doc['revision']),digest(canonical(doc)),b64(key.public_key().public_bytes_raw())]
    data='|'.join(parts)
    return data+'|'+b64(key.sign(QR_DOMAIN+data.encode('ascii')))

def verify_qr(text,expected_fingerprint=None,package=None):
    try:
        if '#' in text:
            from urllib.parse import urlsplit,unquote
            text=unquote(urlsplit(text).fragment)
        parts=text.strip().split('|')
        if len(parts)!=9 or parts[0]!='UE1' or len(text)>700: raise InvalidPackage('QR não reconhecido')
        pub=unb64(parts[7]);fp=digest(pub)
        Ed25519PublicKey.from_public_bytes(pub).verify(unb64(parts[8]),QR_DOMAIN+'|'.join(parts[:8]).encode('ascii'))
        if expected_fingerprint and fp!=expected_fingerprint: raise InvalidPackage('Chave não reconhecida')
        if package:
            p=verify_package(package,fp,parts[1]);d=p['document']
            if [d['id'],d['urn_id'] or '-',d['kind'],str(d['revision']),p['digest']]!=parts[2:7]: raise InvalidPackage('QR e pacote divergem')
        return {'election_id':parts[1],'document_id':parts[2],'digest':parts[6],'fingerprint':fp,'trusted':bool(expected_fingerprint)}
    except InvalidPackage: raise
    except Exception as exc: raise InvalidPackage('Assinatura do QR inválida') from exc
