from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import get_session
from app.models import ProcessedEmail, ProcessingStatus, SkippedEmail, TaskRecord
from app.schemas import ChatRequest, ChatResponse, IngestRequest, IngestResponse, SkippedOut, StatsOut, TaskOut
from app.services.chat import answer_question
from app.services.extractor import get_extractor
from app.services.ingestion import IngestionService
from app.services.task_api import TaskApiClient

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest, session: Session = Depends(get_session)) -> IngestResponse:
    settings = get_settings()
    extractor = get_extractor(settings)
    task_api = TaskApiClient(settings)
    service = IngestionService(session, extractor, task_api)
    results = [service.ingest_email(email) for email in payload.emails]
    return IngestResponse(candidate_id=payload.candidate_id, processed=len(results), results=results)


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(session: Session = Depends(get_session)) -> list[TaskOut]:
    tasks = session.exec(select(TaskRecord).order_by(TaskRecord.updated_at.desc())).all()
    return [
        TaskOut(
            external_task_id=task.external_task_id,
            thread_id=task.thread_id,
            source_email_id=task.source_email_id,
            assignee_id=task.assignee_id,
            category=task.category,
            priority=task.priority,
            title=task.title,
            company=task.company,
            deal_value_inr=task.deal_value_inr,
            due_at=task.due_at,
            confidence=task.confidence,
            reasoning=task.reasoning,
            updated_at=task.updated_at,
        )
        for task in tasks
    ]


@router.get("/skipped", response_model=list[SkippedOut])
def list_skipped(session: Session = Depends(get_session)) -> list[SkippedOut]:
    rows = session.exec(select(SkippedEmail).order_by(SkippedEmail.created_at.desc())).all()
    return [
        SkippedOut(
            source_email_id=row.source_email_id,
            thread_id=row.thread_id,
            skip_type=row.skip_type,
            reason=row.reason,
            subject=row.subject,
            from_email=row.from_email,
            received_at=row.received_at,
        )
        for row in rows
    ]


@router.get("/stats", response_model=StatsOut)
def stats(session: Session = Depends(get_session)) -> StatsOut:
    processed = session.exec(select(ProcessedEmail)).all()
    tasks = session.exec(select(TaskRecord)).all()
    skipped = session.exec(select(SkippedEmail)).all()
    return StatsOut(
        total_emails=len(processed),
        created_tasks=sum(1 for item in processed if item.status == ProcessingStatus.created),
        updated_tasks=sum(1 for item in processed if item.status == ProcessingStatus.updated),
        duplicates=sum(item.duplicate_count for item in processed),
        skipped=len(skipped),
        by_assignee=_counts([task.assignee_id for task in tasks]),
        by_category=_counts([task.category for task in tasks]),
        by_priority=_counts([task.priority for task in tasks]),
        total_pipeline_inr=sum(task.deal_value_inr or 0 for task in tasks),
    )


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, session: Session = Depends(get_session)) -> ChatResponse:
    answer, supporting_data, query_intent = answer_question(session, payload.question)
    return ChatResponse(answer=answer, supporting_data=supporting_data, query_intent=query_intent)


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts
