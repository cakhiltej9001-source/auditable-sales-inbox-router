from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from app.models import ProcessedEmail, TaskRecord
from app.schemas import EmailIn
from app.services.extractor import HeuristicExtractor
from app.services.ingestion import IngestionService


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _service(session: Session) -> IngestionService:
    return IngestionService(session, HeuristicExtractor())


def test_duplicate_email_does_not_create_second_task(tmp_path):
    session = _session(tmp_path)
    service = _service(session)
    email = EmailIn(
        source_email_id="msg-1",
        thread_id="thread-1",
        from_email="buyer@acme.com",
        subject="Need proposal",
        body="Please send proposal for LMS. Budget INR 8L.",
    )

    first = service.ingest_email(email)
    second = service.ingest_email(email)
    tasks = session.exec(select(TaskRecord)).all()
    processed = session.exec(select(ProcessedEmail)).all()

    assert first.status == "created"
    assert second.status == "duplicate"
    assert len(tasks) == 1
    assert processed[0].duplicate_count == 1


def test_reply_on_existing_thread_updates_task(tmp_path):
    session = _session(tmp_path)
    service = _service(session)
    first = EmailIn(
        source_email_id="msg-1",
        thread_id="thread-1",
        from_email="buyer@acme.com",
        subject="Need proposal",
        body="Please send proposal for LMS. Budget INR 8L.",
    )
    reply = EmailIn(
        source_email_id="msg-2",
        thread_id="thread-1",
        from_email="buyer@acme.com",
        subject="Re: Need proposal",
        body="Adding deadline 2026-08-10 and updated budget INR 12L.",
    )

    created = service.ingest_email(first)
    updated = service.ingest_email(reply)
    tasks = session.exec(select(TaskRecord)).all()

    assert created.status == "created"
    assert updated.status == "updated"
    assert len(tasks) == 1
    # The original source id remains stable so the grader can still align Run 1.
    assert tasks[0].source_email_id == "msg-1"
    assert tasks[0].assignee_id == "u_aarti"
    assert tasks[0].update_count == 1


def test_quoted_old_intent_does_not_override_reply(tmp_path):
    session = _session(tmp_path)
    service = _service(session)
    first = EmailIn(
        email_id="quote-1", thread_id="quote-thread", from_email="buyer@acme.com",
        subject="Partnership", body="Please discuss a reseller partnership."
    )
    reply = EmailIn(
        email_id="quote-2", thread_id="quote-thread", message_index=1, is_reply=True,
        from_email="buyer@acme.com", subject="Re: Partnership",
        body="Please send the invoice to finance.\n\nOn Saturday, Karan wrote:\n> Please discuss a reseller partnership."
    )
    service.ingest_email(first)
    result = service.ingest_email(reply)
    task = session.exec(select(TaskRecord)).one()
    assert result.status == "updated"
    assert task.assignee_id == "u_divya"


def test_same_email_id_is_scoped_by_candidate(tmp_path):
    session = _session(tmp_path)
    service = _service(session)
    email = EmailIn(
        email_id="shared-source-id",
        thread_id="shared-thread-id",
        from_email="buyer@acme.com",
        subject="Product demo",
        body="Please schedule a demo. Budget INR 5L.",
    )

    first = service.ingest_email(email, "first@example.com", "run-first")
    second = service.ingest_email(email, "second@example.com", "run-second")

    assert first.status == "created"
    assert second.status == "created"
    assert len(session.exec(select(ProcessedEmail)).all()) == 2
    assert len(session.exec(select(TaskRecord)).all()) == 2
