from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings


def build_engine(url: str | None = None):
    database_url = url or get_settings().database_url
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, echo=False, connect_args=connect_args)


engine = build_engine()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_existing_database()


def _migrate_existing_database() -> None:
    """Add challenge-contract columns without destroying an existing Render database."""
    additions = {
        "taskrecord": {
            "candidate_id": "VARCHAR NOT NULL DEFAULT 'cakhiltej9001@gmail.com'",
            "description": "VARCHAR",
            "due_date": "DATE",
            "update_count": "INTEGER NOT NULL DEFAULT 0",
        },
        "processedemail": {
            "candidate_id": "VARCHAR NOT NULL DEFAULT 'cakhiltej9001@gmail.com'",
            "run_id": "VARCHAR NOT NULL DEFAULT 'legacy'",
            "message_index": "INTEGER NOT NULL DEFAULT 0",
            "category": "VARCHAR NOT NULL DEFAULT 'not_actionable'",
            "confidence": "FLOAT NOT NULL DEFAULT 0",
            "spurious_flagged": "BOOLEAN NOT NULL DEFAULT FALSE",
            "spurious_review_reason": "VARCHAR",
            "spurious_reviewed_at": "TIMESTAMP WITH TIME ZONE",
        },
        "skippedemail": {
            "candidate_id": "VARCHAR NOT NULL DEFAULT 'cakhiltej9001@gmail.com'",
            "run_id": "VARCHAR NOT NULL DEFAULT 'legacy'",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in additions.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {definition}'))
        _normalize_legacy_rows(connection)
        _configure_candidate_scoped_uniqueness(connection)


def _normalize_legacy_rows(connection) -> None:
    """Translate values written by the pre-contract release into exact grader enums."""
    connection.execute(text("""
        UPDATE taskrecord
        SET category = CASE
            WHEN category IN ('rfp', 'government') THEN 'enterprise_rfp'
            WHEN category = 'smb' THEN 'smb_enquiry'
            WHEN category IN ('enterprise_rfp', 'smb_enquiry', 'marketing', 'alliances', 'finance', 'triage') THEN category
            ELSE 'triage'
        END
    """))
    connection.execute(text("""
        UPDATE taskrecord
        SET priority = CASE
            WHEN priority IN ('high', 'medium', 'low') THEN priority
            ELSE 'low'
        END
    """))
    connection.execute(text("""
        UPDATE processedemail
        SET category = CASE
            WHEN category IN ('rfp', 'government') THEN 'enterprise_rfp'
            WHEN category = 'smb' THEN 'smb_enquiry'
            WHEN category = 'unknown' THEN 'triage'
            ELSE category
        END
    """))


def _configure_candidate_scoped_uniqueness(connection) -> None:
    """Replace the first release's global email-id constraint on PostgreSQL."""
    if engine.dialect.name != "postgresql":
        return
    connection.execute(text(
        "ALTER TABLE processedemail DROP CONSTRAINT IF EXISTS processedemail_source_email_id_key"
    ))
    connection.execute(text(
        "ALTER TABLE skippedemail DROP CONSTRAINT IF EXISTS skippedemail_source_email_id_key"
    ))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_processed_candidate_source "
        "ON processedemail (candidate_id, source_email_id)"
    ))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_skipped_candidate_source "
        "ON skippedemail (candidate_id, source_email_id)"
    ))


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
