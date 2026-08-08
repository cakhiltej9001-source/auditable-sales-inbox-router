from datetime import datetime, timezone

from app.schemas import ExtractionResult
from app.services.routing import route_extraction


NOW = datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc)


def test_government_signal_overrides_other_rules():
    extraction = ExtractionResult(
        category="government",
        is_actionable=True,
        deal_value_inr=300_000,
        due_at=datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc),
        summary="PSU tender for LMS",
        confidence=0.9,
        signals=["psu", "tender"],
    )

    decision = route_extraction(extraction, now=NOW)

    assert decision.assignee_id == "u_aarti"
    assert decision.priority == "high"
    assert decision.rule_id == "route.gov_psu"


def test_enterprise_deal_routes_to_aarti():
    extraction = ExtractionResult(
        category="rfp",
        is_actionable=True,
        deal_value_inr=1_500_000,
        due_at=None,
        summary="Enterprise proposal",
        confidence=0.8,
    )

    decision = route_extraction(extraction, now=NOW)

    assert decision.assignee_id == "u_aarti"
    assert decision.rule_id == "route.enterprise"


def test_finance_routes_to_divya():
    extraction = ExtractionResult(
        category="finance",
        is_actionable=True,
        summary="Invoice dispute",
        confidence=0.8,
    )

    assert route_extraction(extraction, now=NOW).assignee_id == "u_divya"


def test_marketing_routes_to_meera():
    extraction = ExtractionResult(
        category="marketing",
        is_actionable=True,
        summary="Sponsorship request",
        confidence=0.8,
    )

    assert route_extraction(extraction, now=NOW).assignee_id == "u_meera"


def test_alliances_routes_to_karan():
    extraction = ExtractionResult(
        category="alliances",
        is_actionable=True,
        summary="Channel partner request",
        confidence=0.8,
    )

    assert route_extraction(extraction, now=NOW).assignee_id == "u_karan"


def test_newsletter_is_skipped():
    extraction = ExtractionResult(
        category="newsletter",
        is_actionable=False,
        summary="Weekly digest",
        confidence=0.9,
    )

    decision = route_extraction(extraction, now=NOW)

    assert decision.should_skip is True
    assert decision.skip_type == "newsletter"

