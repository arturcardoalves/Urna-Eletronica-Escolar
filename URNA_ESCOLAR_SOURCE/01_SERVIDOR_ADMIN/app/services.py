from __future__ import annotations
import json
import secrets
import hashlib
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import append_audit
from .config import APP_VERSION, PUBLIC_KEY_PATH, MAX_URNS, DATA_DIR, BASE_DIR
from .internal_key import ensure_internal_keypair
from .models import (
    AnonymousVotingAuthorization, AuditEvent, Ballot, Election, ElectionState, Slate, Urn, UrnStatus, User, UserRole,
    Voter, VoterStatus, VotingAuthorization, Setting, VoterAmendment, NativeVoteState,
)
from .security import canonical_json, encrypt_ballot, random_token, sha256_text
from .integrity import current_software_hash, public_key_fingerprint, verify_audit_chain


class DomainError(Exception):
    pass


def get_election(db: Session) -> Election:
    election = db.execute(select(Election).limit(1)).scalar_one_or_none()
    if election is None:
        election = Election()
        db.add(election)
        db.flush()
    return election


def _logo_digest(logo_path: str | None) -> str | None:
    if not logo_path:
        return None
    rel = logo_path.lstrip('/')
    if rel == 'static/sounds/final.mp3':
        override = DATA_DIR / 'user_static' / 'sounds' / 'final.mp3'
        path = override if override.exists() else (BASE_DIR / 'app' / rel)
    elif rel.startswith('user-static/'):
        path = DATA_DIR / 'user_static' / rel[len('user-static/'): ]
    elif rel.startswith('static/'):
        path = BASE_DIR / 'app' / rel
    else:
        path = BASE_DIR / rel
    if not path.exists() or not path.is_file():
        return 'MISSING'
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def election_config_payload(db: Session) -> dict:
    """Immutable election configuration captured by the seal.

    Operational/ephemeral state (printer availability, last seen, voter status,
    sessions) is intentionally excluded; anything capable of changing who can
    vote or how a ballot is interpreted is included.
    """
    election = get_election(db)
    slates = db.execute(select(Slate).where(Slate.active == True).order_by(Slate.number)).scalars().all()
    urns = db.execute(select(Urn).order_by(Urn.code)).scalars().all()
    users = db.execute(select(User).where(User.active == True).order_by(User.username)).scalars().all()
    voters = db.execute(
        select(Voter.enrollment, Voter.name, Voter.class_code, Voter.shift)
        .where(Voter.exceptional_addition == False)
        .order_by(Voter.enrollment)
    ).all()
    return {
        "version": APP_VERSION,
        "election": {
            "name": election.name,
            "institution_name": election.institution_name,
            "allow_blank": election.allow_blank,
            "voter_identification_enabled": election.voter_identification_enabled,
            "voter_lookup_mode": election.voter_lookup_mode,
            "show_members_on_ballot": election.show_members_on_ballot,
            "voting_mode": election.voting_mode,
            "sound_enabled": election.sound_enabled,
            "paper_enabled": election.paper_enabled,
            "paper_show_institution": election.paper_show_institution,
            "paper_show_election_name": election.paper_show_election_name,
            "paper_show_slate_number": election.paper_show_slate_number,
            "paper_show_slate_name": election.paper_show_slate_name,
            "paper_show_members": election.paper_show_members,
            "paper_show_instruction": election.paper_show_instruction,
            "paper_change_warning_enabled": election.paper_change_warning_enabled,
            "paper_change_warning_votes": election.paper_change_warning_votes,
            "zero_copies": election.zero_copies,
            "result_copies": election.result_copies,
            "zero_signature_fields": election.zero_signature_fields,
            "keyboard_confirm_key": election.keyboard_confirm_key,
            "keyboard_correct_key": election.keyboard_correct_key,
            "keyboard_blank_key": election.keyboard_blank_key,
            "paper_instruction_text": election.paper_instruction_text,
            "final_sound_sha256": _logo_digest("/static/sounds/final.mp3"),
        },
        "slates": [
            {
                "number": slate.number,
                "name": slate.name,
                "logo_path": slate.logo_path,
                "logo_sha256": _logo_digest(slate.logo_path),
                "members": [
                    {"role": member.role_name, "name": member.person_name, "order": member.display_order}
                    for member in sorted(slate.members, key=lambda x: x.display_order)
                ],
            }
            for slate in slates
        ],
        "urns": [
            {"code": urn.code, "name": urn.name, "device_secret_hash": urn.device_secret_hash,
             "voting_mode_override": urn.voting_mode_override or "INHERIT"}
            for urn in urns
        ],
        "users": [
            {"username": row.username, "display_name": row.display_name, "role": row.role,
             "password_hash": row.password_hash, "active": row.active}
            for row in users
        ],
        "voters": ([
            {"enrollment": e, "name": n, "class_code": c, "shift": sh}
            for e, n, c, sh in voters
        ] if election.voter_identification_enabled else []),
    }


