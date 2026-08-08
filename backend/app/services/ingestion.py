import hashlib
import json

from sqlmodel import Session, select

from app.models import ProcessedEmail, ProcessingStatus, SkippedEmail, TaskRecord, utc_now
from app.schemas import EmailIn, IngestItemResult
from app.services.extractor import Extractor
from app.services.preprocess import normalize_email, obvious_skip_type
from app.services.routing import route_extraction


class IngestionService:
    def __init__(self, session: Session, extractor: Extractor):
        self.session = session
        self.extractor = extractor

    def ingest_email(
        self,
        email: EmailIn,
        candidate_id: str = "cakhiltej9001@gmail.com",
        run_id: str = "manual",
    ) -> IngestItemResult:
        candidate_id = candidate_id.lower()
        email = normalize_email(email)
        existing_email = self.session.exec(
            select(ProcessedEmail).where(
                ProcessedEmail.candidate_id == candidate_id,
                ProcessedEmail.source_email_id == email.email_id,
            )
        ).first()
        if existing_email:
            existing_email.duplicate_count += 1
            existing_email.last_duplicate_at = utc_now()
            self.session.add(existing_email)
            self.session.commit()
            return IngestItemResult(
                source_email_id=email.email_id,
                thread_id=email.thread_id,
                status="duplicate",
                task_id=self._task_id(existing_email.task_record_id),
                reason="Email was already processed; replay ignored without creating another task.",
            )

        skip = obvious_skip_type(email.subject, email.body)
        if skip:
            return self._persist_skip(email, candidate_id, run_id, skip[0], skip[1], None, None)

        extraction = self.extractor.extract(email)
        routing = route_extraction(extraction, email.received_at)
        if routing.should_skip:
            return self._persist_skip(
                email,
                candidate_id,
                run_id,
                routing.skip_type or "not_actionable",
                routing.reason,
                extraction.model_dump_json(),
                routing.model_dump_json(),
            )

        existing_thread_task = self.session.exec(
            select(TaskRecord).where(
                TaskRecord.candidate_id == candidate_id,
                TaskRecord.thread_id == email.thread_id,
            ).order_by(TaskRecord.updated_at.desc())
        ).first()
        payload = _build_task_payload(candidate_id, email, extraction, routing)

        if existing_thread_task:
            existing_thread_task.assignee_id = routing.assignee_id or existing_thread_task.assignee_id
            existing_thread_task.category = routing.category or existing_thread_task.category
            existing_thread_task.priority = routing.priority
            existing_thread_task.title = payload["title"]
            existing_thread_task.description = payload["description"]
            existing_thread_task.company = extraction.company_name
            existing_thread_task.deal_value_inr = extraction.deal_value_inr
            existing_thread_task.due_date = extraction.due_date
            existing_thread_task.confidence = extraction.confidence
            existing_thread_task.reasoning = routing.reason
            existing_thread_task.update_count += 1
            existing_thread_task.task_payload_json = json.dumps(payload, default=str)
            existing_thread_task.supporting_data_json = json.dumps(_supporting_data(email, extraction, routing), default=str)
            existing_thread_task.updated_at = utc_now()
            self.session.add(existing_thread_task)
            self._persist_processed(email, candidate_id, run_id, ProcessingStatus.updated, existing_thread_task.id, routing.reason, extraction, routing)
            self.session.commit()
            return IngestItemResult(
                source_email_id=email.email_id,
                thread_id=email.thread_id,
                status="updated",
                task_id=existing_thread_task.external_task_id,
                assignee_id=routing.assignee_id,
                priority=routing.priority,
                reason="Existing thread task updated; quoted history was excluded from extraction.",
            )

        task = TaskRecord(
            external_task_id=_stable_task_id(candidate_id, email.thread_id),
            candidate_id=candidate_id,
            thread_id=email.thread_id,
            source_email_id=email.email_id,
            assignee_id=routing.assignee_id or "u_triage",
            category=routing.category or "triage",
            priority=routing.priority,
            title=payload["title"],
            description=payload["description"],
            company=extraction.company_name,
            deal_value_inr=extraction.deal_value_inr,
            due_date=extraction.due_date,
            confidence=extraction.confidence,
            reasoning=routing.reason,
            task_payload_json=json.dumps(payload, default=str),
            supporting_data_json=json.dumps(_supporting_data(email, extraction, routing), default=str),
        )
        self.session.add(task)
        self.session.flush()
        self._persist_processed(email, candidate_id, run_id, ProcessingStatus.created, task.id, routing.reason, extraction, routing)
        self.session.commit()
        return IngestItemResult(
            source_email_id=email.email_id,
            thread_id=email.thread_id,
            status="created",
            task_id=task.external_task_id,
            assignee_id=routing.assignee_id,
            priority=routing.priority,
            reason=routing.reason,
        )

    def _persist_skip(self, email, candidate_id, run_id, skip_type, reason, extraction_json, routing_json):
        self.session.add(
            SkippedEmail(
                candidate_id=candidate_id,
                run_id=run_id,
                source_email_id=email.email_id,
                thread_id=email.thread_id,
                skip_type=skip_type,
                reason=reason,
                subject=email.subject,
                from_email=str(email.from_email),
                received_at=email.received_at,
            )
        )
        self.session.add(
            ProcessedEmail(
                candidate_id=candidate_id,
                run_id=run_id,
                source_email_id=email.email_id,
                thread_id=email.thread_id,
                message_index=email.message_index,
                status=ProcessingStatus.skipped,
                category=skip_type,
                confidence=1.0,
                reason=reason,
                received_at=email.received_at,
                raw_email_json=email.model_dump_json(by_alias=True),
                extraction_json=extraction_json,
                routing_json=routing_json,
            )
        )
        self.session.commit()
        return IngestItemResult(source_email_id=email.email_id, thread_id=email.thread_id, status="skipped", reason=reason)

    def _persist_processed(self, email, candidate_id, run_id, status, task_record_id, reason, extraction, routing):
        self.session.add(
            ProcessedEmail(
                candidate_id=candidate_id,
                run_id=run_id,
                source_email_id=email.email_id,
                thread_id=email.thread_id,
                message_index=email.message_index,
                status=status,
                category=routing.category or extraction.category,
                confidence=extraction.confidence,
                task_record_id=task_record_id,
                reason=reason,
                received_at=email.received_at,
                raw_email_json=email.model_dump_json(by_alias=True),
                extraction_json=extraction.model_dump_json(),
                routing_json=routing.model_dump_json(),
            )
        )

    def _task_id(self, task_record_id: int | None) -> str | None:
        task = self.session.get(TaskRecord, task_record_id) if task_record_id else None
        return task.external_task_id if task else None


def _stable_task_id(candidate_id: str, thread_id: str) -> str:
    digest = hashlib.sha256(f"{candidate_id}:{thread_id}".encode()).hexdigest()[:12]
    return f"tsk_{digest}"


def _build_task_payload(candidate_id, email, extraction, routing) -> dict:
    category = routing.category or "triage"
    return {
        "candidate_id": candidate_id,
        "source_email_id": email.email_id,
        "thread_id": email.thread_id,
        "title": f"{category.replace('_', ' ').title()}: {(email.subject or 'Action required')[:90]}",
        "description": extraction.summary,
        "assignee_id": routing.assignee_id,
        "category": category,
        "priority": routing.priority,
        "due_date": extraction.due_date.isoformat() if extraction.due_date else None,
        "deal_value_inr": extraction.deal_value_inr,
        "company_name": extraction.company_name,
        "confidence": extraction.confidence,
    }


def _supporting_data(email, extraction, routing) -> dict:
    return {
        "source_email_id": email.email_id,
        "thread_id": email.thread_id,
        "subject": email.subject,
        "category": routing.category,
        "signals": extraction.signals,
        "rule_id": routing.rule_id,
        "reason": routing.reason,
    }
