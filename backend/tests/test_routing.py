from datetime import date, datetime, timezone

from app.schemas import ExtractionResult
from app.services.routing import route_extraction


RECEIVED = datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc)


def extraction(category: str, **overrides) -> ExtractionResult:
    values = {"category": category, "is_actionable": True, "summary": "Actionable request", "confidence": 0.8}
    values.update(overrides)
    return ExtractionResult(**values)


def test_government_override_beats_low_deal_value():
    decision = route_extraction(
        extraction("smb_enquiry", deal_value_inr=300_000, signals=["PSU tender"]), RECEIVED
    )
    assert decision.assignee_id == "u_aarti"
    assert decision.category == "enterprise_rfp"
    assert decision.rule_id == "route.gov_psu"


def test_enterprise_deal_routes_to_aarti_and_no_deadline_is_low():
    decision = route_extraction(extraction("enterprise_rfp", deal_value_inr=1_500_000), RECEIVED)
    assert decision.assignee_id == "u_aarti"
    assert decision.priority == "low"


def test_deadline_within_72_hours_is_high():
    decision = route_extraction(extraction("smb_enquiry", due_date=date(2026, 8, 10)), RECEIVED)
    assert decision.priority == "high"


def test_later_deadline_is_medium():
    decision = route_extraction(extraction("smb_enquiry", due_date=date(2026, 8, 20)), RECEIVED)
    assert decision.priority == "medium"


def test_business_category_routes():
    assert route_extraction(extraction("finance"), RECEIVED).assignee_id == "u_divya"
    assert route_extraction(extraction("marketing"), RECEIVED).assignee_id == "u_meera"
    assert route_extraction(extraction("alliances"), RECEIVED).assignee_id == "u_karan"
    assert route_extraction(extraction("smb_enquiry"), RECEIVED).assignee_id == "u_rohit"
    assert route_extraction(extraction("triage", confidence=0.4), RECEIVED).assignee_id == "u_triage"


def test_noise_is_skipped():
    decision = route_extraction(
        ExtractionResult(category="newsletter", is_actionable=False, summary="Weekly digest", confidence=0.9),
        RECEIVED,
    )
    assert decision.should_skip is True
    assert decision.skip_type == "newsletter"


def test_overdue_finance_is_high_without_due_date():
    decision = route_extraction(extraction("finance", signals=["overdue"]), RECEIVED)
    assert decision.priority == "high"
