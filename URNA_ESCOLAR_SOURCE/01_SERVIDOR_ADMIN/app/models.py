from __future__ import annotations
from datetime import datetime
from enum import Enum
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ElectionState(str, Enum):
    CONFIG = "CONFIG"
    SEALED = "SEALED"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MESARIO = "MESARIO"


class VoterStatus(str, Enum):
    NOT_VOTED = "NOT_VOTED"
    IN_PROGRESS = "IN_PROGRESS"
    VOTED = "VOTED"


class UrnStatus(str, Enum):
    OFFLINE = "OFFLINE"
    AVAILABLE = "AVAILABLE"
    IN_USE = "IN_USE"
    PRINT_ERROR = "PRINT_ERROR"
    PRINTING = "PRINTING"


class Election(Base):
    __tablename__ = "elections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), default="Eleição do Grêmio Estudantil")
    institution_name: Mapped[str] = mapped_column(String(180), default="")
    state: Mapped[str] = mapped_column(String(16), default=ElectionState.CONFIG.value)
    allow_blank: Mapped[bool] = mapped_column(Boolean, default=True)
    voter_identification_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    voter_lookup_mode: Mapped[str] = mapped_column(String(24), default="SEARCH_LIST")
    show_members_on_ballot: Mapped[bool] = mapped_column(Boolean, default=True)
    voting_mode: Mapped[str] = mapped_column(String(20), default="SELECTION")
    sound_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    paper_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    paper_show_institution: Mapped[bool] = mapped_column(Boolean, default=True)
    paper_show_election_name: Mapped[bool] = mapped_column(Boolean, default=True)
    paper_show_slate_number: Mapped[bool] = mapped_column(Boolean, default=True)
    paper_show_slate_name: Mapped[bool] = mapped_column(Boolean, default=True)
    paper_show_members: Mapped[bool] = mapped_column(Boolean, default=False)
    paper_show_instruction: Mapped[bool] = mapped_column(Boolean, default=True)
    paper_change_warning_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    paper_change_warning_votes: Mapped[int] = mapped_column(Integer, default=200)
    zero_copies: Mapped[int] = mapped_column(Integer, default=3)
    result_copies: Mapped[int] = mapped_column(Integer, default=3)
    zero_signature_fields: Mapped[bool] = mapped_column(Boolean, default=True)
    keyboard_confirm_key: Mapped[str] = mapped_column(String(40), default="Enter")
    keyboard_correct_key: Mapped[str] = mapped_column(String(40), default="Backspace")
    keyboard_blank_key: Mapped[str] = mapped_column(String(40), default="b")
    paper_instruction_text: Mapped[str] = mapped_column(String(180), default="Dobre e coloque na urna.")
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    software_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    public_key_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    election_uuid: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid.uuid4()))
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    final_tally_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    zero_issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    zero_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    zero_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    display_name: Mapped[str] = mapped_column(String(140))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Voter(Base):
    __tablename__ = "voters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrollment: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    class_code: Mapped[str] = mapped_column(String(20), index=True)
    shift: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20), default=VoterStatus.NOT_VOTED.value)
    active_urn_id: Mapped[int | None] = mapped_column(ForeignKey("urns.id"), nullable=True)
    # Eleitores incluídos excepcionalmente durante a votação não alteram a
    # configuração original lacrada. A inclusão é vinculada a uma emenda
    # append-only e fica sujeita à verificação de integridade própria.
    exceptional_addition: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    exceptional_added_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exceptional_added_by: Mapped[str | None] = mapped_column(String(80), nullable=True)


class VoterAmendment(Base):
    __tablename__ = "voter_amendments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    voter_id: Mapped[int] = mapped_column(ForeignKey("voters.id"), unique=True, index=True)
    enrollment: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(180))
    class_code: Mapped[str] = mapped_column(String(20))
    shift: Mapped[str] = mapped_column(String(30))
    admin_username: Mapped[str] = mapped_column(String(80))
    print_command_id: Mapped[str] = mapped_column(String(36), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    previous_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)


class VoterExceptionPermit(Base):
    __tablename__ = "voter_exception_permits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    print_command_id: Mapped[str] = mapped_column(String(36), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    printed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)



