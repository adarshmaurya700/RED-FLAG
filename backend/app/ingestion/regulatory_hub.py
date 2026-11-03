"""Strict regulator schemas with JSON/CSV/HTML-table/PDF-text import adapters."""

import csv
import hashlib
import io
import json
import re
from html.parser import HTMLParser
from app.ingestion.dpdpa_scrubber import scrub_text, safe_source_url
from app.models.schemas import RegulatoryRecord

SOURCES = {"foscos", "pvpi", "ayush", "food_safety_connect", "nch", "bis"}
SUPPORTED_LANGUAGES = {"en", "hi", "bn", "mr", "ta", "te", "gu", "kn", "ml", "pa", "or"}
ALIASES = {
    "license_no": "fssai_license_no",
    "fssai_license_number": "fssai_license_no",
    "license_number": "fssai_license_no",
    "fbo": "fbo_name",
    "brand": "brand_name",
    "batch": "batch_lot_no",
    "reason": "reason_for_recall",
    "date": "start_date",
    "category": "food_category_code",
    "standard": "is_standard",
}


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], [], []
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        if tag in {"td", "th"}:
            self.cell, self.in_cell = [], True

    def handle_data(self, data):
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"}:
            self.row.append(" ".join("".join(self.cell).split()))
            self.in_cell = False
        if tag == "tr" and self.row:
            self.rows.append(self.row)


def normalized_key(key: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
    return ALIASES.get(normalized, normalized)


def parse_records(
    content: bytes, format: str, source: str, source_url: str = ""
) -> list[RegulatoryRecord]:
    if source not in SOURCES:
        raise ValueError("Unknown regulatory source")
    if len(content) > 5_000_000:
        raise ValueError("Import must be at most 5 MB")
    if format == "json":
        raw = json.loads(content)
        rows = raw.get("records", [raw]) if isinstance(raw, dict) else raw
    elif format == "csv":
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    elif format == "html":
        parser = TableParser()
        parser.feed(content.decode("utf-8"))
        if len(parser.rows) < 2:
            raise ValueError(
                "No structured regulatory table found; use JSON/CSV import"
            )
        rows = [dict(zip(parser.rows[0], row)) for row in parser.rows[1:]]
    elif format == "pdf":
        from pypdf import PdfReader

        text = "\n".join(
            page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages
        )
        blocks = re.split(r"\n\s*\n", text)
        rows = []
        for block in blocks:
            pairs = [line.split(":", 1) for line in block.splitlines() if ":" in line]
            if any(normalized_key(key) == "fbo_name" for key, _ in pairs):
                rows.append({key: value.strip() for key, value in pairs})
        if not rows:
            raise ValueError(
                "PDF has no extractable structured recall fields; import an accompanying JSON/CSV or manually transcribe the official record"
            )
    else:
        raise ValueError("Supported formats: json, csv, html, pdf")
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError("Import must contain at most 500 records")
    output = []
    for row in rows:
        data = {
            normalized_key(key): value
            for key, value in row.items()
            if value is not None and value != ""
        }
        data["source"] = source
        data["source_url"] = safe_source_url(data.get("source_url", source_url))
        data.setdefault(
            "id",
            "REG-"
            + hashlib.sha256(
                json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()[:20],
        )
        if "food_category_code" in data:
            data["food_category_code"] = str(data["food_category_code"]).zfill(2)
        for key in ("reason_for_recall",):
            if key in data:
                data[key] = scrub_text(str(data[key]))[0]
        for key in ("start_date", "termination_date"):
            if key in data and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data[key])):
                data[key] += "T00:00:00Z"
        if data.get("language", "en") not in SUPPORTED_LANGUAGES:
            raise ValueError("Unsupported language code")
        record = RegulatoryRecord.model_validate(data)
        if source == "ayush":
            record.clinical_cues = sorted(
                set(record.clinical_cues + ayush_cues(record.reason_for_recall))
            )
        output.append(record)
    return output


def packaging_claim_flags(text: str) -> list[dict]:
    return (
        [
            {
                "claim": "FSSAI Approved",
                "status": "potential_advertising_violation",
                "requires_review": True,
                "basis": "FSS (Advertising and Claims) Regulations, 2018",
                "source_url": "https://www.fssai.gov.in/cms/advertisements-and-claims.php",
            }
        ]
        if re.search(r"\bfssai\s+approved\b", text, re.I)
        else []
    )


def ayush_cues(text: str) -> list[str]:
    return [
        label
        for label, pattern in [
            ("suspected HILI", r"jaundice|liver|hepatotoxic|पीलिया"),
            ("heavy metals", r"lead|arsenic|mercury"),
            ("suspected drug spiking", r"steroid|nsaid"),
            (
                "misleading advertisement",
                r"cure.all|guaranteed cure|misleading|objectionable",
            ),
        ]
        if re.search(pattern, text, re.I)
    ]
