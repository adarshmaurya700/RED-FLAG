from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


LicenseNumber = Annotated[str, Field(pattern=r"^\d{14}$")]
Score = Annotated[float, Field(ge=0, le=100)]
FoodCategory = Annotated[str, Field(pattern=r"^(0[1-9]|1[0-8]|99|100|101|102)$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SubScores(StrictModel):
    regulatory: Score = 0
    adverse_events: Score = 0
    live_web: Score = 0
    credibility: Score = 0


class Attribution(StrictModel):
    batch: float = Field(ge=0, le=1)
    counterfeit: float = Field(ge=0, le=1)
    dark_store: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def normalized(self):
        if abs(self.batch + self.counterfeit + self.dark_store - 1) > 0.00001:
            raise ValueError("Attribution must sum to 1")
        return self


class ClinicalCues(StrictModel):
    onset_latency_hours: float | None = Field(default=None, ge=0)
    symptom_duration_days: float | None = Field(default=None, ge=0)
    dechallenge_status: Literal["positive", "negative", "unknown"] = "unknown"
    rechallenge_status: Literal["positive", "negative", "unknown"] = "unknown"
    concomitant_products: list[str] = Field(default_factory=list)


class Entity(StrictModel):
    text: str
    kind: Literal["symptom", "hazard", "batch", "counterfeit", "location", "product"]
    normalized: str
    severity: float = Field(default=0, ge=0, le=100)


class Geography(StrictModel):
    city: str | None = None
    pin_code_prefix: str | None = Field(default=None, pattern=r"^\d{3}$")
    node_id: str | None = None
    node_name: str | None = None
    node_latitude: float | None = Field(default=None, ge=-90, le=90)
    node_longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_km: float | None = Field(default=None, ge=0, le=3)


class Signal(StrictModel):
    id: str
    case_id: str | None = None
    platform: str
    source_url: str = ""
    timestamp: datetime
    retrieved_at: datetime = Field(default_factory=utcnow)
    product_name: str
    text: str
    language: str = "en"
    channel: str = "public_web"
    evidence_type: Literal["complaint", "news", "video", "regulatory", "support"] = (
        "complaint"
    )
    verified_purchase: bool = False
    lab_evidence: Literal["none", "attachment", "verified"] = "none"
    synthetic: bool = False
    entities: list[Entity] = Field(default_factory=list)
    clinical: ClinicalCues = Field(default_factory=ClinicalCues)
    geography: Geography = Field(default_factory=Geography)
    extraction_method: str = "rules-v1"
    redacted_fields: list[str] = Field(default_factory=list)
    privacy_status: Literal["scrubbed", "synthetic"] = "scrubbed"
    warnings: list[str] = Field(default_factory=list)


class RegulatoryRecord(StrictModel):
    id: str
    source: Literal["foscos", "pvpi", "ayush", "food_safety_connect", "nch", "bis"]
    source_url: str = ""
    recall_id: str | None = None
    fbo_name: str
    fssai_license_no: LicenseNumber | None = None
    license_type: Literal["central", "state", "registration", "unknown"] = "unknown"
    brand_name: str = ""
    batch_lot_no: str | None = None
    food_category_code: FoodCategory | None = None
    recall_class: (
        Literal["Class I", "Class II", "Class III", "Market Withdrawal"] | None
    ) = None
    action_type: Literal[
        "FoSCoS Recall",
        "Section 36(3)(b) Prohibition Order",
        "Improvement Notice",
        "Advertising & Claims Notice",
        "Premises License Suspension",
        "Suspected ADR",
        "Misleading Advertisement",
        "Grievance",
        "BIS Recall",
    ]
    reason_for_recall: str
    start_date: datetime
    termination_date: datetime | None = None
    language: str = "en"
    is_standard: str | None = None
    grievance_category: (
        Literal[
            "Packaged Food", "Food Premises", "Online Aggregator / Delivery Platform"
        ]
        | None
    ) = None
    clinical_cues: list[str] = Field(default_factory=list)
    synthetic: bool = False


class ScanRequest(StrictModel):
    product_name: str = Field(min_length=2, max_length=160)
    brand: str = Field(default="", max_length=100)
    product_urls: list[str] = Field(default_factory=list, max_length=5)
    sources: list[Literal["reddit", "google_news", "tinyfish", "brightdata"]] = Field(
        default_factory=lambda: ["reddit", "google_news"]
    )

    @model_validator(mode="after")
    def valid_sources(self):
        self.product_name = " ".join(self.product_name.split())
        self.sources = list(dict.fromkeys(self.sources))
        if not self.sources or len(self.product_name) < 2:
            raise ValueError("Provide a product and at least one source")
        return self


class SourceOutcome(StrictModel):
    status: Literal["ok", "empty", "blocked", "unavailable", "error"]
    count: int = 0
    message: str = ""


class ScanState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class CaseSummary(StrictModel):
    id: str
    title: str
    subtitle: str
    product_name: str
    brand_name: str
    risk_score: Score
    sub_scores: SubScores
    attribution: Attribution
    dominant_vector: str
    delta_velocity_48h: float = Field(ge=0, le=1)
    complaint_count_48h: int = Field(ge=0)
    cities: list[str]
    synthetic: bool
    updated_at: datetime
    status: str = "investigating"


class PacketRequest(StrictModel):
    kind: Literal[
        "recall",
        "consumer_notice",
        "marketplace",
        "authentication",
        "lab_request",
        "dark_store",
    ]


class GrievanceUpdate(StrictModel):
    status: Literal["open", "resolved"]


class QueryRequest(StrictModel):
    reference: str = Field(min_length=1, max_length=120)
    received_at: datetime


class RecallDecisionRequest(StrictModel):
    decision_at: datetime


class WeeklyReportRequest(StrictModel):
    submitted_at: datetime
    distributed_units: int = Field(gt=0)
    recovered_units: int = Field(ge=0)
    effectiveness_notes: str = Field(min_length=1, max_length=1500)

    @model_validator(mode="after")
    def quantities(self):
        if self.recovered_units > self.distributed_units:
            raise ValueError("Recovered units cannot exceed distributed units")
        return self
