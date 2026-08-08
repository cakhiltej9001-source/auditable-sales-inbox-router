import json
import uuid
from collections import Counter

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import get_session
from app.models import IngestRun, ProcessedEmail, ProcessingStatus, SkippedEmail, TaskRecord, utc_now
from app.schemas import (
    ChatRequest,
    ChatResponse,
    IngestRequest,
    IngestResponse,
    SkippedOut,
    TEAM_ROSTER,
    TaskApiOut,
    TaskCreate,
    TaskCreated,
    TaskOut,
    TaskPatch,
)
from app.services.chat import answer_question
from app.services.extractor import get_extractor
from app.services.ingestion import IngestionService

router = APIRouter()

ENUMS = {
    "assignee_id": ["u_aarti", "u_rohit", "u_meera", "u_karan", "u_divya", "u_triage"],
    "category": ["enterprise_rfp", "smb_enquiry", "marketing", "alliances", "finance", "triage"],
    "priority": ["high", "medium", "low"],
}


@router.get("/")
def root() -> dict[str, str]:
    return {"service": "Sales Inbox Task Router", "status": "ok", "docs": "/docs"}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/tasks", response_model=TaskCreated, status_code=status.HTTP_201_CREATED)
def create_task(payload: dict = Body(...), session: Session = Depends(get_session)):
    task_in = _validate_task_payload(TaskCreate, payload)
    if isinstance(task_in, JSONResponse):
        return task_in
    candidate_id = str(task_in.candidate_id).lower()
    existing = session.exec(select(TaskRecord).where(
        TaskRecord.candidate_id == candidate_id,
        TaskRecord.source_email_id == task_in.source_email_id,
    )).first()
    if existing:
        return TaskCreated(task_id=existing.external_task_id, candidate_id=existing.candidate_id, source_email_id=existing.source_email_id, created_at=existing.created_at)
    task = TaskRecord(
        external_task_id=f"tsk_{uuid.uuid4().hex[:12]}",
        candidate_id=candidate_id,
        source_email_id=task_in.source_email_id,
        thread_id=task_in.thread_id,
        title=task_in.title,
        description=task_in.description,
        assignee_id=task_in.assignee_id,
        category=task_in.category,
        priority=task_in.priority,
        due_date=task_in.due_date,
        deal_value_inr=task_in.deal_value_inr,
        company=task_in.company_name,
        confidence=task_in.confidence,
        reasoning="Created through the Task API.",
        task_payload_json=task_in.model_dump_json(),
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return TaskCreated(task_id=task.external_task_id, candidate_id=task.candidate_id, source_email_id=task.source_email_id, created_at=task.created_at)


@router.patch("/tasks/{task_id}", response_model=TaskApiOut)
def patch_task(task_id: str, payload: dict = Body(...), session: Session = Depends(get_session)):
    patch = _validate_task_payload(TaskPatch, payload)
    if isinstance(patch, JSONResponse):
        return patch
    task = _task_or_404(session, task_id)
    field_map = {"company_name": "company"}
    for field in patch.model_fields_set:
        setattr(task, field_map.get(field, field), getattr(patch, field))
    task.updated_at = utc_now()
    task.update_count += 1
    session.add(task)
    session.commit()
    session.refresh(task)
    return _task_api_out(task)


@router.get("/tasks", response_model=list[TaskApiOut])
def list_task_api(
    candidate_id: str = Query(...),
    thread_id: str | None = None,
    source_email_id: str | None = None,
    assignee_id: str | None = None,
    session: Session = Depends(get_session),
):
    statement = select(TaskRecord).where(TaskRecord.candidate_id == candidate_id.lower())
    if thread_id:
        statement = statement.where(TaskRecord.thread_id == thread_id)
    if source_email_id:
        statement = statement.where(TaskRecord.source_email_id == source_email_id)
    if assignee_id:
        if assignee_id not in ENUMS["assignee_id"]:
            return _enum_error("assignee_id", assignee_id)
        statement = statement.where(TaskRecord.assignee_id == assignee_id)
    return [_task_api_out(task) for task in session.exec(statement.order_by(TaskRecord.updated_at.desc())).all()]


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, session: Session = Depends(get_session)) -> Response:
    task = _task_or_404(session, task_id)
    audits = session.exec(select(ProcessedEmail).where(ProcessedEmail.task_record_id == task.id)).all()
    for audit in audits:
        audit.task_record_id = None
        session.add(audit)
    session.delete(task)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users")
def users() -> dict[str, list[dict]]:
    return {"team": TEAM_ROSTER}


@router.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest, session: Session = Depends(get_session)) -> IngestResponse:
    settings = get_settings()
    service = IngestionService(session, get_extractor(settings))
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    results = []
    errors = []
    for email in payload.emails:
        try:
            results.append(service.ingest_email(email, str(payload.candidate_id).lower(), run_id))
        except Exception as exc:
            session.rollback()
            errors.append({"email_id": email.email_id, "error": type(exc).__name__, "message": str(exc)[:300]})
    response = IngestResponse(
        processed=len(payload.emails),
        tasks_created=sum(item.status == "created" for item in results),
        tasks_updated=sum(item.status == "updated" for item in results),
        skipped=sum(item.status in {"skipped", "duplicate"} for item in results),
        errors=errors,
    )
    session.add(IngestRun(
        run_id=run_id,
        candidate_id=str(payload.candidate_id).lower(),
        processed=response.processed,
        tasks_created=response.tasks_created,
        tasks_updated=response.tasks_updated,
        skipped=response.skipped,
        duplicate_count=sum(item.status == "duplicate" for item in results),
        error_count=len(errors),
    ))
    session.commit()
    return response


