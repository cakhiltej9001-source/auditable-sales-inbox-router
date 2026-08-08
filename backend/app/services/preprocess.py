import re
from html import unescape

from app.schemas import EmailIn


HTML_TAG_RE = re.compile(r"<[^>]+>")
QUOTE_START_RE = re.compile(
    r"(?im)^(?:on .+ wrote:|from:\s.+|-----original message-----|_{5,}|>{1,}\s?.*)$"
)


def normalize_email(email: EmailIn) -> EmailIn:
    body = unescape(HTML_TAG_RE.sub(" ", email.body))
    marker = QUOTE_START_RE.search(body)
    if marker:
        body = body[: marker.start()]
    body = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith(">"))
    body = re.sub(r"\s+", " ", body).strip()
    subject = re.sub(r"\s+", " ", email.subject).strip()
    return email.model_copy(update={"subject": subject, "body": body})


def obvious_skip_type(subject: str, body: str) -> tuple[str, str] | None:
    text = f"{subject} {body}".lower()
    if any(token in text for token in ["out of office", "automatic reply", "auto-reply", "autoreply", "ooo"]):
        return "out_of_office", "Auto-reply or out-of-office message."
    if any(token in text for token in ["unsubscribe", "newsletter", "weekly digest", "monthly digest"]):
        return "newsletter", "Newsletter or digest content."
    spam_phrases = ["seo backlinks", "guest post", "buy verified leads", "verified leads", "rank #1", "boost your rankings", "link building package"]
    if any(token in text for token in spam_phrases):
        return "vendor_spam", "Unsolicited vendor solicitation or spam."
    return None