AMENDMENT_GENESIS = "0" * 64


def _amendment_payload(row: VoterAmendment) -> dict:
    return {
        "voter_id": row.voter_id,
        "enrollment": row.enrollment,
        "name": row.name,
        "class_code": row.class_code,
        "shift": row.shift,
        "admin_username": row.admin_username,
        "print_command_id": row.print_command_id,
        "previous_hash": row.previous_hash,
        "created_at": row.created_at.isoformat(timespec="microseconds"),
    }


def append_voter_amendment(
    db: Session, voter: Voter, admin_username: str, print_command_id: str
) -> VoterAmendment:
    last = db.execute(select(VoterAmendment).order_by(VoterAmendment.id.desc()).limit(1)).scalar_one_or_none()
    previous = last.entry_hash if last else AMENDMENT_GENESIS
    created_at = datetime.utcnow()
    row = VoterAmendment(
        voter_id=voter.id, enrollment=voter.enrollment, name=voter.name,
        class_code=voter.class_code, shift=voter.shift, admin_username=admin_username,
        print_command_id=print_command_id, created_at=created_at, previous_hash=previous, entry_hash="",
    )
    row.entry_hash = sha256_text(canonical_json(_amendment_payload(row)))
    db.add(row)
    db.flush()
    return row


def verify_voter_amendments(db: Session) -> None:
    rows = db.execute(select(VoterAmendment).order_by(VoterAmendment.id)).scalars().all()
    previous = AMENDMENT_GENESIS
    amendment_by_voter: dict[int, VoterAmendment] = {}
    for row in rows:
        if row.previous_hash != previous:
            raise DomainError("A cadeia das inclusões excepcionais de eleitores está inconsistente.")
        expected = sha256_text(canonical_json(_amendment_payload(row)))
        if row.entry_hash != expected:
            raise DomainError("Uma inclusão excepcional de eleitor foi alterada depois do registro.")
        previous = row.entry_hash
        amendment_by_voter[row.voter_id] = row

    exceptional = db.execute(select(Voter).where(Voter.exceptional_addition == True)).scalars().all()
    if len(exceptional) != len(rows):
        raise DomainError("O cadastro excepcional de eleitores não corresponde ao registro de emendas.")
    for voter in exceptional:
        row = amendment_by_voter.get(voter.id)
        if not row:
            raise DomainError("Existe eleitor excepcional sem registro de inclusão excepcional.")
        if (voter.enrollment, voter.name, voter.class_code, voter.shift) != (row.enrollment, row.name, row.class_code, row.shift):
            raise DomainError("Os dados de um eleitor excepcional não correspondem ao registro de inclusão.")


def _sealed_audit_details(db: Session, election: Election) -> dict:
    events = db.execute(select(AuditEvent).where(AuditEvent.event_type == "ELECTION_SEALED").order_by(AuditEvent.id)).scalars().all()
    for event in events:
        try:
            details = json.loads(event.details_json or "{}")
        except Exception:
            continue
        if details.get("election_uuid") == election.election_uuid:
            return details
    raise DomainError("O registro original da lacração não foi encontrado no log de auditoria.")


def verify_zero_snapshot_integrity(db: Session) -> None:
    election = get_election(db)
    if not election.zero_snapshot_json and not election.zero_snapshot_hash:
        return
    if not election.zero_snapshot_json or not election.zero_snapshot_hash:
        raise DomainError("O registro da zerésima está incompleto.")
    expected = sha256_text(election.zero_snapshot_json)
    if expected != election.zero_snapshot_hash:
        raise DomainError("A zerésima armazenada foi alterada depois da emissão.")
    events = db.execute(select(AuditEvent).where(AuditEvent.event_type == "ZERO_ISSUED").order_by(AuditEvent.id)).scalars().all()
    matched = False
    for event in events:
        try:
            details = json.loads(event.details_json or "{}")
        except Exception:
            continue
        if details.get("snapshot_hash") == election.zero_snapshot_hash:
            matched = True
            break
    if not matched:
        raise DomainError("A zerésima não corresponde ao registro original do log de auditoria.")


