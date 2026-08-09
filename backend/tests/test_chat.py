import json
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import ProcessedEmail, ProcessingStatus, TaskRecord
from app.services.chat import answer_question


CANDIDATE = "cakhiltej9001@gmail.com"


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'chat.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    tasks = [
        TaskRecord(
            external_task_id="tsk-rfp", candidate_id=CANDIDATE, thread_id="thread-rfp", source_email_id="mail-rfp",
            assignee_id="u_aarti", category="enterprise_rfp", priority="high", title="Enterprise RFP",
            description="Proposal", deal_value_inr=2_500_000, confidence=0.9, reasoning="Enterprise rule",
        ),
        TaskRecord(
            external_task_id="tsk-rfp-missing", candidate_id=CANDIDATE, thread_id="thread-rfp-2", source_email_id="mail-rfp-2",
            assignee_id="u_aarti", category="enterprise_rfp", priority="low", title="RFP without value",
            description="Proposal", deal_value_inr=None, confidence=0.8, reasoning="Enterprise rule",
        ),
        TaskRecord(
            external_task_id="tsk-marketing", candidate_id=CANDIDATE, thread_id="thread-marketing", source_email_id="mail-marketing",
            assignee_id="u_meera", category="marketing", priority="low", title="Marketing",
            description="Campaign", confidence=0.8, reasoning="Marketing rule",
        ),
        TaskRecord(
            external_task_id="tsk-triage", candidate_id=CANDIDATE, thread_id="thread-triage", source_email_id="mail-triage",
            assignee_id="u_triage", category="triage", priority="high", title="Ambiguous",
            description="Invoice and partnership", confidence=0.42, reasoning="Competing intents",
        ),
        TaskRecord(
            external_task_id="tsk-alliance", candidate_id=CANDIDATE, thread_id="thread-alliance", source_email_id="mail-alliance",
            assignee_id="u_karan", category="alliances", priority="medium", title="Reseller",
            description="Reseller integration", confidence=0.8, reasoning="Alliance rule",
        ),
    ]
    session.add_all(tasks)
    session.flush()
    by_source = {task.source_email_id: task for task in tasks}
    rows = [
        ("mail-rfp", "thread-rfp", ProcessingStatus.created, "enterprise_rfp", False, "proposal rfp"),
        ("mail-rfp-2", "thread-rfp-2", ProcessingStatus.created, "enterprise_rfp", False, "proposal rfp"),
        ("mail-marketing", "thread-marketing", ProcessingStatus.created, "marketing", False, "marketing campaign"),
        ("mail-triage", "thread-triage", ProcessingStatus.created, "triage", True, "invoice partnership"),
        ("mail-alliance", "thread-alliance", ProcessingStatus.created, "alliances", False, "reseller integration"),
        ("mail-gst", "thread-gst", ProcessingStatus.skipped, "not_actionable", False, "GST refund status"),
        ("mail-spam", "thread-spam", ProcessingStatus.skipped, "vendor_spam", False, "SEO marketing campaign"),
        ("mail-update-1", "thread-rfp", ProcessingStatus.updated, "enterprise_rfp", False, "deadline update"),
        ("mail-update-2", "thread-rfp", ProcessingStatus.updated, "enterprise_rfp", False, "budget update"),
    ]
    for source, thread, status, category, spurious, raw in rows:
        task = by_source.get(source) or (by_source["mail-rfp"] if status == ProcessingStatus.updated else None)
        session.add(ProcessedEmail(
            candidate_id=CANDIDATE,
            run_id="chat-eval",
            source_email_id=source,
            thread_id=thread,
            status=status,
            category=category,
            confidence=task.confidence if task else 1.0,
            spurious_flagged=spurious,
            task_record_id=task.id if task else None,
            reason="Test audit",
            raw_email_json=json.dumps({"body": raw}),
        ))
    session.commit()
    return session


@pytest.mark.parametrize(
    ("question", "intent", "supporting_key"),
    [
        ("How many proposal or RFP-related emails?", "enterprise_rfp_count", "enterprise_rfp"),
        ("Marketing versus spam?", "marketing_vs_spam", "skipped_marketing_lookalike_spam"),
        ("Why are tasks in triage?", "triage_tasks", "items"),
        ("What is the spurious rate?", "spurious_rate", "spurious_rate"),
        ("How many GST refund emails?", "gst_refund_count", "gst_refund_count"),
        ("What is the total open RFP deal value?", "open_rfp_value", "rfps_with_no_stated_value"),
        ("Which high priority tasks have low confidence?", "high_priority_low_confidence", "matches"),
        ("Alliances: reseller versus integration?", "alliances_breakdown_unavailable", "alliances"),
        ("How many high priority tasks?", "high_priority_tasks", "high_priority_count"),
        ("Show counts by assignee", "count_by_assignee", "by_assignee"),
        ("Which threads were updated more than once?", "repeated_thread_updates", "threads_updated_multiple_times"),
        ("Send an email to the owner", "out_of_scope", None),
    ],
)
def test_grounded_chat_intents(tmp_path, question, intent, supporting_key):
    session = _session(tmp_path)
    _, supporting_data, actual_intent = answer_question(session, CANDIDATE, question)
    assert actual_intent == intent
    if supporting_key:
        assert supporting_key in supporting_data
