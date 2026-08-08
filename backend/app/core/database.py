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


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
