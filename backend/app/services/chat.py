from sqlmodel import Session, select

from app.models import ProcessedEmail, ProcessingStatus, SkippedEmail, TaskRecord


def answer_question(session: Session, question: str) -> tuple[str, dict, str]:
    q = question.lower()
    if any(token in q for token in ["skip", "ignored", "noise"]):
        rows = session.exec(select(SkippedEmail).order_by(SkippedEmail.created_at.desc()).limit(10)).all()
        supporting = {
            "skipped_count": len(rows),
            "items": [
                {"source_email_id": row.source_email_id, "skip_type": row.skip_type, "reason": row.reason}
                for row in rows
            ],
        }
        return f"{len(rows)} skipped emails are shown in the latest skipped log.", supporting, "latest_skipped"

    if any(token in q for token in ["pipeline", "deal value", "revenue", "amount"]):
        tasks = session.exec(select(TaskRecord)).all()
        total = sum(task.deal_value_inr or 0 for task in tasks)
        supporting = {"total_pipeline_inr": total, "task_count": len(tasks)}
        return f"Tracked pipeline is INR {total:,} across {len(tasks)} tasks.", supporting, "pipeline_sum"

    if any(token in q for token in ["high priority", "urgent", "deadline"]):
        tasks = session.exec(select(TaskRecord).where(TaskRecord.priority == "high")).all()
        supporting = {
            "high_priority_count": len(tasks),
            "items": [{"task_id": task.external_task_id, "title": task.title, "assignee_id": task.assignee_id} for task in tasks],
        }
        return f"There are {len(tasks)} high-priority tasks.", supporting, "high_priority_tasks"

    if any(token in q for token in ["assignee", "owner", "assigned"]):
        tasks = session.exec(select(TaskRecord)).all()
        counts: dict[str, int] = {}
        for task in tasks:
            counts[task.assignee_id] = counts.get(task.assignee_id, 0) + 1
        return "Tasks by assignee are based on persisted routed tasks.", {"by_assignee": counts}, "count_by_assignee"

    processed = session.exec(select(ProcessedEmail)).all()
    counts = {
        "created": sum(1 for item in processed if item.status == ProcessingStatus.created),
        "updated": sum(1 for item in processed if item.status == ProcessingStatus.updated),
        "duplicates": sum(item.duplicate_count for item in processed),
        "skipped": sum(1 for item in processed if item.status == ProcessingStatus.skipped),
    }
    return "Here is the current processing summary from stored audit rows.", counts, "processing_summary"
