"""Source-authored reviews are references, never consumer or regulatory signals."""

from datetime import datetime
from typing import Literal
from pydantic import Field, field_validator, model_validator, AwareDatetime
from app.models.schemas import StrictModel
from urllib.parse import urlsplit

SourceName = Literal["trustified", "foodpharmer"]
FindingOutcome = Literal["pass", "fail", "recommended", "unknown"]


def public_link(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.port not in (None, 443)
    ):
        raise ValueError("Expected a public HTTPS proof link")
    import ipaddress

    try:
        ipaddress.ip_address(parts.hostname)
    except ValueError:
        if "." not in parts.hostname or parts.hostname.endswith(
            (".local", ".localhost")
        ):
            raise ValueError("Invalid proof hostname")
    else:
        raise ValueError("IP addresses are not proof links")
    return value


class ProofLink(StrictModel):
    label: str = Field(max_length=120)
    url: str
    _link = field_validator("url")(public_link)


class FindingChange(StrictModel):
    changed_at: AwareDatetime
    outcome: FindingOutcome
    testing_status: str
    content_hash: str


class SourceFinding(StrictModel):
    id: str = Field(pattern=r"^[a-f0-9]{24}$")
    source: SourceName
    source_url: str
    product_name: str = Field(min_length=1, max_length=240)
    brand: str | None = Field(default=None, max_length=240)
    category: str | None = Field(default=None, max_length=160)
    outcome: FindingOutcome = "unknown"
    testing_status: Literal["passed", "failed", "expired", "unknown"] = "unknown"
    review_method: Literal[
        "independent_test", "label_reviewed", "reported_lab_test", "reviewed", "unknown"
    ] = "unknown"
    batch: str | None = Field(default=None, max_length=160)
    manufactured: str | None = Field(default=None, max_length=100)
    expires: str | None = Field(default=None, max_length=100)
    published_at: str | None = None
    last_verified_at: str | None = None
    laboratory: str | None = Field(default=None, max_length=160)
    criteria: list[str] = Field(default_factory=list, max_length=12)
    excerpt: str = Field(default="", max_length=350)
    proof_links: list[ProofLink] = Field(default_factory=list, max_length=12)
    fetched_at: AwareDatetime
    first_seen_at: AwareDatetime
    updated_at: AwareDatetime
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    revision: int = Field(default=1, ge=1)
    history: list[FindingChange] = Field(default_factory=list, max_length=5)
    availability: Literal["available", "unavailable"] = "available"

    @field_validator("source_url")
    @classmethod
    def source_link(cls, value):
        public_link(value)
        if urlsplit(value).hostname not in {"www.trustified.in", "foodpharmer.health"}:
            raise ValueError("Unknown finding publisher")
        return value

    @model_validator(mode="after")
    def publisher_matches(self):
        if (
            urlsplit(self.source_url).hostname
            != {"trustified": "www.trustified.in", "foodpharmer": "foodpharmer.health"}[
                self.source
            ]
        ):
            raise ValueError("Finding source does not match its publisher")
        return self


class SourceHealth(StrictModel):
    status: Literal["ok", "partial", "blocked", "error", "unavailable"] = "unavailable"
    last_attempt_at: AwareDatetime | None = None
    last_success_at: AwareDatetime | None = None
    discovered: int = Field(default=0, ge=0)
    checked: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    pending_urls: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list, max_length=20)


class SourceCatalog(StrictModel):
    schema_version: Literal[1] = 1
    generated_at: AwareDatetime
    sources: dict[SourceName, SourceHealth]
    items: list[SourceFinding] = Field(default_factory=list, max_length=5000)

    @model_validator(mode="after")
    def catalog_contract(self):
        if set(self.sources) != {"trustified", "foodpharmer"}:
            raise ValueError("Both source health records are required")
        if len({item.id for item in self.items}) != len(self.items) or len(
            {item.source_url for item in self.items}
        ) != len(self.items):
            raise ValueError("Duplicate finding identifiers or URLs")
        return self


class FindingView(SourceFinding):
    stale: bool


class SourceFindingsResponse(StrictModel):
    items: list[FindingView]
    total: int
    generated_at: datetime
    sources: dict[str, dict]
    catalog_origin: str
    notice: str = "Source-authored findings for review. Batch-specific tests and nutrition recommendations are not regulator decisions or safety guarantees."
