import re
import time
from datetime import date, datetime, timedelta

from app.core.config import Settings
from app.schemas import EmailIn, ExtractionResult


class Extractor:
    def extract(self, email: EmailIn) -> ExtractionResult:
        raise NotImplementedError


class GeminiExtractor(Extractor):
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        self.fallback = HeuristicExtractor()

    def _load_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    def extract(self, email: EmailIn) -> ExtractionResult:
        from google.genai import types

        prompt = (
            "Extract only explicitly supported routing facts. Never choose an assignee or priority. "
            "Use enterprise_rfp for RFPs/tenders/deals above INR 10L; smb_enquiry for demos/product enquiries/deals at or below INR 10L; "
            "marketing, alliances, finance, triage, newsletter, out_of_office, vendor_spam, or not_actionable otherwise. "
            "Use null for unstated company, value, or due date. Invoice amounts are not deal values.\n\n"
            f"Received: {email.received_at}\nFrom: {email.from_name or ''} <{email.from_email}>\n"
            f"Subject: {email.subject}\nBody: {email.body}"
        )
        for attempt in range(self.settings.gemini_max_retries):
            try:
                response = self._load_client().models.generate_content(
                    model=self.settings.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_json_schema=ExtractionResult.model_json_schema(),
                    ),
                )
                return ExtractionResult.model_validate_json(response.text or "{}")
            except Exception:
                if attempt + 1 < self.settings.gemini_max_retries:
                    time.sleep(2**attempt)
        return self.fallback.extract(email)


class HeuristicExtractor(Extractor):
    def extract(self, email: EmailIn) -> ExtractionResult:
        text = f"{email.subject} {email.body}".lower()
        groups = {
            "finance": ["invoice", "payment", "billing", "refund", "purchase order", "gst", "vendor bill"],
            "marketing": ["sponsor", "sponsorship", "campaign", "webinar", "event booth", "conference", "media", "content collaboration", "pr opportunity"],
            "alliances": ["partner", "partnership", "alliance", "channel", "reseller", "integration proposal", "technology integration"],
            "enterprise_rfp": ["rfp", "rfi", "tender", "procurement"],
            "smb_enquiry": ["demo", "product enquiry", "product inquiry", "pricing", "quote", "trial"],
        }
        government = any(token in text for token in ["government", "govt", "psu", "ministry", "public sector", "tender"])
        matches = [name for name, tokens in groups.items() if any(token in text for token in tokens)]
        deal_value = _extract_inr(text)

        if government:
            category = "enterprise_rfp"
        elif len(matches) > 1:
            category = "triage"
        elif matches:
            category = matches[0]
        elif deal_value is not None:
            category = "enterprise_rfp" if deal_value > 1_000_000 else "smb_enquiry"
        else:
            category = "triage"

        actionable_tokens = ["please", "can you", "could you", "need", "request", "interested", "discuss", "schedule", "would like", "help", "proposal"]
        actionable = category != "triage" or any(token in text for token in actionable_tokens)
        if not actionable:
            category = "not_actionable"

        if category in {"finance", "marketing", "alliances"}:
            deal_value = None

        signals = [token for token in ["government", "govt", "psu", "tender", "deadline", "overdue", "past due", "invoice", "sponsorship", "partnership", "reseller"] if token in text]
        confidence = 0.9 if government else 0.82 if category not in {"triage", "not_actionable"} else 0.42
        return ExtractionResult(
            category=category,
            is_actionable=actionable,
            company_name=_extract_company(text),
            deal_value_inr=deal_value,
            due_date=_extract_due_date(text, email.received_at),
            summary=(email.subject or email.body[:180] or "Action required")[:180],
            confidence=confidence,
            signals=signals,
        )


def get_extractor(settings: Settings) -> Extractor:
    return GeminiExtractor(settings) if settings.gemini_api_key else HeuristicExtractor()


def _extract_inr(text: str) -> int | None:
    match = re.search(r"(?:inr|rs\.?|₹)\s*([0-9]+(?:\.[0-9]+)?)\s*(cr|crore|l|lac|lakh|lakhs|k)?", text, re.I)
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "").lower()
    if unit in {"cr", "crore"}:
        amount *= 10_000_000
    elif unit in {"l", "lac", "lakh", "lakhs"}:
        amount *= 100_000
    elif unit == "k":
        amount *= 1_000
    return int(amount)


def _extract_due_date(text: str, received_at: datetime | None) -> date | None:
    iso = re.search(r"\b(20[0-9]{2}-[01][0-9]-[0-3][0-9])\b", text)
    if iso:
        try:
            return date.fromisoformat(iso.group(1))
        except ValueError:
            return None
    named = re.search(r"\b([0-3]?\d)\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(20\d{2})\b", text, re.I)
    if named:
        try:
            return datetime.strptime(" ".join(named.groups()), "%d %B %Y").date()
        except ValueError:
            try:
                return datetime.strptime(" ".join(named.groups()), "%d %b %Y").date()
            except ValueError:
                pass
    if received_at:
        base = received_at.date()
        if "tomorrow" in text:
            return base + timedelta(days=1)
        if "today" in text or "eod" in text:
            return base
        relative = re.search(r"within\s+(\d+)\s+days?", text)
        if relative:
            return base + timedelta(days=int(relative.group(1)))
    return None


def _extract_company(text: str) -> str | None:
    match = re.search(r"(?:company|organisation|organization)\s*(?:name)?\s*[:\-]\s*([A-Z][A-Za-z0-9 &.-]{2,60})", text)
    return match.group(1).strip(" .") if match else None