def verify_sealed_integrity(db: Session) -> None:
    election = get_election(db)
    if election.state == ElectionState.CONFIG.value:
        return
    if not election.config_hash or not election.software_hash or not election.public_key_fingerprint:
        raise DomainError("A lacração de segurança está incompleta. Não prossiga com a votação.")
    audit_ok, _ = verify_audit_chain(db)
    if not audit_ok:
        raise DomainError("A cadeia de auditoria foi alterada ou está inconsistente.")
    sealed = _sealed_audit_details(db, election)
    if sealed.get("config_hash") != election.config_hash or sealed.get("software_hash") != election.software_hash or sealed.get("public_key_fingerprint") != election.public_key_fingerprint:
        raise DomainError("Os hashes atuais não correspondem ao registro original da lacração.")
    live_config = sha256_text(canonical_json(election_config_payload(db)))
    if live_config != election.config_hash:
        raise DomainError("A configuração da eleição foi alterada depois da lacração.")
    live_software = current_software_hash()
    if live_software != election.software_hash:
        raise DomainError("Os arquivos do sistema foram alterados depois da lacração.")
    live_key = public_key_fingerprint(PUBLIC_KEY_PATH)
    if live_key != election.public_key_fingerprint:
        raise DomainError("A chave pública da eleição não corresponde à chave lacrada.")
    verify_voter_amendments(db)
    verify_zero_snapshot_integrity(db)


def seal_election(db: Session, actor: str) -> Election:
    election = get_election(db)
    if election.state != ElectionState.CONFIG.value:
        raise DomainError("A eleição só pode ser lacrada a partir da configuração.")
    urn_count = len(db.execute(select(Urn)).scalars().all())
    if urn_count < 1 or urn_count > MAX_URNS:
        raise DomainError("Configure entre 1 e 3 urnas antes de lacrar.")
    slate_count = len(db.execute(select(Slate).where(Slate.active == True)).scalars().all())
    if slate_count < 1:
        raise DomainError("Cadastre ao menos uma chapa.")
    voter_count = len(db.execute(select(Voter)).scalars().all())
    if election.voter_identification_enabled and voter_count < 1:
        raise DomainError("Cadastre ao menos um eleitor ou desative a identificação de eleitores.")
    mesario_count = len(db.execute(select(User).where(User.active == True, User.role == UserRole.MESARIO.value)).scalars().all())
    if mesario_count < 1:
        raise DomainError("Cadastre ao menos um usuário MESÁRIO antes de lacrar.")
    try:
        ensure_internal_keypair()
    except Exception as exc:
        raise DomainError(f"Não foi possível gerar a chave interna da eleição: {exc}") from exc
    election.config_hash = sha256_text(canonical_json(election_config_payload(db)))
    election.software_hash = current_software_hash()
    election.public_key_fingerprint = public_key_fingerprint(PUBLIC_KEY_PATH)
    election.sealed_at = datetime.utcnow()
    election.state = ElectionState.SEALED.value
    append_audit(db, "ELECTION_SEALED", actor, {
        "config_hash": election.config_hash,
        "software_hash": election.software_hash,
        "public_key_fingerprint": election.public_key_fingerprint,
        "election_uuid": election.election_uuid,
    })
    return election


def open_election(db: Session, actor: str) -> Election:
    election = get_election(db)
    if election.state != ElectionState.SEALED.value:
        raise DomainError("A eleição precisa estar lacrada.")
    verify_sealed_integrity(db)
    election.state = ElectionState.OPEN.value
    election.opened_at = datetime.utcnow()
    append_audit(db, "ELECTION_OPENED", actor, {})
    return election


