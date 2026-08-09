from sqlmodel import Session, select

from app.core.identity import normalize_candidate_id
from app.models import IngestRun, ProcessedEmail, SkippedEmail, TaskRecord


def purge_candidate_data(session: Session, candidate_id: str) -> dict[str, int]:
    """Delete one canonical candidate's operational data in dependency order."""
    candidate = normalize_candidate_id(candidate_id)
    model_names = [
        ("processed_emails", ProcessedEmail),
        ("skipped_emails", SkippedEmail),
        ("ingest_runs", IngestRun),
        ("tasks", TaskRecord),
    ]
    counts: dict[str, int] = {}
    for label, model in model_names:
        rows = session.exec(select(model).where(model.candidate_id == candidate)).all()
        counts[label] = len(rows)
        for row in rows:
            session.delete(row)
    session.commit()
    return counts
