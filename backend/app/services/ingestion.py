import json
from datetime import datetime

from sqlmodel import Session, select

from app.models import ProcessedEmail, ProcessingStatus, SkippedEmail, TaskRecord, utc_now
from app.schemas import EmailIn, IngestItemResult
from app.services.extractor import Extractor
from app.services.preprocess import normalize_email, obvious_skip_type
from app.services.routing import route_extraction
from app.services.task_api import TaskApiClient


class IngestionService:
    def __init__(self, session: Session, extractor: Extractor, task_api: TaskApiClient):
        self.session = session
        self.extractor = extractor
        self.task_api = task_api

    def ingest_email(self, email: EmailIn) -> IngestItemResult:
        email = normalize_email(email)
        existing_email = self.session.exec(
            select(ProcessedEmail).where(ProcessedEmail.source_email_id == email.source_email_id)
        ).first()
        if existing_email:
            existing_email.duplicate_count += 1
            existing_email.last_duplicate_at = utc_now()
            self.session.add(existing_email)
            self.session.commit()
            return IngestItemResult(
                source_email_id=email.source_email_id,
                thread_id=email.thread_id,
                status="duplicate",
                task_id=self._task_id(existing_email.task_record_id),
                reason="Email was already processed; replay ignored.",
            )

        skip = obvious_skip_type(email.subject, email.body)
        if skip:
            skip_type, reason = skip
            return self._persist_skip(email, skip_type, reason, extraction_json=None, routing_json=None)

        extraction = self.extractor.extract(email)
        routing = route_extraction(extraction)

        if routing.should_skip:
            return self._persist_skip(
                email,
                routing.skip_type or "not_actionable",
                routing.reason,
                extraction.model_dump_json(),
                routing.model_dump_json(),
            )

        payload = _build_task_payload(email, extraction, routing)
        existing_thread_task = self.session.exec(
            select(TaskRecord).where(TaskRecord.thread_id == email.thread_id).order_by(TaskRecord.updated_at.desc())
        ).first()

        if existing_thread_task:
            external_task_id = self.task_api.update_task(existing_thread_task.external_task_id, payload)
            existing_thread_task.source_email_id = email.source_email_id
            existing_thread_task.assignee_id = routing.assignee_id or existing_thread_task.assignee_id
            existing_thread_task.category = extraction.category
            existing_thread_task.priority = routing.priority
            existing_thread_task.title = payload["title"]
            existing_thread_task.company = extraction.company
            existing_thread_task.deal_value_inr = extraction.deal_value_inr
            existing_thread_task.due_at = extraction.due_at
            existing_thread_task.confidence = extraction.confidence
            existing_thread_task.reasoning = routing.reason
            existing_thread_task.task_payload_json = json.dumps(payload, default=str)
            existing_thread_task.supporting_data_json = json.dumps(_supporting_data(email, extraction, routing), default=str)
            existing_thread_task.updated_at = utc_now()
            self.session.add(existing_thread_task)
            self._persist_processed(email, ProcessingStatus.updated, existing_thread_task.id, routing.reason, extraction, routing)
            self.session.commit()
            return IngestItemResult(
                source_email_id=email.source_email_id,
                thread_id=email.thread_id,
                status="updated",
                task_id=external_task_id,
                assignee_id=routing.assignee_id,
                priority=routing.priority,
                reason="Existing thread task updated.",
            )

        reconciled_task_id = self.task_api.find_existing_task(email.source_email_id, email.thread_id)
        external_task_id = reconciled_task_id or self.task_api.create_task(payload)
        task = TaskRecord(
            external_task_id=external_task_id,
            thread_id=email.thread_id,
            source_email_id=email.source_email_id,
            assignee_id=routing.assignee_id or "u_triage",
            category=extraction.category,
            priority=routing.priority,
            title=payload["title"],
            company=extraction.company,
            deal_value_inr=extraction.deal_value_inr,
            due_at=extraction.due_at,
            confidence=extraction.confidence,
            reasoning=routing.reason,
            task_payload_json=json.dumps(payload, default=str),
            supporting_data_json=json.dumps(_supporting_data(email, extraction, routing), default=str),
        )
        self.session.add(task)
        self.session.flush()
        self._persist_processed(email, ProcessingStatus.created, task.id, routing.reason, extraction, routing)
        self.session.commit()
        return IngestItemResult(
            source_email_id=email.source_email_id,
            thread_id=email.thread_id,
            status="created",
            task_id=external_task_id,
            assignee_id=routing.assignee_id,
            priority=routing.priority,
            reason=routing.reason,
        )

    def _persist_skip(
        self,
        email: EmailIn,
        skip_type: str,
        reason: str,
        extraction_json: str | None,
        routing_json: str | None,
    ) -> IngestItemResult:
        skipped = SkippedEmail(
            source_email_id=email.source_email_id,
            thread_id=email.thread_id,
            skip_type=skip_type,
            reason=reason,
            subject=email.subject,
            from_email=str(email.from_email),
            received_at=email.received_at,
        )
        self.session.add(skipped)
        self.session.add(
            ProcessedEmail(
                source_email_id=email.source_email_id,
                thread_id=email.thread_id,
                status=ProcessingStatus.skipped,
                reason=reason,
                received_at=email.received_at,
                raw_email_json=email.model_dump_json(),
                extraction_json=extraction_json,
                routing_json=routing_json,
            )
        )
        self.session.commit()
        return IngestItemResult(
            source_email_id=email.source_email_id,
            thread_id=email.thread_id,
            status="skipped",
            reason=reason,
        )

    def _persist_processed(
        self,
        email: EmailIn,
        status: ProcessingStatus,
        task_record_id: int | None,
        reason: str,
        extraction,
        routing,
    ) -> None:
        self.session.add(
            ProcessedEmail(
                source_email_id=email.source_email_id,
                thread_id=email.thread_id,
                status=status,
                task_record_id=task_record_id,
                reason=reason,
                received_at=email.received_at,
                raw_email_json=email.model_dump_json(),
                extraction_json=extraction.model_dump_json(),
                routing_json=routing.model_dump_json(),
            )
        )

    def _task_id(self, task_record_id: int | None) -> str | None:
        if task_record_id is None:
            return None
        task = self.session.get(TaskRecord, task_record_id)
        return task.external_task_id if task else None


def _build_task_payload(email, extraction, routing) -> dict:
    title = f"{extraction.category.upper()}: {email.subject[:90]}"
    return {
        "title": title,
        "description": extraction.summary,
        "source_email_id": email.source_email_id,
        "thread_id": email.thread_id,
        "assignee_id": routing.assignee_id,
        "priority": routing.priority,
        "company": extraction.company,
        "deal_value_inr": extraction.deal_value_inr,
        "due_at": extraction.due_at.isoformat() if isinstance(extraction.due_at, datetime) else None,
        "reason": routing.reason,
        "confidence": extraction.confidence,
    }


def _supporting_data(email, extraction, routing) -> dict:
    return {
        "source_email_id": email.source_email_id,
        "thread_id": email.thread_id,
        "subject": email.subject,
        "category": extraction.category,
        "signals": extraction.signals,
        "rule_id": routing.rule_id,
        "reason": routing.reason,
    }