class Slate(Base):
    __tablename__ = "slates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(150))
    logo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    members: Mapped[list[SlateMember]] = relationship(back_populates="slate", cascade="all, delete-orphan")


class SlateMember(Base):
    __tablename__ = "slate_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slate_id: Mapped[int] = mapped_column(ForeignKey("slates.id"))
    role_name: Mapped[str] = mapped_column(String(100))
    person_name: Mapped[str] = mapped_column(String(160))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    slate: Mapped[Slate] = relationship(back_populates="members")


class Urn(Base):
    __tablename__ = "urns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    device_secret_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=UrnStatus.AVAILABLE.value)
    print_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_vote_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pending_reprint_ballot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reprint_authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    printer_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    print_agent_url: Mapped[str] = mapped_column(String(220), default="http://127.0.0.1:8765")
    agent_online: Mapped[bool] = mapped_column(Boolean, default=False)
    printer_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    printer_mode: Mapped[str] = mapped_column(String(20), default="escpos")
    voting_mode_override: Mapped[str] = mapped_column(String(20), default="INHERIT")
    managed_print: Mapped[bool] = mapped_column(Boolean, default=False)
    native_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class VotingAuthorization(Base):
    __tablename__ = "voting_authorizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    urn_token: Mapped[str] = mapped_column(String(96), unique=True)
    voter_id: Mapped[int] = mapped_column(ForeignKey("voters.id"), unique=True)
    urn_id: Mapped[int] = mapped_column(ForeignKey("urns.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnonymousVotingAuthorization(Base):
    __tablename__ = "anonymous_voting_authorizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    urn_token: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    urn_id: Mapped[int] = mapped_column(ForeignKey("urns.id"), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Ballot(Base):
    __tablename__ = "ballots"
    # New installations use random UUIDs as the physical SQLite primary key,
    # avoiding the hidden sequential rowid of ordinary TEXT-primary-key tables.
    # Existing elections are left intact by create_all (no destructive rewrite).
    __table_args__ = {"sqlite_with_rowid": False}
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ciphertext: Mapped[str] = mapped_column(Text)
    previous_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)
    urn_code: Mapped[str] = mapped_column(String(20))
    rdv_slot: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    print_status: Mapped[str] = mapped_column(String(20), default="PENDING")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80))
    actor: Mapped[str] = mapped_column(String(100))
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    previous_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Occurrence(Base):
    __tablename__ = "occurrences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    author: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class UrnDeviceSession(Base):
    __tablename__ = "urn_device_sessions"
    id_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    urn_id: Mapped[int] = mapped_column(ForeignKey("urns.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LoginGuard(Base):
    __tablename__ = "login_guards"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class ElectionArchive(Base):
    __tablename__ = "election_archives"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    institution_name: Mapped[str] = mapped_column(String(180), default="")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    final_tally_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    voter_identification_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    voter_lookup_mode: Mapped[str] = mapped_column(String(24), default="SEARCH_LIST")
    zero_issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    zero_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    zero_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    software_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    public_key_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    election_uuid: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid.uuid4()))
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    database_file: Mapped[str] = mapped_column(String(255))

class DevicePrintCommand(Base):
    __tablename__ = "device_print_commands"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    urn_id: Mapped[int] = mapped_column(ForeignKey("urns.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class PairedComputer(Base):
    __tablename__ = "paired_computers"
    urn_id: Mapped[int] = mapped_column(ForeignKey("urns.id"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    computer_name: Mapped[str] = mapped_column(String(80))


class PairingRequest(Base):
    __tablename__ = "pairing_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    computer_name: Mapped[str] = mapped_column(String(80))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    urn_id: Mapped[int | None] = mapped_column(ForeignKey("urns.id"), nullable=True)


class BrowserLaunch(Base):
    __tablename__ = "browser_launches"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    urn_id: Mapped[int] = mapped_column(ForeignKey("urns.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class NativeVoteState(Base):
    # One transient slot per urn, never a chronological list of ballots.
    # The print payload is encrypted; there is no voter or timestamp here.
    __tablename__ = "native_vote_states"
    urn_id: Mapped[int] = mapped_column(ForeignKey("urns.id"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    job_id: Mapped[str] = mapped_column(String(36))
    encrypted_payload: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String(16), default="PENDING")
