from dataclasses import dataclass
import re

from modules.email.fetcher import EmailRecord


@dataclass
class ClassificationResult:
    status: str
    confidence: float
    matched_keywords: list[str]


STATUS_RULES: list[tuple[str, float, list[str]]] = [
    ("Rejected", 0.95, [
        r"\bnot moving forward\b", r"\bnot be moving forward\b", r"\bnot selected\b",
        r"\bwe regret\b", r"\bunfortunately\b", r"\brejected\b", r"\bposition has been filled\b",
        r"\bdecided to pursue other candidates\b",
    ]),
    ("Interview Scheduled", 0.92, [
        r"\binterview\b", r"\bdiscussion\b", r"\bschedule a call\b", r"\bschedule.*interview\b",
        r"\bcalendar invite\b", r"\bmeet with\b", r"\bavailability\b",
    ]),
    ("OA Received", 0.9, [
        r"\bonline assessment\b", r"\bassessment\b", r"\bcoding assessment\b",
        r"\bcoding challenge\b", r"\bhackerrank\b", r"\bcodility\b", r"\btestgorilla\b",
        r"\btechnical assessment\b",
    ]),
    ("Under Review", 0.78, [
        r"\bunder review\b", r"\breviewing your application\b", r"\bapplication is being reviewed\b",
        r"\brecruiting team is reviewing\b",
    ]),
    ("Viewed", 0.72, [
        r"\bviewed your application\b", r"\bprofile was viewed\b", r"\bapplication was viewed\b",
    ]),
    ("Shortlisted", 0.84, [
        r"\bshortlisted\b", r"\bshort-listed\b", r"\bmoving forward\b", r"\bnext step\b",
        r"\bproceed to the next\b", r"\bselected for the next\b",
    ]),
    ("On Hold", 0.76, [
        r"\bon hold\b", r"\bpaused hiring\b", r"\bhiring process.*pause\b", r"\brole is paused\b",
    ]),
    ("Offer", 0.94, [
        r"\boffer letter\b", r"\bpleased to offer\b", r"\bjob offer\b", r"\boffer of employment\b",
    ]),
    ("Withdrawn", 0.9, [
        r"\bwithdrawn your application\b", r"\bapplication has been withdrawn\b", r"\byou withdrew\b",
    ]),
    ("Ghosted", 0.7, [
        r"\bhave not heard back\b", r"\bno response\b", r"\bfollowing up\b",
    ]),
]

APPLICATION_HINTS = [
    r"\bapplication\b", r"\bapplied\b", r"\bresume\b", r"\bcv\b", r"\bjob\b",
    r"\brole\b", r"\bposition\b", r"\brecruit", r"\btalent acquisition\b",
]


def classify_email(record: EmailRecord) -> ClassificationResult | None:
    text = f"{record.sender} {record.subject} {record.body}".lower()
    if not any(re.search(pattern, text) for pattern in APPLICATION_HINTS):
        return None

    best: ClassificationResult | None = None
    for status, base_confidence, patterns in STATUS_RULES:
        matched = [pattern.strip(r"\b") for pattern in patterns if re.search(pattern, text)]
        if not matched:
            continue
        confidence = min(0.99, base_confidence + (0.02 * min(len(matched) - 1, 3)))
        if best is None or confidence > best.confidence:
            best = ClassificationResult(status=status, confidence=confidence, matched_keywords=matched)
    return best
