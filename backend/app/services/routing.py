from datetime import datetime, timedelta, timezone

from app.schemas import ExtractionResult, RoutingDecision


ENTERPRISE_THRESHOLD_INR = 1_000_000


def route_extraction(extraction: ExtractionResult, now: datetime | None = None) -> RoutingDecision:
    now = now or datetime.now(timezone.utc)

    if extraction.category in {"newsletter", "out_of_office", "vendor_spam"} or not extraction.is_actionable:
        return RoutingDecision(
            should_skip=True,
            skip_type=extraction.category if extraction.category != "unknown" else "not_actionable",
            reason=f"Skipped because extraction marked it as {extraction.category} and not actionable.",
            rule_id="skip.no_task",
        )

    priority = _priority_for_due_date(extraction.due_at, now)

    if extraction.category == "government" or _has_government_signal(extraction):
        return _decision("u_aarti", priority, "Government/PSU opportunity override.", "route.gov_psu")

    if extraction.deal_value_inr is not None and extraction.deal_value_inr > ENTERPRISE_THRESHOLD_INR:
        return _decision("u_aarti", priority, "Enterprise deal above INR 10L.", "route.enterprise")

    if extraction.category == "finance":
        return _decision("u_divya", priority, "Finance, billing, or payment issue.", "route.finance")

    if extraction.category == "marketing":
        return _decision("u_meera", priority, "Marketing, campaign, or sponsorship request.", "route.marketing")

    if extraction.category == "alliances":
        return _decision("u_karan", priority, "Alliance, channel, or partnership request.", "route.alliances")

    if extraction.deal_value_inr is not None and extraction.deal_value_inr <= ENTERPRISE_THRESHOLD_INR:
        return _decision("u_rohit", priority, "SMB deal at or below INR 10L.", "route.smb")

    if extraction.category in {"rfp", "smb"}:
        return _decision("u_rohit", priority, "Sales opportunity without enterprise or government signal.", "route.sales_default")

    return _decision("u_triage", priority, "Actionable but ambiguous; needs human triage.", "route.triage")


def _decision(assignee_id: str, priority: str, reason: str, rule_id: str) -> RoutingDecision:
    return RoutingDecision(
        should_skip=False,
        assignee_id=assignee_id,
        priority=priority,
        reason=reason,
        rule_id=rule_id,
    )


def _priority_for_due_date(due_at: datetime | None, now: datetime) -> str:
    if due_at is None:
        return "normal"
    due = due_at if due_at.tzinfo else due_at.replace(tzinfo=timezone.utc)
    if due <= now + timedelta(hours=72):
        return "high"
    return "medium"


def _has_government_signal(extraction: ExtractionResult) -> bool:
    text = " ".join([extraction.summary, *extraction.signals]).lower()
    return any(token in text for token in ["government", "govt", "psu", "tender", "ministry", "public sector"])

