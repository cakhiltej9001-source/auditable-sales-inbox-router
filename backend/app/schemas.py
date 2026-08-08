from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


EmailCategory = Literal[
    "rfp",
    "finance",
    "marketing",
    "alliances",
    "smb",
    "government",
    "newsletter",
    "out_of_office",
    "vendor_spam",
    "unknown",
]


class EmailIn(BaseModel):
    source_email_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    from_email: EmailStr
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    received_at: datetime | None = None


class IngestRequest(BaseModel):
    candidate_id: str = Field(min_length=1)
    emails: list[EmailIn] = Field(min_length=1, max_length=500)


class ExtractionResult(BaseModel):
    category: EmailCategory = "unknown"
    is_actionable: bool = False
    company: str | None = None
    deal_value_inr: int | None = Field(default=None, ge=0)
    due_at: datetime | None = None
    summary: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list)


class RoutingDecision(BaseModel):
    should_skip: bool
    skip_type: str | None = None
    assignee_id: str | None = None
    priority: Literal["normal", "medium", "high"] = "normal"
    reason: str
    rule_id: str


class IngestItemResult(BaseModel):
    source_email_id: str
    thread_id: str
    status: Literal["created", "updated", "duplicate", "skipped", "error"]
    task_id: str | None = None
    assignee_id: str | None = None
    priority: str | None = None
    reason: str


class IngestResponse(BaseModel):
    candidate_id: str
    processed: int
    results: list[IngestItemResult]


class TaskOut(BaseModel):
    external_task_id: str
    thread_id: str
    source_email_id: str
    assignee_id: str
    category: str
    priority: str
    title: str
    company: str | None
    deal_value_inr: int | None
    due_at: datetime | None
    confidence: float
    reasoning: str
    updated_at: datetime


class SkippedOut(BaseModel):
    source_email_id: str
    thread_id: str
    skip_type: str
    reason: str
    subject: str
    from_email: str
    received_at: datetime | None


class StatsOut(BaseModel):
    total_emails: int
    created_tasks: int
    updated_tasks: int
    duplicates: int
    skipped: int
    by_assignee: dict[str, int]
    by_category: dict[str, int]
    by_priority: dict[str, int]
    total_pipeline_inr: int


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class ChatResponse(BaseModel):
    answer: str
    supporting_data: dict
    query_intent: str

