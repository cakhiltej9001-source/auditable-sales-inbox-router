from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProcessingStatus(str, Enum):
    created = "created"
    updated = "updated"
    duplicate = "duplicate"
    skipped = "skipped"
    error = "error"


class IngestRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, unique=True)
    candidate_id: str = Field(index=True)
    processed: int
    tasks_created: int
    tasks_updated: int
    skipped: int
    duplicate_count: int
    error_count: int
    created_at: datetime = Field(default_factory=utc_now, index=True)


class TaskRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    external_task_id: str = Field(index=True, unique=True)
    candidate_id: str = Field(default="cakhiltej9001@gmail.com", index=True)
    thread_id: str = Field(index=True)
    source_email_id: str = Field(index=True)
    assignee_id: str = Field(index=True)
    category: str = Field(index=True)
    priority: str = Field(index=True)
    title: str
    description: Optional[str] = None
    company: Optional[str] = Field(default=None, index=True)
    deal_value_inr: Optional[int] = None
    due_date: Optional[date] = None
    due_at: Optional[datetime] = None
    status: str = Field(default="open", index=True)
    confidence: float = 0
    reasoning: str = ""
    update_count: int = 0
    task_payload_json: str = "{}"
    supporting_data_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class ProcessedEmail(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    candidate_id: str = Field(default="cakhiltej9001@gmail.com", index=True)
    run_id: str = Field(default="legacy", index=True)
    source_email_id: str = Field(index=True, unique=True)
    thread_id: str = Field(index=True)
    message_index: int = 0
    status: ProcessingStatus = Field(index=True)
    category: str = Field(default="not_actionable", index=True)
    confidence: float = 0
    spurious_flagged: bool = Field(default=False, index=True)
    task_record_id: Optional[int] = Field(default=None, foreign_key="taskrecord.id")
    reason: str
    received_at: Optional[datetime] = Field(default=None, index=True)
    processed_at: datetime = Field(default_factory=utc_now, index=True)
    duplicate_count: int = 0
    last_duplicate_at: Optional[datetime] = None
    raw_email_json: str
    extraction_json: Optional[str] = None
    routing_json: Optional[str] = None


class SkippedEmail(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    candidate_id: str = Field(default="cakhiltej9001@gmail.com", index=True)
    run_id: str = Field(default="legacy", index=True)
    source_email_id: str = Field(index=True, unique=True)
    thread_id: str = Field(index=True)
    skip_type: str = Field(index=True)
    reason: str
    subject: str
    from_email: str
    received_at: Optional[datetime] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
