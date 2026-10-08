from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .config import DB_PATH
from .models import Base

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _connection_record):
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=FULL")
    cur.close()


def init_db() -> None:
    Base.metadata.create_all(engine)
    # Migrações leves para quem atualizar a partir da v0.1.x sem perder a eleição já configurada.
    with engine.begin() as conn:
        election_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(elections)").fetchall()}
        election_additions = {
            "voter_identification_enabled": "BOOLEAN NOT NULL DEFAULT 1",
            "voter_lookup_mode": "TEXT NOT NULL DEFAULT 'SEARCH_LIST'",
            "keyboard_confirm_key": "TEXT NOT NULL DEFAULT 'Enter'",
            "keyboard_correct_key": "TEXT NOT NULL DEFAULT 'Backspace'",
            "keyboard_blank_key": "TEXT NOT NULL DEFAULT 'b'",
            "paper_instruction_text": "TEXT NOT NULL DEFAULT 'Dobre e coloque na urna.'",
            "paper_change_warning_enabled": "BOOLEAN NOT NULL DEFAULT 0",
            "paper_change_warning_votes": "INTEGER NOT NULL DEFAULT 200",
            "zero_issued_at": "DATETIME",
            "result_copies": "INTEGER NOT NULL DEFAULT 3",
            "zero_snapshot_json": "TEXT",
            "zero_snapshot_hash": "TEXT",
            "software_hash": "TEXT",
            "public_key_fingerprint": "TEXT",
            "election_uuid": "TEXT",
            "sealed_at": "DATETIME",
        }
        for col, ddl in election_additions.items():
            if col not in election_cols:
                conn.exec_driver_sql(f"ALTER TABLE elections ADD COLUMN {col} {ddl}")
        conn.exec_driver_sql("UPDATE elections SET election_uuid = lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab', abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6))) WHERE election_uuid IS NULL OR election_uuid = ''")

        archive_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(election_archives)").fetchall()}
        archive_additions = {
            "zero_issued_at": "DATETIME",
            "voter_identification_enabled": "BOOLEAN NOT NULL DEFAULT 1",
            "voter_lookup_mode": "TEXT NOT NULL DEFAULT 'SEARCH_LIST'",
            "result_copies": "INTEGER NOT NULL DEFAULT 3",
            "zero_snapshot_json": "TEXT",
            "zero_snapshot_hash": "TEXT",
            "software_hash": "TEXT",
            "public_key_fingerprint": "TEXT",
            "election_uuid": "TEXT",
            "sealed_at": "DATETIME",
        }
        for col, ddl in archive_additions.items():
            if col not in archive_cols:
                conn.exec_driver_sql(f"ALTER TABLE election_archives ADD COLUMN {col} {ddl}")

        urn_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(urns)").fetchall()}
        if "managed_print" not in urn_cols:
            conn.exec_driver_sql("ALTER TABLE urns ADD COLUMN managed_print BOOLEAN NOT NULL DEFAULT 0")
        if "native_seen_at" not in urn_cols:
            conn.exec_driver_sql("ALTER TABLE urns ADD COLUMN native_seen_at DATETIME")
        if "last_vote_at" not in urn_cols:
            conn.exec_driver_sql("ALTER TABLE urns ADD COLUMN last_vote_at DATETIME")
        if "printer_name" not in urn_cols:
            conn.exec_driver_sql("ALTER TABLE urns ADD COLUMN printer_name TEXT")
        if "print_agent_url" not in urn_cols:
            conn.exec_driver_sql("ALTER TABLE urns ADD COLUMN print_agent_url TEXT NOT NULL DEFAULT 'http://127.0.0.1:8765'")
        if "agent_online" not in urn_cols:
            conn.exec_driver_sql("ALTER TABLE urns ADD COLUMN agent_online BOOLEAN NOT NULL DEFAULT 0")
        if "printer_ready" not in urn_cols:
            conn.exec_driver_sql("ALTER TABLE urns ADD COLUMN printer_ready BOOLEAN NOT NULL DEFAULT 0")
        if "printer_mode" not in urn_cols:
            conn.exec_driver_sql("ALTER TABLE urns ADD COLUMN printer_mode TEXT NOT NULL DEFAULT 'escpos'")
        if "voting_mode_override" not in urn_cols:
            conn.exec_driver_sql("ALTER TABLE urns ADD COLUMN voting_mode_override TEXT NOT NULL DEFAULT 'INHERIT'")

        voter_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(voters)").fetchall()}
        voter_additions = {
            "exceptional_addition": "BOOLEAN NOT NULL DEFAULT 0",
            "exceptional_added_at": "DATETIME",
            "exceptional_added_by": "TEXT",
        }
        for col, ddl in voter_additions.items():
            if col not in voter_cols:
                conn.exec_driver_sql(f"ALTER TABLE voters ADD COLUMN {col} {ddl}")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS voters_exceptional_addition_idx ON voters(exceptional_addition)")

        ballot_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(ballots)").fetchall()}
        if "rdv_slot" not in ballot_cols:
            conn.exec_driver_sql("ALTER TABLE ballots ADD COLUMN rdv_slot INTEGER")
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ballots_rdv_slot_unique ON ballots(rdv_slot) WHERE rdv_slot IS NOT NULL")
        conn.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS ballots_no_update
        BEFORE UPDATE ON ballots
        BEGIN
            SELECT RAISE(ABORT, 'Ballots are append-only');
        END;
        """)
        conn.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS ballots_no_delete
        BEFORE DELETE ON ballots
        BEGIN
            SELECT RAISE(ABORT, 'Ballots are append-only');
        END;
        """)
        conn.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS audit_no_update
        BEFORE UPDATE ON audit_events
        BEGIN
            SELECT RAISE(ABORT, 'Audit log is append-only');
        END;
        """)
        conn.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS audit_no_delete
        BEFORE DELETE ON audit_events
        BEGIN
            SELECT RAISE(ABORT, 'Audit log is append-only');
        END;
        """)
        conn.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS voter_amendments_no_update
        BEFORE UPDATE ON voter_amendments
        BEGIN
            SELECT RAISE(ABORT, 'Voter amendments are append-only');
        END;
        """)
        conn.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS voter_amendments_no_delete
        BEFORE DELETE ON voter_amendments
        BEGIN
            SELECT RAISE(ABORT, 'Voter amendments are append-only');
        END;
        """)
        conn.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS election_config_hash_immutable
        BEFORE UPDATE OF config_hash ON elections
        WHEN OLD.config_hash IS NOT NULL AND NOT (NEW.config_hash IS OLD.config_hash)
        BEGIN
            SELECT RAISE(ABORT, 'Sealed configuration hash is immutable');
        END;
        """)
        conn.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS election_software_hash_immutable
        BEFORE UPDATE OF software_hash ON elections
        WHEN OLD.software_hash IS NOT NULL AND NOT (NEW.software_hash IS OLD.software_hash)
        BEGIN
            SELECT RAISE(ABORT, 'Sealed software hash is immutable');
        END;
        """)
        conn.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS election_public_key_hash_immutable
        BEFORE UPDATE OF public_key_fingerprint ON elections
        WHEN OLD.public_key_fingerprint IS NOT NULL AND NOT (NEW.public_key_fingerprint IS OLD.public_key_fingerprint)
        BEGIN
            SELECT RAISE(ABORT, 'Sealed public key fingerprint is immutable');
        END;
        """)
        conn.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS election_zero_hash_immutable
        BEFORE UPDATE OF zero_snapshot_hash ON elections
        WHEN OLD.zero_snapshot_hash IS NOT NULL AND NOT (NEW.zero_snapshot_hash IS OLD.zero_snapshot_hash)
        BEGIN
            SELECT RAISE(ABORT, 'Zero snapshot hash is immutable');
        END;
        """)
        conn.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS election_final_tally_immutable
        BEFORE UPDATE OF final_tally_json ON elections
        WHEN OLD.final_tally_json IS NOT NULL AND NOT (NEW.final_tally_json IS OLD.final_tally_json)
        BEGIN
            SELECT RAISE(ABORT, 'Final tally is immutable');
        END;
        """)
