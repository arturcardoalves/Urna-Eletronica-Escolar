"""Explicit test-only generator. Never imported by production components."""
import base64
import copy
import json
import sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN'),str(ROOT/'tests')]
from test_publication import packets
from publication_core.protocol import canonical,digest,verify_package
p=packets.__wrapped__()
revision=copy.deepcopy(p['docs'][3])
revision.update(id=str(uuid4()),revision=2,previous=digest(canonical(revision)),correction='Nota de esclarecimento para teste isolado')
raw_revision=p['build'](revision)
bad=copy.deepcopy(revision);bad.update(id=str(uuid4()),revision=3,previous=digest(canonical(revision)))
bad['totals'].update(total=2,attendance=2);bad['totals']['slates'][0]['votes']=2
conflict=copy.deepcopy(p['docs'][0]);conflict['correction']='Conteúdo diferente com o mesmo identificador'
out={'raw':[base64.b64encode(raw).decode() for raw in p['raw']], 'trust':p['trust'], 'eid':p['eid'], 'docs':p['docs'],
     'revision':base64.b64encode(raw_revision).decode(),'changed_totals':base64.b64encode(p['build'](bad)).decode(),
     'conflict':base64.b64encode(p['build'](conflict)).decode(),'revision_id':revision['id']}
from publication_core.documents import links,qr_image
qr=links(p['docs'][3],p['key'])['verification']
frame=qr_image(qr).convert('RGBA')
next_config=copy.deepcopy(p['docs'][0]);next_id=str(uuid4());next_config['id']=str(uuid4());next_config['election']['id']=next_id;next_config['election']['name']='Nova eleição atual'
next_raw=p['build'](next_config)
out['trust'][next_id]=copy.deepcopy(out['trust'][p['eid']])
old_revision=copy.deepcopy(p['docs'][0]);old_revision.update(id=str(uuid4()),revision=2,previous=digest(canonical(p['docs'][0])),correction='Nota na eleição anterior')
out.update(next_config=base64.b64encode(next_raw).decode(),old_revision=base64.b64encode(p['build'](old_revision)).decode())
out.update(qr=qr,envelope=verify_package(p['raw'][3])['envelope'],frame={'width':frame.width,'height':frame.height,'rgba':base64.b64encode(frame.tobytes()).decode()})
Path(sys.argv[1]).write_text(json.dumps(out),encoding='utf-8')
