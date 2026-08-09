import uuid

from sqlmodel import Session, select

from app.models import TaskRecord
from app.schemas import TaskCreate


class TaskWriteService:
    """Single persistence path shared by the public Task API and ingestion."""

    def __init__(self, session: Session):
        self.session = session

    def find_by_source(self, candidate_id: str, source_email_id: str) -> TaskRecord | None:
        return self.session.exec(
            select(TaskRecord).where(
                TaskRecord.candidate_id == candidate_id.lower(),
                TaskRecord.source_email_id == source_email_id,
            )
        ).first()

    def create(
        self,
        payload: TaskCreate,
        *,
        external_task_id: str | None = None,
        reasoning: str = "Created through the Task API.",
        supporting_data_json: str = "{}",
    ) -> tuple[TaskRecord, bool]:
        candidate_id = str(payload.candidate_id).lower()
        existing = self.find_by_source(candidate_id, payload.source_email_id)
        if existing:
            return existing, False

        task = TaskRecord(
            external_task_id=external_task_id or f"tsk_{uuid.uuid4().hex[:12]}",
            candidate_id=candidate_id,
            source_email_id=payload.source_email_id,
            thread_id=payload.thread_id,
            title=payload.title,
            description=payload.description,
            assignee_id=payload.assignee_id,
            category=payload.category,
            priority=payload.priority,
            due_date=payload.due_date,
            deal_value_inr=payload.deal_value_inr,
            company=payload.company_name,
            confidence=payload.confidence,
            reasoning=reasoning,
            task_payload_json=payload.model_dump_json(),
            supporting_data_json=supporting_data_json,
        )
        self.session.add(task)
        self.session.flush()
        return task, True
