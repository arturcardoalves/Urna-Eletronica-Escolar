from __future__ import annotations

import json

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.integrity import current_software_hash, public_key_fingerprint, verify_audit_chain
from app.models import Ballot, Election, Setting, Voter, VoterStatus
from app.security import canonical_json, sha256_text
from app.services import election_config_payload
from app.tally_service import verify_ballot_chain


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "OK" if ok else "FALHA"
    print(f"[{mark}] {label}" + (f": {detail}" if detail else ""))
    return ok


def main() -> int:
    init_db()
    db = SessionLocal()
    all_ok = True
    try:
        election = db.execute(select(Election).limit(1)).scalar_one_or_none()
        if not election:
            print("[FALHA] Nenhuma eleição encontrada.")
            return 2

        print("URNA ESCOLAR - VERIFICADOR INDEPENDENTE DE INTEGRIDADE")
        print(f"Eleição: {election.name}")
        print(f"ID: {election.election_uuid}")
        print(f"Estado: {election.state}\n")

        live_config = sha256_text(canonical_json(election_config_payload(db)))
        live_software = current_software_hash()
        live_key = public_key_fingerprint()
        all_ok &= check("Configuração lacrada", bool(election.config_hash) and live_config == election.config_hash,
                        f"atual={live_config} / lacrado={election.config_hash or 'ausente'}")
        all_ok &= check("Software lacrado", bool(election.software_hash) and live_software == election.software_hash,
                        f"atual={live_software} / lacrado={election.software_hash or 'ausente'}")
        all_ok &= check("Chave pública lacrada", bool(election.public_key_fingerprint) and live_key == election.public_key_fingerprint,
                        f"atual={live_key or 'ausente'} / lacrado={election.public_key_fingerprint or 'ausente'}")

        audit_ok, audit_head = verify_audit_chain(db)
        all_ok &= check("Cadeia de auditoria", audit_ok, f"âncora={audit_head}")

        ballots = db.execute(select(Ballot)).scalars().all()
        head = db.get(Setting, "ballot_head_hash")
        ballot_ok, ballot_head = verify_ballot_chain(ballots, head.value if head else None)
        all_ok &= check("Cadeia dos votos", ballot_ok, f"votos={len(ballots)} / âncora={ballot_head}")

        voted_count = len(db.execute(select(Voter).where(Voter.status == VoterStatus.VOTED.value)).scalars().all())
        all_ok &= check("Votantes x votos", voted_count == len(ballots), f"votantes={voted_count} / votos={len(ballots)}")

        if election.zero_snapshot_json:
            zero_hash = sha256_text(election.zero_snapshot_json)
            zero_ok = zero_hash == election.zero_snapshot_hash
            try:
                snap = json.loads(election.zero_snapshot_json)
                zero_ok = zero_ok and int(snap.get("ballot_count", -1)) == 0
            except Exception:
                zero_ok = False
            all_ok &= check("Zerésima preservada", zero_ok, f"hash={zero_hash}")
        else:
            print("[INFO] Zerésima ainda não emitida.")

        print("\nRESULTADO: " + ("INTEGRIDADE CONFIRMADA" if all_ok else "INCONSISTÊNCIA DETECTADA"))
        return 0 if all_ok else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
