from dataclasses import dataclass
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime
import re

from config.settings import GMAIL_LOOKBACK_DAYS, GMAIL_MAX_EMAILS


@dataclass
class EmailRecord:
    message_id: str
    sender: str
    sender_email: str
    subject: str
    date: datetime | None
    body: str


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    decoded_parts = decode_header(value)
    chunks = []
    for content, charset in decoded_parts:
        if isinstance(content, bytes):
            chunks.append(content.decode(charset or "utf-8", errors="replace"))
        else:
            chunks.append(content)
    return "".join(chunks).strip()


def _sender_email(sender: str) -> str:
    match = re.search(r"<([^>]+)>", sender)
    if match:
        return match.group(1).strip().lower()
    match = re.search(r"[\w.\-+%]+@[\w.\-]+\.[A-Za-z]{2,}", sender)
    return match.group(0).strip().lower() if match else ""


def _message_date(message: Message) -> datetime | None:
    try:
        parsed = parsedate_to_datetime(message.get("Date"))
        if parsed and parsed.tzinfo:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def _extract_body(message: Message, max_chars: int = 5000) -> str:
    parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", "")).lower()
            if "attachment" in disposition or content_type not in {"text/plain", "text/html"}:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            parts.append(text)
    else:
        payload = message.get_payload(decode=True)
        if payload:
            parts.append(payload.decode(message.get_content_charset() or "utf-8", errors="replace"))

    body = "\n".join(parts)
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    return body[:max_chars]


def fetch_recent_emails(client, lookback_days: int = GMAIL_LOOKBACK_DAYS, max_emails: int = GMAIL_MAX_EMAILS) -> list[EmailRecord]:
    status, _ = client.select("INBOX", readonly=True)
    if status != "OK":
        raise RuntimeError("Unable to select Gmail inbox.")

    since_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%d-%b-%Y")
    status, data = client.search(None, "SINCE", since_date)
    if status != "OK" or not data:
        return []

    message_ids = data[0].split()[-max_emails:]
    records: list[EmailRecord] = []
    for raw_id in reversed(message_ids):
        status, payload = client.fetch(raw_id, "(RFC822)")
        if status != "OK" or not payload:
            continue
        raw_message = payload[0][1]
        if not isinstance(raw_message, bytes):
            continue
        message = message_from_bytes(raw_message)
        sender = _decode_header_value(message.get("From"))
        subject = _decode_header_value(message.get("Subject"))
        records.append(
            EmailRecord(
                message_id=raw_id.decode("utf-8", errors="replace"),
                sender=sender,
                sender_email=_sender_email(sender),
                subject=subject,
                date=_message_date(message),
                body=_extract_body(message),
            )
        )
    return records
