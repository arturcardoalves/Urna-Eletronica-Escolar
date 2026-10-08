import json
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import AuditEvent
from .security import canonical_json, sha256_text

GENESIS = "0" * 64


def append_audit(db: Session, event_type: str, actor: str, details: dict | None = None) -> AuditEvent:
    last = db.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)).scalar_one_or_none()
    prev = last.entry_hash if last else GENESIS
    created_at = datetime.utcnow()
    payload = {
        "event_type": event_type,
        "actor": actor,
        "details": details or {},
        "previous_hash": prev,
        "created_at": created_at.isoformat(timespec="microseconds"),
    }
    entry_hash = sha256_text(canonical_json(payload))
    event = AuditEvent(
        event_type=event_type,
        actor=actor,
        details_json=json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
        previous_hash=prev,
        entry_hash=entry_hash,
        created_at=created_at,
    )
    db.add(event)
    # Garante que dois eventos adicionados na mesma transação formem uma cadeia
    # correta. Sem o flush, uma segunda chamada poderia não enxergar o evento
    # recém-adicionado e reutilizar o mesmo previous_hash.
    db.flush()
    return event