def close_election(db: Session, actor: str) -> Election:
    election = get_election(db)
    if election.state != ElectionState.OPEN.value:
        raise DomainError("A eleição precisa estar aberta.")
    verify_sealed_integrity(db)
    in_progress = db.execute(select(Voter).where(Voter.status == VoterStatus.IN_PROGRESS.value)).scalars().all()
    anonymous_in_progress = db.execute(select(AnonymousVotingAuthorization)).scalars().all()
    if in_progress or anonymous_in_progress:
        raise DomainError("Existe uma votação em andamento em uma das urnas.")
    pending_print = db.scalars(select(Urn).where(Urn.status.in_([UrnStatus.PRINTING.value, UrnStatus.PRINT_ERROR.value]))).first()
    if pending_print:
        raise DomainError("Resolva a impressão pendente antes de encerrar a eleição.")
    election.state = ElectionState.CLOSED.value
    election.closed_at = datetime.utcnow()
    # No reprint is needed after all ballots have printed and voting is closed.
    # Do not carry the last plaintext-equivalent print payload into archives.
    for state in db.scalars(select(NativeVoteState)).all():
        state.encrypted_payload = ""
    for urn in db.scalars(select(Urn)).all():
        urn.pending_reprint_ballot_id = None
        urn.reprint_authorized = False
        urn.last_vote_at = None
    append_audit(db, "ELECTION_CLOSED", actor, {})
    return election


def authorize_voter(db: Session, enrollment: str, urn_code: str, actor: str) -> str:
    election = get_election(db)
    if election.state != ElectionState.OPEN.value:
        raise DomainError("A votação não está aberta.")
    verify_sealed_integrity(db)
    voter = db.execute(select(Voter).where(Voter.enrollment == enrollment).with_for_update()).scalar_one_or_none()
    if not voter:
        raise DomainError("Eleitor não encontrado.")
    if voter.status == VoterStatus.VOTED.value:
        raise DomainError("Este eleitor já votou.")
    if voter.status == VoterStatus.IN_PROGRESS.value:
        raise DomainError("Este eleitor já está em processo de votação.")
    urn = db.execute(select(Urn).where(Urn.code == urn_code).with_for_update()).scalar_one_or_none()
    if not urn:
        raise DomainError("Urna não encontrada.")
    from .deployment import require_ready, clear_previous_vote
    require_ready(urn, election)
    clear_previous_vote(db, urn)
    token = random_token(24)
    auth = VotingAuthorization(
        urn_token=token,
        voter_id=voter.id,
        urn_id=urn.id,
    )
    voter.status = VoterStatus.IN_PROGRESS.value
    voter.active_urn_id = urn.id
    urn.status = UrnStatus.IN_USE.value
    db.add(auth)
    # Não gravamos evento individual de liberação: o horário/ordem de liberações
    # poderia facilitar correlação entre identidade e sequência dos votos.
    return token


def cancel_authorization(db: Session, enrollment: str, actor: str) -> None:
    voter = db.execute(select(Voter).where(Voter.enrollment == enrollment).with_for_update()).scalar_one_or_none()
    if not voter or voter.status != VoterStatus.IN_PROGRESS.value:
        raise DomainError("Não há liberação pendente para este eleitor.")
    auth = db.execute(
        select(VotingAuthorization).where(
            VotingAuthorization.voter_id == voter.id,
        )
    ).scalar_one_or_none()
    if auth:
        urn = db.get(Urn, auth.urn_id)
        if urn:
            urn.status = UrnStatus.AVAILABLE.value
        db.delete(auth)
    voter.status = VoterStatus.NOT_VOTED.value
    voter.active_urn_id = None
    # Cancelamento também não entra no log cronológico por eleitor.