@router.get("/api/tasks", response_model=list[TaskOut])
def api_tasks(candidate_id: str | None = None, session: Session = Depends(get_session)) -> list[TaskOut]:
    candidate = (candidate_id or get_settings().candidate_id).lower()
    tasks = session.exec(select(TaskRecord).where(TaskRecord.candidate_id == candidate).order_by(TaskRecord.updated_at.desc())).all()
    return [_task_out(task) for task in tasks]


@router.get("/api/stats")
def api_stats(candidate_id: str | None = None, session: Session = Depends(get_session)) -> dict:
    candidate = (candidate_id or get_settings().candidate_id).lower()
    processed = session.exec(select(ProcessedEmail).where(ProcessedEmail.candidate_id == candidate)).all()
    tasks = session.exec(select(TaskRecord).where(TaskRecord.candidate_id == candidate)).all()
    runs = session.exec(select(IngestRun).where(IngestRun.candidate_id == candidate).order_by(IngestRun.created_at.desc())).all()
    result = {
        "processed": len(processed),
        "created": sum(row.status == ProcessingStatus.created for row in processed),
        "updated": sum(row.status == ProcessingStatus.updated for row in processed),
        "skipped": sum(row.status == ProcessingStatus.skipped for row in processed),
        "duplicates": sum(row.duplicate_count for row in processed),
        "spurious_flagged": sum(row.spurious_flagged for row in processed),
        "by_category": dict(Counter(row.category for row in processed)),
        "spurious_by_category": dict(Counter(row.category for row in processed if row.spurious_flagged)),
        "by_run": {
            run.run_id: {
                "processed": run.processed,
                "created": run.tasks_created,
                "updated": run.tasks_updated,
                "skipped": run.skipped,
                "duplicates": run.duplicate_count,
                "errors": run.error_count,
            }
            for run in runs
        },
        "by_assignee": dict(Counter(task.assignee_id for task in tasks)),
        "by_priority": dict(Counter(task.priority for task in tasks)),
        "total_pipeline_inr": sum(task.deal_value_inr or 0 for task in tasks),
    }
    return result


@router.post("/api/chat", response_model=ChatResponse)
def api_chat(payload: ChatRequest, session: Session = Depends(get_session)) -> ChatResponse:
    answer, supporting_data, intent = answer_question(session, str(payload.candidate_id).lower(), payload.query, payload.email_ids)
    return ChatResponse(answer=answer, supporting_data=supporting_data, query_intent=intent)


# Compatibility aliases for the first deployed UI.
@router.get("/stats")
def legacy_stats(candidate_id: str | None = None, session: Session = Depends(get_session)) -> dict:
    return api_stats(candidate_id, session)


@router.get("/skipped", response_model=list[SkippedOut])
def list_skipped(candidate_id: str | None = None, session: Session = Depends(get_session)) -> list[SkippedOut]:
    candidate = (candidate_id or get_settings().candidate_id).lower()
    rows = session.exec(select(SkippedEmail).where(SkippedEmail.candidate_id == candidate).order_by(SkippedEmail.created_at.desc())).all()
    return [SkippedOut(source_email_id=r.source_email_id, thread_id=r.thread_id, skip_type=r.skip_type, reason=r.reason, subject=r.subject, from_email=r.from_email, received_at=r.received_at) for r in rows]


def _validate_task_payload(model, payload):
    for field, allowed in ENUMS.items():
        if field in payload and payload[field] not in allowed:
            return _enum_error(field, payload[field])
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from exc


def _enum_error(field: str, received):
    return JSONResponse(status_code=400, content={"error": "invalid_enum_value", "field": field, "received": received, "allowed": ENUMS[field]})


def _task_or_404(session: Session, task_id: str) -> TaskRecord:
    task = session.exec(select(TaskRecord).where(TaskRecord.external_task_id == task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _task_api_out(task: TaskRecord) -> TaskApiOut:
    return TaskApiOut(
        task_id=task.external_task_id,
        candidate_id=task.candidate_id,
        source_email_id=task.source_email_id,
        thread_id=task.thread_id,
        title=task.title,
        description=task.description,
        assignee_id=task.assignee_id,
        category=_normalized_category(task.category),
        priority=_normalized_priority(task.priority),
        due_date=task.due_date,
        deal_value_inr=task.deal_value_inr,
        company_name=task.company,
        confidence=task.confidence,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _task_out(task: TaskRecord) -> TaskOut:
    return TaskOut(
        task_id=task.external_task_id,
        candidate_id=task.candidate_id,
        thread_id=task.thread_id,
        source_email_id=task.source_email_id,
        assignee_id=task.assignee_id,
        category=_normalized_category(task.category),
        priority=_normalized_priority(task.priority),
        title=task.title,
        description=task.description,
        company_name=task.company,
        deal_value_inr=task.deal_value_inr,
        due_date=task.due_date,
        confidence=task.confidence,
        reasoning=task.reasoning,
        status=task.status,
        update_count=task.update_count,
        updated_at=task.updated_at,
    )


def _normalized_category(value: str) -> str:
    legacy = {"rfp": "enterprise_rfp", "government": "enterprise_rfp", "smb": "smb_enquiry"}
    normalized = legacy.get(value, value)
    return normalized if normalized in ENUMS["category"] else "triage"


def _normalized_priority(value: str) -> str:
    return value if value in ENUMS["priority"] else "low"
