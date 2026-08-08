import re
from html import unescape

from app.schemas import EmailIn


HTML_TAG_RE = re.compile(r"<[^>]+>")
QUOTE_RE = re.compile(r"(?im)^(>.*|on .* wrote:)$")


def normalize_email(email: EmailIn) -> EmailIn:
    body = unescape(HTML_TAG_RE.sub(" ", email.body))
    body = "\n".join(line for line in body.splitlines() if not QUOTE_RE.match(line.strip()))
    body = re.sub(r"\s+", " ", body).strip()
    subject = re.sub(r"\s+", " ", email.subject).strip()
    return email.model_copy(update={"subject": subject, "body": body})


def obvious_skip_type(subject: str, body: str) -> tuple[str, str] | None:
    text = f"{subject} {body}".lower()
    if any(token in text for token in ["out of office", "automatic reply", "ooo", "auto-reply"]):
        return "out_of_office", "Auto-reply or out-of-office message."
    if any(token in text for token in ["unsubscribe", "newsletter", "weekly digest"]):
        return "newsletter", "Newsletter or digest content."
    if any(token in text for token in ["seo backlinks", "guest post", "buy verified leads", "rank #1"]):
        return "vendor_spam", "Vendor solicitation or spam."
    return None

