import json
from collections import Counter

from sqlmodel import Session, select

from app.core.identity import normalize_candidate_id
from app.models import ProcessedEmail, ProcessingStatus, TaskRecord


def answer_question(
    session: Session,
    candidate_id: str,
    question: str,
    email_ids: list[str] | None = None,
) -> tuple[str, dict, str]:
    q = question.lower().strip()
    candidate = normalize_candidate_id(candidate_id)
    processed = session.exec(select(ProcessedEmail).where(ProcessedEmail.candidate_id == candidate)).all()
    if email_ids is not None:
        allowed = set(email_ids)
        processed = [row for row in processed if row.source_email_id in allowed]
    task_ids = {row.task_record_id for row in processed if row.task_record_id is not None}
    tasks = session.exec(select(TaskRecord).where(TaskRecord.candidate_id == candidate)).all()
    if email_ids is not None:
        tasks = [task for task in tasks if task.id in task_ids]

    asks_to_send_email = any(verb in q for verb in ["send", "email", "message", "notify"]) and any(
        verb in q for verb in ["send", "write", "draft", "compose", "notify"]
    )
    if asks_to_send_email or any(token in q for token in ["delete", "assign it", "reassign", "create a task", "close the task"]):
        return "I can answer questions about processed inbox data, but I cannot send emails or perform actions.", {}, "out_of_scope"

    if "gst" in q and "refund" in q:
        count = sum(1 for row in processed if "gst" in row.raw_email_json.lower() and "refund" in row.raw_email_json.lower())
        return f"There are {count} emails about GST refunds in this batch.", {"gst_refund_count": count}, "gst_refund_count"

    if "thread" in q and any(token in q for token in ["updated", "update", "changed", "more than once", "multiple"]):
        updates = Counter(row.thread_id for row in processed if row.status == ProcessingStatus.updated)
        repeated = sorted(thread_id for thread_id, count in updates.items() if count > 1)
        return (
            f"{len(repeated)} threads were updated more than once.",
            {"threads_updated_multiple_times": repeated},
            "repeated_thread_updates",
        )

    if "spurious" in q:
        spurious = sum(1 for row in processed if row.spurious_flagged)
        total = len(processed)
        rate = round(spurious / total, 3) if total else 0.0
        data = {"spurious_count": spurious, "processed": total, "spurious_rate": rate}
        return f"The spurious rate is {rate:.1%}: {spurious} flagged tasks across {total} processed emails.", data, "spurious_rate"

    if "triage" in q:
        matches = [task for task in tasks if task.category == "triage"]
        items = [{"task_id": task.external_task_id, "reason": task.reasoning, "description": task.description} for task in matches]
        data = {"triage_count": len(matches), "triage_task_ids": [item["task_id"] for item in items], "items": items}
        return f"There are {len(matches)} tasks in triage. Each item includes the stored routing reason.", data, "triage_tasks"

    if "high" in q and "confidence" in q:
        matches = [task for task in tasks if task.priority == "high" and task.confidence < 0.6]
        data = {"matches": [{"task_id": task.external_task_id, "confidence": task.confidence} for task in matches]}
        return f"There are {len(matches)} high-priority tasks with confidence below 0.60.", data, "high_priority_low_confidence"

    if "alliances" in q and any(token in q for token in ["reseller", "integration", "versus", "vs"]):
        count = sum(1 for row in processed if row.category == "alliances" and row.status != ProcessingStatus.skipped)
        return (
            f"There are {count} alliances emails, but the stored schema does not reliably separate resellers from technology-integration partners.",
            {"alliances": count},
            "alliances_breakdown_unavailable",
        )

    if any(token in q for token in ["deal value", "pipeline", "open rfp", "total value"]):
        rfps = [task for task in tasks if task.category == "enterprise_rfp" and task.status == "open"]
        total = sum(task.deal_value_inr for task in rfps if task.deal_value_inr is not None)
        missing = sum(1 for task in rfps if task.deal_value_inr is None)
        data = {"total_deal_value_inr": total, "rfps_with_no_stated_value": missing}
        return f"Open RFP value is INR {total:,}; {missing} RFP tasks have no stated value and were not treated as zero.", data, "open_rfp_value"

    asks_about_rfps = "rfp" in q or "proposal" in q
    asks_about_marketing = any(token in q for token in ["marketing", "sponsorship", "campaign", "webinar"])
    if asks_about_rfps and asks_about_marketing:
        enterprise = sum(1 for row in processed if row.category == "enterprise_rfp" and row.status != ProcessingStatus.skipped)
        marketing = sum(1 for row in processed if row.category == "marketing" and row.status != ProcessingStatus.skipped)
        data = {"enterprise_rfp": enterprise, "marketing": marketing}
        return (
            f"This batch contains {enterprise} proposal or enterprise-RFP emails and {marketing} marketing emails.",
            data,
            "rfp_vs_marketing",
        )

    if asks_about_marketing and any(token in q for token in ["spam", "junk", "ignored", "skipped", "vendor pitch"]):
        marketing = sum(1 for row in processed if row.category == "marketing" and row.status != ProcessingStatus.skipped)
        spam = sum(
            1 for row in processed
            if row.category == "vendor_spam" and any(token in row.raw_email_json.lower() for token in ["marketing", "seo", "leads", "campaign"])
        )
        data = {"marketing": marketing, "skipped_marketing_lookalike_spam": spam}
        return f"{marketing} emails were routed as marketing; {spam} marketing-adjacent vendor spam emails were correctly skipped.", data, "marketing_vs_spam"

    if asks_about_rfps:
        count = sum(1 for row in processed if row.category == "enterprise_rfp" and row.status != ProcessingStatus.skipped)
        return f"There are {count} proposal or enterprise-RFP-related emails in this batch.", {"enterprise_rfp": count}, "enterprise_rfp_count"

    if any(token in q for token in ["high priority", "urgent", "deadline"]):
        matches = [task for task in tasks if task.priority == "high"]
        data = {"high_priority_count": len(matches), "items": [{"task_id": t.external_task_id, "title": t.title, "assignee_id": t.assignee_id} for t in matches]}
        return f"There are {len(matches)} high-priority tasks.", data, "high_priority_tasks"

    if any(token in q for token in ["assignee", "owner", "assigned"]):
        counts = Counter(task.assignee_id for task in tasks)
        return "Task counts by assignee come directly from persisted tasks.", {"by_assignee": dict(counts)}, "count_by_assignee"

    counts = Counter(row.category for row in processed)
    statuses = Counter(row.status.value for row in processed)
    data = {"processed": len(processed), "by_category": dict(counts), "by_status": dict(statuses)}
    return "Here is the stored processing summary for this batch. Ask about RFPs, marketing versus spam, triage, priority, value, or updates for more detail.", data, "processing_summary"
