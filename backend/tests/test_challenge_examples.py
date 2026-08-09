from datetime import date, datetime, timezone

import pytest

from app.schemas import EmailIn
from app.services.extractor import HeuristicExtractor
from app.services.preprocess import obvious_skip_type
from app.services.routing import route_extraction


RECEIVED = datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc)


def email(subject: str, body: str, email_id: str = "worked-example") -> EmailIn:
    return EmailIn(
        email_id=email_id,
        thread_id=f"thread-{email_id}",
        message_index=0,
        from_name="Challenge Sender",
        from_email="sender@example.com",
        to=["sales@example.com"],
        cc=[],
        subject=subject,
        body=body,
        received_at=RECEIVED,
        attachments=[],
        is_reply=False,
    )


@pytest.mark.parametrize(
    ("subject", "body", "skip_type"),
    [
        ("Automatic reply", "I am out of office until Monday.", "out_of_office"),
        ("Weekly digest", "This week's newsletter. Unsubscribe here.", "newsletter"),
        (
            "Your website is not ranking on page 1",
            "We offer content marketing and webinar promotion. Book a free audit.",
            "vendor_spam",
        ),
    ],
)
def test_directional_noise_is_skipped(subject, body, skip_type):
    skip = obvious_skip_type(subject, body)
    assert skip is not None
    assert skip[0] == skip_type


def test_enterprise_indian_currency_ordinal_date_and_company():
    message = email(
        "Enterprise document-management RFP",
        "Company: Meridian Steel. Please submit a proposal. Budget Rs. 25,00,000; deadline 12th August 2026.",
    )
    extraction = HeuristicExtractor().extract(message)
    decision = route_extraction(extraction, message.received_at)
    assert extraction.company_name == "Meridian Steel"
    assert extraction.deal_value_inr == 2_500_000
    assert extraction.due_date == date(2026, 8, 12)
    assert decision.assignee_id == "u_aarti"
    assert decision.priority == "medium"


def test_government_tender_override_below_threshold():
    message = email("PSU tender", "Government PSU tender. Please quote INR 4,00,000.")
    decision = route_extraction(HeuristicExtractor().extract(message), message.received_at)
    assert decision.assignee_id == "u_aarti"
    assert decision.rule_id == "route.gov_psu"


def test_smb_demo_routes_to_rohit():
    message = email("Demo request", "Could you schedule a product demo? Budget INR 6L.")
    extraction = HeuristicExtractor().extract(message)
    decision = route_extraction(extraction, message.received_at)
    assert extraction.deal_value_inr == 600_000
    assert decision.assignee_id == "u_rohit"


def test_company_is_extracted_from_an_explicit_signature():
    message = email(
        "Demo request",
        "Could you schedule a demo sometime next week?\n— Ankit Bose, Founder, Railyard Logistics",
    )
    extraction = HeuristicExtractor().extract(message)
    assert extraction.company_name == "Railyard Logistics"


def test_company_like_sender_name_is_used_without_domain_inference():
    message = email("Invoice overdue", "Please resolve this overdue invoice payment.")
    message.from_name = "Vantage Cloud Services"
    extraction = HeuristicExtractor().extract(message)
    assert extraction.company_name == "Vantage Cloud Services"


def test_sponsorship_price_remains_pipeline_value():
    message = email(
        "Webinar sponsorship",
        "Company: Growth Collective. We would like the INR 4,00,000 sponsorship package.",
    )
    extraction = HeuristicExtractor().extract(message)
    decision = route_extraction(extraction, message.received_at)
    assert extraction.company_name == "Growth Collective"
    assert extraction.deal_value_inr == 400_000
    assert decision.assignee_id == "u_meera"


def test_high_value_sponsorship_still_routes_to_marketing():
    message = email(
        "Conference sponsorship",
        "Company: Growth Collective. We would like the INR 15,00,000 sponsorship package.",
    )
    extraction = HeuristicExtractor().extract(message)
    decision = route_extraction(extraction, message.received_at)
    assert extraction.deal_value_inr == 1_500_000
    assert (decision.assignee_id, decision.category) == ("u_meera", "marketing")


def test_high_value_reseller_still_routes_to_alliances():
    message = email(
        "Reseller partnership",
        "Company: Zenith Cloud Partners. Could we discuss a reseller partnership priced at INR 20L?",
    )
    extraction = HeuristicExtractor().extract(message)
    decision = route_extraction(extraction, message.received_at)
    assert extraction.deal_value_inr == 2_000_000
    assert (decision.assignee_id, decision.category) == ("u_karan", "alliances")


def test_priced_competing_intents_remain_in_triage():
    message = email(
        "Platform evaluation and webinar",
        "Please schedule a product demo for our INR 25L evaluation and discuss a webinar sponsorship.",
    )
    extraction = HeuristicExtractor().extract(message)
    decision = route_extraction(extraction, message.received_at)
    assert extraction.deal_value_inr == 2_500_000
    assert (decision.assignee_id, decision.category) == ("u_triage", "triage")


def test_overdue_invoice_is_high_but_not_pipeline_value():
    message = email("Invoice overdue", "Invoice Rs. 6,50,000 is overdue. Please resolve the payment issue.")
    extraction = HeuristicExtractor().extract(message)
    decision = route_extraction(extraction, message.received_at)
    assert extraction.deal_value_inr is None
    assert decision.assignee_id == "u_divya"
    assert decision.priority == "high"


def test_alliance_without_date_is_medium():
    message = email("Reseller partnership", "Could we discuss a reseller partnership?")
    decision = route_extraction(HeuristicExtractor().extract(message), message.received_at)
    assert decision.assignee_id == "u_karan"
    assert decision.priority == "medium"


def test_competing_intents_go_to_medium_triage():
    message = email("Partnership and invoice", "Please discuss a partnership and help with an invoice.")
    extraction = HeuristicExtractor().extract(message)
    decision = route_extraction(extraction, message.received_at)
    assert extraction.confidence == 0.42
    assert decision.assignee_id == "u_triage"
    assert decision.priority == "medium"


def test_hinglish_crore_and_date_are_parsed():
    message = email(
        "RFP budget update",
        "Company: Bharat Systems. Budget INR 1.2 cr hai aur deadline 20th ko August 2026.",
    )
    extraction = HeuristicExtractor().extract(message)
    decision = route_extraction(extraction, message.received_at)
    assert extraction.deal_value_inr == 12_000_000
    assert extraction.due_date == date(2026, 8, 20)
    assert decision.assignee_id == "u_aarti"
    assert decision.priority == "medium"
