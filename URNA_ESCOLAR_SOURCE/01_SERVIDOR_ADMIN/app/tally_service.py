import json
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import GENESIS, append_audit
from .integrity import verify_audit_chain
from .models import AuditEvent, Ballot, ElectionState, Setting, Slate, Voter, VoterStatus
from .security import decrypt_ballot, sha256_text, canonical_json
from .services import DomainError, get_election, verify_sealed_integrity


def _unordered_rdv_hash(ballots: list[Ballot]) -> tuple[bool, str]:
    """Validate v1.5 RDV records without reconstructing vote chronology."""
    seen_slots: set[int] = set()
    hashes: list[str] = []
    for ballot in ballots:
        if ballot.rdv_slot is None or ballot.rdv_slot in seen_slots:
            return False, GENESIS
        seen_slots.add(ballot.rdv_slot)
        anchor = sha256_text(f"RDV-SLOT:{ballot.rdv_slot}")
        if ballot.previous_hash != anchor:
            return False, GENESIS
        expected = sha256_text(canonical_json({
            "slot": ballot.rdv_slot, "ciphertext": ballot.ciphertext,
            "urn": ballot.urn_code, "anchor": anchor,
        }))
        if expected != ballot.entry_hash:
            return False, GENESIS
        hashes.append(ballot.entry_hash)
    root = sha256_text(canonical_json({"rdv_ballot_hashes": sorted(hashes)}))
    return True, root


def _legacy_chain_hash(ballots: list[Ballot], expected_head: str | None):
    """Compatibility verifier for elections created before the v1.5 RDV model."""
    if not ballots:
        return (expected_head in (None, GENESIS)), GENESIS
    by_prev: dict[str, list[Ballot]] = {}
    for ballot in ballots:
        by_prev.setdefault(ballot.previous_hash, []).append(ballot)
    current = GENESIS
    visited: set[str] = set()
    while current in by_prev:
        children = by_prev[current]
        if len(children) != 1:
            return False, current
        ballot = children[0]
        expected = sha256_text(ballot.previous_hash + ballot.ciphertext + ballot.urn_code)
        if expected != ballot.entry_hash or ballot.id in visited:
            return False, current
        visited.add(ballot.id)
        current = ballot.entry_hash
    return len(visited) == len(ballots) and current == (expected_head or GENESIS), current


def verify_ballot_chain(ballots: list[Ballot], expected_head: str | None):
    # v1.5 uses independent random RDV slots + an order-independent set hash.
    if ballots and all(b.rdv_slot is not None for b in ballots):
        ok, root = _unordered_rdv_hash(ballots)
        return ok and expected_head is not None and root == expected_head, root
    return _legacy_chain_hash(ballots, expected_head)



def verify_final_tally_integrity(db: Session) -> dict:
    election = get_election(db)
    if election.state != ElectionState.CLOSED.value or not election.final_tally_json:
        raise DomainError("O resultado final ainda não está disponível.")
    verify_sealed_integrity(db)
    audit_ok, _ = verify_audit_chain(db)
    if not audit_ok:
        raise DomainError("A cadeia de auditoria está inconsistente.")
    try:
        result = json.loads(election.final_tally_json)
    except Exception as exc:
        raise DomainError("O resultado final armazenado está ilegível.") from exc

    ballots = db.execute(select(Ballot)).scalars().all()
    head = db.get(Setting, "ballot_head_hash")
    ok, final_head = verify_ballot_chain(ballots, head.value if head else None)
    if not ok or result.get("ballot_head_hash") != final_head:
        raise DomainError("O resultado final não corresponde aos votos armazenados.")
    voted_count = len(db.execute(select(Voter).where(Voter.status == VoterStatus.VOTED.value)).scalars().all())
    if int(result.get("total", -1)) != len(ballots):
        raise DomainError("O total do resultado final não corresponde ao banco de votos.")
    if election.voter_identification_enabled and voted_count != len(ballots):
        raise DomainError("A quantidade de eleitores marcados como votantes difere da quantidade de votos armazenados.")
    if result.get("election_uuid") != election.election_uuid or result.get("config_hash") != election.config_hash or result.get("software_hash") != election.software_hash or result.get("public_key_fingerprint") != election.public_key_fingerprint or result.get("zero_snapshot_hash") != election.zero_snapshot_hash:
        raise DomainError("O resultado final não corresponde à eleição lacrada.")


    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "FINAL_TALLY_CREATED").order_by(AuditEvent.id).limit(1)
    ).scalar_one_or_none()
    if not event or result.get("audit_head_at_tally") != event.entry_hash:
        raise DomainError("O resultado final não corresponde ao registro original da apuração no log de auditoria.")
    try:
        event_details = json.loads(event.details_json or "{}")
    except Exception as exc:
        raise DomainError("O registro de auditoria da apuração está ilegível.") from exc
    if int(event_details.get("total", -1)) != int(result.get("total", -2)) or event_details.get("ballot_head_hash") != result.get("ballot_head_hash"):
        raise DomainError("Os totais da apuração divergem do registro original de auditoria.")
    # New tallies bind the entire result (including distribution per slate/urn),
    # not merely the overall count. Legacy closed elections remain readable.
    if event_details.get("result_hash"):
        original = {key: value for key, value in result.items() if key != "audit_head_at_tally"}
        if sha256_text(canonical_json(original)) != event_details["result_hash"]:
            raise DomainError("A distribuição dos resultados foi alterada depois da apuração.")
    return result