def cast_vote(db: Session, urn_code: str, token: str, choice: dict) -> str:
    election = get_election(db)
    if election.state != ElectionState.OPEN.value:
        raise DomainError("A votação não está aberta.")
    verify_sealed_integrity(db)
    voter = None
    anonymous_auth = None
    if election.voter_identification_enabled:
        auth = db.execute(
            select(VotingAuthorization).where(VotingAuthorization.urn_token == token).with_for_update()
        ).scalar_one_or_none()
        if not auth:
            raise DomainError("Autorização inválida ou já utilizada.")
        urn = db.get(Urn, auth.urn_id)
        if not urn or urn.code != urn_code:
            raise DomainError("Esta autorização pertence a outra urna.")
        voter = db.get(Voter, auth.voter_id)
        if not voter or voter.status != VoterStatus.IN_PROGRESS.value:
            raise DomainError("Estado do eleitor inválido.")
    else:
        anonymous_auth = db.execute(
            select(AnonymousVotingAuthorization).where(AnonymousVotingAuthorization.urn_token == token).with_for_update()
        ).scalar_one_or_none()
        if not anonymous_auth:
            raise DomainError("Sessão anônima inválida ou já utilizada.")
        urn = db.get(Urn, anonymous_auth.urn_id)
        if not urn or urn.code != urn_code:
            raise DomainError("Esta sessão pertence a outra urna.")

    if choice.get("type") == "blank":
        if not election.allow_blank:
            raise DomainError("Voto em branco está desabilitado.")
        ballot_payload = {"type": "blank"}
    elif choice.get("type") == "slate":
        try:
            slate_number = int(choice.get("number"))
        except (TypeError, ValueError):
            raise DomainError("Número de chapa inválido.") from None
        slate = db.execute(select(Slate).where(Slate.number == slate_number, Slate.active == True)).scalar_one_or_none()
        if not slate:
            raise DomainError("Número de chapa inválido.")
        ballot_payload = {"type": "slate", "number": slate.number}
    else:
        raise DomainError("Escolha inválida.")

    public_key_pem = PUBLIC_KEY_PATH.read_bytes()
    ciphertext = encrypt_ballot(public_key_pem, ballot_payload)

    # RDV escolar: cada voto recebe, no momento da gravação, uma posição aleatória
    # dentro do universo de eleitores. O registro do voto não carrega eleitor nem
    # horário; a posição aleatória é a ordem usada nas exportações/recontagens.
    used_slots = {int(row[0]) for row in db.execute(select(Ballot.rdv_slot).where(Ballot.rdv_slot.is_not(None))).all()}
    if election.voter_identification_enabled:
        total_voters = len(db.execute(select(Voter.id)).all())
        available_slots = [i for i in range(1, total_voters + 1) if i not in used_slots]
        if not available_slots:
            raise DomainError("Não há posições RDV disponíveis para registrar o voto.")
        rdv_slot = secrets.choice(available_slots)
    else:
        # Sem cadastro nominal não existe universo fixo de eleitores. O RDV usa
        # uma posição aleatória ampla e única, sem revelar a ordem dos votos.
        rdv_slot = secrets.randbelow(2_000_000_000) + 1
        while rdv_slot in used_slots:
            rdv_slot = secrets.randbelow(2_000_000_000) + 1

    # Integridade sem sequência cronológica: cada voto é autenticado por sua
    # posição RDV aleatória e o hash geral é um compromisso do CONJUNTO de votos.
    # Assim, nem previous_hash nem o hash global revelam a ordem de comparecimento.
    slot_anchor = sha256_text(f"RDV-SLOT:{rdv_slot}")
    entry_hash = sha256_text(canonical_json({
        "slot": rdv_slot, "ciphertext": ciphertext, "urn": urn.code, "anchor": slot_anchor,
    }))
    ballot = Ballot(
        ciphertext=ciphertext,
        previous_hash=slot_anchor,
        entry_hash=entry_hash,
        urn_code=urn.code,
        rdv_slot=rdv_slot,
        print_status="PENDING" if election.paper_enabled and urn.print_enabled else "DISABLED",
    )
    db.add(ballot)
    db.flush()
    hashes = sorted(str(row[0]) for row in db.execute(select(Ballot.entry_hash)).all())
    aggregate_hash = sha256_text(canonical_json({"rdv_ballot_hashes": hashes})) if hashes else sha256_text(canonical_json({"rdv_ballot_hashes": []}))
    head_setting = db.get(Setting, "ballot_head_hash")
    if head_setting is None:
        db.add(Setting(key="ballot_head_hash", value=aggregate_hash))
    else:
        head_setting.value = aggregate_hash

    if election.voter_identification_enabled:
        db.delete(auth)
        voter.status = VoterStatus.VOTED.value
        voter.active_urn_id = None
    else:
        db.delete(anonymous_auth)
    urn.status = UrnStatus.AVAILABLE.value
    urn.last_vote_at = datetime.utcnow()
    urn.pending_reprint_ballot_id = ballot.id if ballot.print_status == "PENDING" else None
    urn.reprint_authorized = False
    # Não criamos evento de auditoria por voto individual para evitar reconstrução da ordem de votação.
    return ballot.id
