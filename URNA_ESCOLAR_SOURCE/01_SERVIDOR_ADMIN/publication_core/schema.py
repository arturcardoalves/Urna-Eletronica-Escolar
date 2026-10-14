"""Strict public schemas: reject fields that are not explicitly publishable."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator
from uuid import UUID
from urllib.parse import urlsplit

class PublicModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

class Member(PublicModel):
    role: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=160)

class Slate(PublicModel):
    number: StrictInt = Field(ge=0, le=99)
    name: str = Field(min_length=1, max_length=150)
    members: list[Member] = Field(max_length=100)
    photo: str | None = None
    @field_validator('photo')
    @classmethod
    def photo_name(cls, v):
        import re
        if v is not None and not re.fullmatch(r'photo-[0-9]{1,2}\.png', v): raise ValueError('Foto inválida')
        return v

class Urn(PublicModel):
    id: str
    code: str = Field(min_length=1,max_length=20)
    name: str = Field(min_length=1,max_length=80)
    @field_validator('id')
    @classmethod
    def uuid(cls,v):
        if str(UUID(v)) != v: raise ValueError('UUID não canônico')
        return v

class Election(PublicModel):
    id: str
    name: str = Field(min_length=1,max_length=160)
    school: str = Field(max_length=180)
    public_url: str = Field(max_length=160)
    identified: bool
    registered: StrictInt | None = Field(default=None,ge=0,le=1_000_000_000)
    allow_blank: bool
    sealed_at: str
    config_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    slates: list[Slate] = Field(min_length=1,max_length=100)
    urns: list[Urn] = Field(min_length=1,max_length=3)
    @field_validator('id')
    @classmethod
    def uuid(cls,v): return Urn.uuid(v)
    @field_validator('public_url')
    @classmethod
    def url(cls,v):
        u=urlsplit(v)
        if len(v)>160 or any(c.isspace() or ord(c)<32 for c in v) or u.port==0 or u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
            raise ValueError('Use a origem HTTPS do portal, sem caminho, usuário ou parâmetros.')
        host=u.hostname.encode('idna').decode('ascii').lower()
        if ':' in host:host='['+host+']'
        return 'https://'+host+(':'+str(u.port) if u.port not in (None,443) else '')
    @field_validator('sealed_at')
    @classmethod
    def sealed_time(cls,v):
        from datetime import datetime
        if datetime.fromisoformat(v).tzinfo is None:raise ValueError('Data de lacração sem fuso')
        return v
    @model_validator(mode='after')
    def unique(self):
        if len({s.number for s in self.slates}) != len(self.slates): raise ValueError('Chapas repetidas')
        if len({u.id for u in self.urns}) != len(self.urns) or len({u.code for u in self.urns}) != len(self.urns): raise ValueError('Urnas repetidas')
        if self.identified != (self.registered is not None): raise ValueError('Cadastro incompatível')
        return self

class Count(PublicModel):
    number: StrictInt = Field(ge=0,le=99)
    votes: StrictInt = Field(ge=0,le=1_000_000_000)

class Totals(PublicModel):
    registered: StrictInt | None = Field(ge=0,le=1_000_000_000)
    slates: list[Count] = Field(min_length=1,max_length=100)
    blank: StrictInt = Field(ge=0,le=1_000_000_000)
    null: StrictInt = Field(ge=0,le=1_000_000_000)
    total: StrictInt = Field(ge=0,le=1_000_000_000)
    attendance: StrictInt | None = Field(ge=0,le=1_000_000_000)
    @model_validator(mode='after')
    def sum(self):
        if self.total != sum(x.votes for x in self.slates)+self.blank+self.null: raise ValueError('Total inconsistente')
        if len({s.number for s in self.slates}) != len(self.slates): raise ValueError('Chapas repetidas')
        if self.attendance is not None and self.attendance != self.total: raise ValueError('Comparecimento inconsistente')
        return self

class Evidence(PublicModel):
    software_version: str = Field(min_length=1,max_length=40)
    zero_issued_at: str | None
    opened_at: str | None
    closed_at: str | None
    zero_snapshot_hash: str | None = Field(pattern=r'^[0-9a-f]{64}$')
    ballot_set_hash: str | None = Field(pattern=r'^[0-9a-f]{64}$')
    @field_validator('zero_issued_at','opened_at','closed_at')
    @classmethod
    def timestamp(cls,value):
        from datetime import datetime
        if value is not None and datetime.fromisoformat(value).tzinfo is None:raise ValueError('Data sem fuso')
        return value

class Document(PublicModel):
    schema_version: Literal[1]
    id: str
    kind: Literal['configuration','zero','result']
    revision: StrictInt = Field(ge=1,le=10000)
    previous: str | None = Field(default=None,pattern=r'^[0-9a-f]{64}$')
    correction: str = Field(default='',max_length=500)
    created_at: str
    election: Election
    urn_id: str | None
    configuration_digest: str | None = Field(default=None,pattern=r'^[0-9a-f]{64}$')
    totals: Totals | None
    evidence: Evidence
    @field_validator('id')
    @classmethod
    def uuid(cls,v): return Urn.uuid(v)
    @model_validator(mode='after')
    def semantics(self):
        from datetime import datetime
        if datetime.fromisoformat(self.created_at).tzinfo is None: raise ValueError('Data sem fuso')
        if (self.revision == 1) != (self.previous is None): raise ValueError('Cadeia de revisão inválida')
        if self.revision>1 and not self.correction.strip(): raise ValueError('Informe motivo da retificação')
        if self.kind=='configuration':
            if self.urn_id is not None or self.totals is not None or self.configuration_digest is not None: raise ValueError('Configuração inválida')
        else:
            if self.urn_id not in {u.id for u in self.election.urns} or self.totals is None or not self.configuration_digest: raise ValueError('Documento incompleto')
            if {s.number for s in self.totals.slates} != {s.number for s in self.election.slates}: raise ValueError('Chapas incompatíveis')
            if self.kind=='zero' and self.totals.total: raise ValueError('Zerésima com votos')
            if not self.election.allow_blank and self.totals.blank: raise ValueError('Brancos desabilitados')
            if self.election.identified != (self.totals.attendance is not None): raise ValueError('Comparecimento incompatível')
            if self.election.identified != (self.totals.registered is not None): raise ValueError('Cadastro incompatível')
            if self.totals.registered is not None and (self.totals.total>self.totals.registered or self.totals.registered<self.election.registered): raise ValueError('Total excede cadastro ou cadastro regrediu')
            if not self.evidence.zero_snapshot_hash or not self.evidence.zero_issued_at:raise ValueError('Registro da Zerésima ausente')
            if self.kind=='result' and not all((self.evidence.opened_at,self.evidence.closed_at,self.evidence.ballot_set_hash)):raise ValueError('Registro de encerramento ausente')
            if self.kind=='result' and datetime.fromisoformat(self.evidence.closed_at)<datetime.fromisoformat(self.evidence.opened_at):raise ValueError('Encerramento anterior à abertura')
        return self
