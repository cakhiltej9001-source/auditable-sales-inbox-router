from datetime import datetime, time, timedelta, timezone

from app.schemas import ExtractionResult, RoutingDecision, TaskCategory, TaskPriority


ENTERPRISE_THRESHOLD_INR = 1_000_000


def route_extraction(extraction: ExtractionResult, received_at: datetime | None = None) -> RoutingDecision:
    reference = received_at or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    if extraction.category in {"newsletter", "out_of_office", "vendor_spam", "not_actionable"} or not extraction.is_actionable:
        return RoutingDecision(
            should_skip=True,
            skip_type=extraction.category,
            reason=f"Skipped as {extraction.category}; no trustworthy operational task should be created.",
            rule_id="skip.no_task",
        )

    priority = _priority(extraction, reference)

    if _has_government_signal(extraction):
        return _decision("u_aarti", "enterprise_rfp", priority, "Government/PSU tender override applies irrespective of value.", "route.gov_psu")
    if extraction.category == "enterprise_rfp" or (
        extraction.deal_value_inr is not None and extraction.deal_value_inr > ENTERPRISE_THRESHOLD_INR
    ):
        return _decision("u_aarti", "enterprise_rfp", priority, "Enterprise RFP or deal above INR 10L.", "route.enterprise")
    if extraction.category == "finance":
        return _decision("u_divya", "finance", priority, "Invoice, purchase order, payment, GST, or billing request.", "route.finance")
    if extraction.category == "marketing":
        return _decision("u_meera", "marketing", priority, "Marketing, media, campaign, webinar, or sponsorship request.", "route.marketing")
    if extraction.category == "alliances":
        return _decision("u_karan", "alliances", priority, "Alliance, reseller, channel, or integration request.", "route.alliances")
    if extraction.category == "smb_enquiry":
        return _decision("u_rohit", "smb_enquiry", priority, "SMB enquiry or deal at or below INR 10L.", "route.smb")
    return _decision("u_triage", "triage", priority, "Actionable request is ambiguous or contains competing intents.", "route.triage")


def _decision(assignee_id: str, category: TaskCategory, priority: TaskPriority, reason: str, rule_id: str) -> RoutingDecision:
    return RoutingDecision(
        should_skip=False,
        assignee_id=assignee_id,
        category=category,
        priority=priority,
        reason=reason,
        rule_id=rule_id,
    )


def _priority(extraction: ExtractionResult, received_at: datetime) -> TaskPriority:
    if extraction.category == "finance" and any(token in " ".join(extraction.signals).lower() for token in ["overdue", "past due"]):
        return "high"
    if extraction.due_date is None:
        return "low"
    due = datetime.combine(extraction.due_date, time.min, tzinfo=received_at.tzinfo or timezone.utc)
    if due <= received_at + timedelta(hours=72):
        return "high"
    return "medium"


def _has_government_signal(extraction: ExtractionResult) -> bool:
    text = " ".join([extraction.summary, *extraction.signals]).lower()
    return any(token in text for token in ["government", "govt", "psu", "tender", "ministry", "public sector"])
