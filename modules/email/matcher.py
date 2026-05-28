from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
import re

from modules.email.fetcher import EmailRecord


@dataclass
class MatchResult:
    index: int
    confidence: float
    reasons: list[str]


def _norm(value: str) -> str:
    value = str(value or "").lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _compact(value: str) -> str:
    return _norm(value).replace(" ", "")


def _similarity(left: str, right: str) -> float:
    left = _norm(left)
    right = _norm(right)
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _urls(value: str) -> set[str]:
    return {match.rstrip(").,]") for match in re.findall(r"https?://[^\s<>\"]+", value or "")}


def _linkedin_job_ids(value: str) -> set[str]:
    ids: set[str] = set()
    for url in _urls(value):
        match = re.search(r"/jobs/view/(\d+)", url)
        if match:
            ids.add(match.group(1))
    ids.update(re.findall(r"\b(?:job\s*id|jobid|jobs/view)[^\d]{0,10}(\d{5,})\b", value or "", flags=re.I))
    return ids


def _domain(email_address: str) -> str:
    if "@" not in email_address:
        return ""
    domain = email_address.split("@", 1)[1].lower()
    return domain.split(".")[0]


def sender_domain(email_address: str) -> str:
    return _domain(email_address)


def sender_host(email_address: str) -> str:
    if "@" not in email_address:
        return ""
    return email_address.split("@", 1)[1].lower()


def _parse_date(value: str) -> datetime | None:
    value = str(value or "").strip()
    if not value or value.lower() in {"pending", "unknown"}:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(value[:26], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def match_email_to_application(record: EmailRecord, applications: list[dict[str, str]]) -> MatchResult | None:
    subject = _norm(record.subject)
    sender_text = _norm(record.sender)
    text = _norm(f"{record.sender} {record.subject} {record.body}")
    raw_text = f"{record.sender} {record.subject} {record.body}"
    email_urls = _urls(raw_text)
    email_job_ids = _linkedin_job_ids(raw_text)
    sender_domain = _domain(record.sender_email)
    best: MatchResult | None = None

    for index, app in enumerate(applications):
        score = 0.0
        reasons: list[str] = []
        anchor_found = False
        company = _norm(app.get("company", ""))
        recruiter_name = _norm(app.get("recruiter_name", ""))
        recruiter_email = str(app.get("recruiter_email", "")).lower().strip()
        title = _norm(app.get("title", ""))
        app_urls = {str(app.get("job_url", "")).strip(), str(app.get("external_job_url", "")).strip()}
        app_urls = {url for url in app_urls if url}
        app_job_id = str(app.get("job_id", "")).strip()

        if app_urls & email_urls:
            return MatchResult(index=index, confidence=1.0, reasons=["exact_url"])

        if app_job_id and app_job_id in email_job_ids:
            return MatchResult(index=index, confidence=1.0, reasons=["job_id"])

        company_compact = company.replace(" ", "")
        company_pattern = rf"(?<![a-z0-9]){re.escape(company)}(?![a-z0-9])" if company else ""
        if company and company != "unknown" and len(company_compact) >= 5 and re.search(company_pattern, text):
            score += 0.50
            reasons.append("company")
            anchor_found = True
            if re.search(company_pattern, subject) or re.search(company_pattern, sender_text):
                score += 0.08
                reasons.append("company_subject_or_sender")
        elif sender_domain and company and len(company_compact) >= 5 and company_compact in sender_domain:
            score += 0.45
            reasons.append("sender_domain")
            anchor_found = True
        elif sender_domain and company and len(company_compact) >= 5 and _similarity(sender_domain, company_compact) >= 0.82:
            score += 0.35
            reasons.append("sender_domain_fuzzy")
            anchor_found = True

        if recruiter_email and recruiter_email == record.sender_email:
            score += 0.50
            reasons.append("recruiter_email")
            anchor_found = True
        elif recruiter_email and sender_domain and sender_domain == _domain(recruiter_email):
            score += 0.25
            reasons.append("recruiter_domain")
            anchor_found = True

        if recruiter_name and recruiter_name != "unknown" and recruiter_name in text:
            score += 0.30
            reasons.append("recruiter_name")
            anchor_found = True

        title_words = [word for word in title.split() if len(word) > 3]
        if title and len(title.replace(" ", "")) >= 6 and re.search(rf"(?<![a-z0-9]){re.escape(title)}(?![a-z0-9])", text):
            score += 0.15
            reasons.append("job_title_exact")

        title_hits = sum(1 for word in title_words[:6] if word in text)
        if title_hits:
            score += min(0.2, title_hits * 0.05)
            reasons.append("job_title")
        elif title and _similarity(title, subject) >= 0.72:
            score += 0.12
            reasons.append("job_title_fuzzy_subject")

        application_date = _parse_date(app.get("application_date", ""))
        if application_date and record.date:
            days_apart = (record.date - application_date).days
            if 0 <= days_apart <= 45:
                score += 0.1
                reasons.append("recent_application")

        if anchor_found and score > 0 and (best is None or score > best.confidence):
            best = MatchResult(index=index, confidence=min(score, 1.0), reasons=reasons)

    return best