def tally_closed_election(db: Session, private_key_bytes: bytes, password: str, actor: str) -> dict:
    election = get_election(db)
    if election.state != ElectionState.CLOSED.value:
        raise DomainError("A apuração só é permitida depois do encerramento.")
    if election.final_tally_json:
        return verify_final_tally_integrity(db)

    verify_sealed_integrity(db)
    audit_ok, _audit_before = verify_audit_chain(db)
    if not audit_ok:
        raise DomainError("A cadeia de auditoria está inconsistente. A apuração foi bloqueada.")

    ballots = db.execute(select(Ballot)).scalars().all()
    rdv_ballots = sorted(ballots, key=lambda b: (b.rdv_slot is None, b.rdv_slot or 10**9, b.id))
    head = db.get(Setting, "ballot_head_hash")
    ok, final_head = verify_ballot_chain(ballots, head.value if head else None)
    if not ok:
        raise DomainError("A cadeia de integridade dos votos é inválida.")

    voted_count = len(db.execute(select(Voter).where(Voter.status == VoterStatus.VOTED.value)).scalars().all())
    if election.voter_identification_enabled and voted_count != len(ballots):
        raise DomainError("A quantidade de eleitores marcados como votantes difere da quantidade de votos armazenados.")

    slates = db.execute(select(Slate).where(Slate.active == True)).scalars().all()
    valid = {s.number: s.name for s in slates}
    counts = {n: 0 for n in valid}
    blank = 0
    invalid = 0
    per_urn: dict[str, dict] = {}
    try:
        for ballot in rdv_ballots:
            payload = decrypt_ballot(private_key_bytes, password, ballot.ciphertext)
            urn_result = per_urn.setdefault(ballot.urn_code, {
                "total": 0, "blank": 0, "invalid": 0,
                "slates": {n: 0 for n in valid},
            })
            urn_result["total"] += 1
            if payload.get("type") == "blank":
                blank += 1
                urn_result["blank"] += 1
            elif payload.get("type") == "slate" and payload.get("number") in valid:
                number = payload["number"]
                counts[number] += 1
                urn_result["slates"][number] += 1
            else:
                invalid += 1
                urn_result["invalid"] += 1
    except Exception as exc:
        raise DomainError("Não foi possível abrir os votos com a chave interna desta eleição.") from exc

    per_urn_serialized = {}
    for urn_code, item in sorted(per_urn.items()):
        per_urn_serialized[urn_code] = {
            "total": item["total"],
            "blank": item["blank"],
            "invalid": item["invalid"],
            "slates": [{"number": n, "name": valid[n], "votes": item["slates"][n]} for n in sorted(valid)],
        }

    result = {
        "total": len(ballots),
        "blank": blank,
        "invalid": invalid,
        "slates": [{"number": n, "name": valid[n], "votes": counts[n]} for n in sorted(valid)],
        "per_urn": per_urn_serialized,
        "ballot_head_hash": final_head,
        "rdv_slots_used": len([b for b in ballots if b.rdv_slot is not None]),
        "election_uuid": election.election_uuid,
        "config_hash": election.config_hash,
        "software_hash": election.software_hash,
        "public_key_fingerprint": election.public_key_fingerprint,
        "zero_snapshot_hash": election.zero_snapshot_hash,
    }

    event = append_audit(db, "FINAL_TALLY_CREATED", actor, {
        "total": len(ballots), "ballot_head_hash": final_head,
        "result_hash": sha256_text(canonical_json(result)),
    })
    result["audit_head_at_tally"] = event.entry_hash
    election.final_tally_json = json.dumps(result, ensure_ascii=False, sort_keys=True)
    return result
