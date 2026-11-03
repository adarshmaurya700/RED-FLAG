"""Minimise consumer data at ingestion. This is a control, not a compliance certificate."""

import re
from urllib.parse import urlsplit, urlunsplit

PII_KEYS = {
    "username",
    "user",
    "author",
    "name",
    "full_name",
    "phone_number",
    "phone",
    "email",
    "exact_street_address",
    "address",
    "voice_biometrics",
    "audio",
    "avatar",
    "user_id",
    "ip_address",
}
PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    "phone_number": re.compile(
        r"(?<!\d)(?:\+91[\s-]?|0091[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"
    ),
    "username": re.compile(r"(?<!\w)(?:u/[A-Za-z0-9_-]+|@[A-Za-z0-9_]{2,})"),
    "exact_street_address": re.compile(
        r"(?i)\b(?:flat|house|plot|apartment|door|room)\s*(?:no\.?\s*)?[A-Za-z0-9/-]+(?:,?\s+[A-Za-z][A-Za-z .-]*){0,2}(?:road|street|lane|society|nagar|building)\b|\b\d{1,4}[, ]+(?:[A-Za-z]+[ .]){1,4}(?:Road|Street|Lane)\b"
    ),
    "personal_name": re.compile(
        r"(?i)\b(?:my name is|patient name\s*[:=]|name\s*[:=])\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}"
    ),
}


def scrub_text(text: str) -> tuple[str, list[str]]:
    redacted = []
    for name, pattern in PATTERNS.items():
        text, count = pattern.subn(f"[REDACTED {name.upper()}]", text)
        if count:
            redacted.append(name)
    # Preserve only the coarse PIN prefix when consumers include a full PIN.
    text = re.sub(r"(?<![.\d])\b([1-9]\d{2})\d{3}\b", r"\1***", text)
    return text, redacted


def safe_source_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            return ""
        path = re.sub(
            r"/(?:user|users|u|profile)/[^/]+",
            "/profile/redacted",
            parts.path,
            flags=re.I,
        )
        # Video IDs are retained; arbitrary query parameters and tracking identifiers are discarded.
        query = ""
        if parts.hostname in {"youtube.com", "www.youtube.com"}:
            match = re.search(r"(?:^|&)v=([A-Za-z0-9_-]{6,20})(?:&|$)", parts.query)
            if match:
                query = f"v={match.group(1)}"
        return urlunsplit((parts.scheme, parts.netloc, path, query, ""))
    except ValueError:
        return ""


def scrub_payload(payload: dict) -> tuple[dict, list[str]]:
    fields: set[str] = set()

    def walk(value):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key.lower() in PII_KEYS:
                    fields.add(key.lower())
                elif key == "source_url":
                    result[key] = safe_source_url(str(item))
                elif key == "pin_code_prefix":
                    prefix = str(item)[:3] if item is not None else None
                    result[key] = (
                        prefix if prefix and re.fullmatch(r"\d{3}", prefix) else None
                    )
                else:
                    result[key] = walk(item)
            return result
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, str):
            cleaned, found = scrub_text(value)
            fields.update(found)
            return cleaned
        return value

    return walk(payload), sorted(fields)
