from datetime import date, datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field


AssigneeId = Literal["u_aarti", "u_rohit", "u_meera", "u_karan", "u_divya", "u_triage"]
TaskCategory = Literal["enterprise_rfp", "smb_enquiry", "marketing", "alliances", "finance", "triage"]
TaskPriority = Literal["high", "medium", "low"]
ExtractionCategory = Literal[
    "enterprise_rfp",
    "smb_enquiry",
    "marketing",
    "alliances",
    "finance",
    "triage",
    "newsletter",
    "out_of_office",
    "vendor_spam",
    "not_actionable",
]


class EmailIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email_id: str = Field(validation_alias=AliasChoices("email_id", "source_email_id"), min_length=1)
    thread_id: str = Field(min_length=1)
    message_index: int = Field(default=0, ge=0)
    from_name: str | None = None
    from_email: EmailStr
    to: str | list[str] | None = None
    cc: list[str] = Field(default_factory=list)
    subject: str = ""
    body: str = ""
    received_at: datetime | None = None
    attachments: list[str] = Field(default_factory=list)
    is_reply: bool = False

    @property
    def source_email_id(self) -> str:
        """Compatibility name used internally by the original implementation."""
        return self.email_id


class IngestRequest(BaseModel):
    candidate_id: EmailStr
    emails: list[EmailIn] = Field(min_length=1, max_length=100)


class ExtractionResult(BaseModel):
    category: ExtractionCategory = "not_actionable"
    is_actionable: bool = False
    company_name: str | None = Field(default=None, validation_alias=AliasChoices("company_name", "company"))
    deal_value_inr: int | None = Field(default=None, ge=0)
    due_date: date | None = Field(default=None, validation_alias=AliasChoices("due_date", "due_at"))
    summary: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list)

    @property
    def company(self) -> str | None:
        return self.company_name

    @property
    def due_at(self) -> datetime | None:
        return datetime.combine(self.due_date, datetime.min.time()) if self.due_date else None


class RoutingDecision(BaseModel):
    should_skip: bool
    skip_type: str | None = None
    assignee_id: AssigneeId | None = None
    category: TaskCategory | None = None
    priority: TaskPriority = "low"
    reason: str
    rule_id: str


class IngestItemResult(BaseModel):
    source_email_id: str
    thread_id: str
    status: Literal["created", "updated", "duplicate", "skipped", "error"]
    task_id: str | None = None
    assignee_id: AssigneeId | None = None
    priority: TaskPriority | None = None
    reason: str


class IngestResponse(BaseModel):
    processed: int
    tasks_created: int
    tasks_updated: int
    skipped: int
    errors: list[dict]


class TaskCreate(BaseModel):
    candidate_id: EmailStr
    source_email_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    assignee_id: AssigneeId
    category: TaskCategory
    priority: TaskPriority
    due_date: date | None
    deal_value_inr: int | None = Field(ge=0)
    company_name: str | None
    confidence: float = Field(ge=0.0, le=1.0)


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee_id: AssigneeId | None = None
    category: TaskCategory | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None
    deal_value_inr: int | None = Field(default=None, ge=0)
    company_name: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class TaskCreated(BaseModel):
    task_id: str
    candidate_id: str
    source_email_id: str
    created_at: datetime


class TaskApiOut(TaskCreate):
    task_id: str
    created_at: datetime
    updated_at: datetime


class TaskOut(BaseModel):
    task_id: str
    candidate_id: str
    thread_id: str
    source_email_id: str
    assignee_id: AssigneeId
    category: TaskCategory
    priority: TaskPriority
    title: str
    description: str | None
    company_name: str | None
    deal_value_inr: int | None
    due_date: date | None
    confidence: float
    reasoning: str
    status: str
    update_count: int
    updated_at: datetime


class SkippedOut(BaseModel):
    source_email_id: str
    thread_id: str
    skip_type: str
    reason: str
    subject: str
    from_email: str
    received_at: datetime | None


class ChatRequest(BaseModel):
    candidate_id: EmailStr
    query: str = Field(validation_alias=AliasChoices("query", "question"), min_length=2, max_length=500)
    email_ids: list[str] | None = None


class ChatResponse(BaseModel):
    answer: str
    supporting_data: dict
    query_intent: str | None = None


TEAM_ROSTER = [
    {"user_id": "u_aarti", "name": "Aarti Menon", "department": "Sales — Enterprise", "scope": "RFPs, RFIs, tenders, and inbound deals above ₹10,00,000"},
    {"user_id": "u_rohit", "name": "Rohit Sharma", "department": "Sales — SMB", "scope": "Product enquiries, demo requests, deals at or below ₹10,00,000"},
    {"user_id": "u_meera", "name": "Meera Iyer", "department": "Marketing", "scope": "Webinars, sponsorships, content collaborations, PR and media"},
    {"user_id": "u_karan", "name": "Karan Doshi", "department": "Alliances", "scope": "Reseller, channel partner, and technology integration proposals"},
    {"user_id": "u_divya", "name": "Divya Rao", "department": "Finance", "scope": "Invoices, purchase orders, payments, GST and vendor billing"},
    {"user_id": "u_triage", "name": "Triage Queue", "department": "Operations", "scope": "Ambiguous items requiring human review"},
]
