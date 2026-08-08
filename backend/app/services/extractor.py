import json
import re
from datetime import datetime

from app.core.config import Settings
from app.schemas import EmailIn, ExtractionResult


class Extractor:
    def extract(self, email: EmailIn) -> ExtractionResult:
        raise NotImplementedError


class GeminiExtractor(Extractor):
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None

    def _load_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    def extract(self, email: EmailIn) -> ExtractionResult:
        from google.genai import types

        prompt = (
            "Extract structured routing facts from this sales inbox email. "
            "Return only facts supported by the email. Leave unknown fields null. "
            "Do not choose assignee or priority.\n\n"
            f"From: {email.from_email}\n"
            f"Subject: {email.subject}\n"
            f"Body: {email.body}"
        )
        response = self._load_client().models.generate_content(
            model=self.settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=ExtractionResult.model_json_schema(),
            ),
        )
        raw = response.text or "{}"
        return ExtractionResult.model_validate_json(raw)


class HeuristicExtractor(Extractor):
    def extract(self, email: EmailIn) -> ExtractionResult:
        text = f"{email.subject} {email.body}".lower()
        category = "unknown"
        actionable = True
        signals: list[str] = []

        if any(token in text for token in ["out of office", "automatic reply", "auto-reply", "ooo"]):
            category, actionable = "out_of_office", False
        elif any(token in text for token in ["unsubscribe", "newsletter", "weekly digest"]):
            category, actionable = "newsletter", False
        elif any(token in text for token in ["seo backlinks", "guest post", "verified leads", "rank #1"]):
            category, actionable = "vendor_spam", False
        elif any(token in text for token in ["invoice", "payment", "billing", "refund", "purchase order"]):
            category = "finance"
        elif any(token in text for token in ["sponsor", "sponsorship", "campaign", "webinar", "event booth"]):
            category = "marketing"
        elif any(token in text for token in ["partner", "partnership", "alliance", "channel", "reseller"]):
            category = "alliances"
        elif any(token in text for token in ["government", "govt", "psu", "ministry", "tender"]):
            category = "government"
        elif any(token in text for token in ["rfp", "proposal", "demo", "procurement", "quote"]):
            category = "rfp"

        deal_value = _extract_inr(text)
        due_at = _extract_due_date(text)
        company = _extract_company(email)

        for token in ["government", "psu", "tender", "deadline", "invoice", "sponsorship", "partnership"]:
            if token in text:
                signals.append(token)

        summary = email.subject[:180]
        confidence = 0.82 if category != "unknown" else 0.45
        if not actionable:
            confidence = 0.9

        return ExtractionResult(
            category=category,
            is_actionable=actionable and category != "unknown",
            company=company,
            deal_value_inr=deal_value,
            due_at=due_at,
            summary=summary,
            confidence=confidence,
            signals=signals,
        )


def get_extractor(settings: Settings) -> Extractor:
    if settings.gemini_api_key:
        return GeminiExtractor(settings)
    return HeuristicExtractor()


def _extract_inr(text: str) -> int | None:
    match = re.search(r"(?:inr|rs\.?|₹)\s*([0-9]+(?:\.[0-9]+)?)\s*(cr|crore|l|lac|lakh|k)?", text, re.I)
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "").lower()
    if unit in {"cr", "crore"}:
        amount *= 10_000_000
    elif unit in {"l", "lac", "lakh"}:
        amount *= 100_000
    elif unit == "k":
        amount *= 1_000
    return int(amount)


def _extract_due_date(text: str) -> datetime | None:
    iso = re.search(r"\b(20[0-9]{2}-[01][0-9]-[0-3][0-9])\b", text)
    if iso:
        return datetime.fromisoformat(iso.group(1))
    return None


def _extract_company(email: EmailIn) -> str | None:
    domain = email.from_email.split("@")[-1]
    if domain.lower() in {"gmail.com", "outlook.com", "yahoo.com"}:
        return None
    return domain.split(".")[0].replace("-", " ").title()

