import asyncio
import hashlib
import json
import re
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select, text as sql_text
from app.config import get_settings
from app.models.database import (
    Session,
    ScanJob,
    CaseFile,
    Evidence,
    Product,
    Regulation,
    Snapshot,
    AuditEvent,
)
from app.models.schemas import ScanRequest, Signal, SubScores, utcnow
from app.ingestion.brightdata_scraper import collect_sources
from app.ingestion.dpdpa_scrubber import scrub_payload, scrub_text
from app.nlp_engine.hinglish_extractor import extract_entities, TransformerFusion
from app.nlp_engine.recam_causality import extract_causality
from app.triage_engine.risk_scorer import risk_score, velocity, evidence_subscores
from app.triage_engine.tri_vector_classifier import classify
from app.triage_engine.cognee_graph import (
    persist_product_edges,
    graph_view,
    sync_cognee,
)
from app.triggerware.foscos_schedule1 import ensure_packets


def product_key(request: ScanRequest) -> str:
    return hashlib.sha256(
        (
            request.brand.strip().casefold()
            + "|"
            + request.product_name.strip().casefold()
        ).encode()
    ).hexdigest()[:24]


async def process_scan(identifier: str):
    async with Session() as session:
        job = await session.get(ScanJob, identifier)
        if not job or job.state not in {"queued", "running"}:
            return
        request = ScanRequest(**job.request)
        job.state, job.updated_at = "running", utcnow()
        await session.commit()
    try:
        raw, outcomes = await collect_sources(request)
        # Publisher reviews never enter complaint, clinical, attribution or risk paths.
        source_findings = [
            item["finding"]
            for item in raw
            if item.get("record_kind") == "source_finding"
        ]
        raw = [item for item in raw if item.get("record_kind") != "source_finding"]
        terms = [
            term.casefold()
            for term in re.findall(r"[\w]+", request.product_name + " " + request.brand)
            if len(term) > 2
        ]
        relevant = [
            item
            for item in raw
            if any(term in item.get("text", "").casefold() for term in terms)
        ]
        cleaned = []
        warnings = []
        for index, item in enumerate(relevant[:90]):
            data, fields = scrub_payload(item)
            content = data["text"]
            entities = extract_entities(content)
            method = "rules-v1"
            item_warnings = []
            if get_settings().gemini_api_key and index < 8:
                try:
                    from app.nlp_engine.gemini_adapter import gemini_extract

                    extraction, model = await gemini_extract(content)
                    # Deterministic catalog remains the authority for severity weights.
                    known = {(e.kind, e.normalized) for e in entities}
                    for entity in extraction.entities:
                        if (entity.kind, entity.normalized) not in known:
                            entity.severity = 0
                            entity.normalized = scrub_text(entity.normalized)[0]
                            entities.append(entity)
                    method += " + " + model
                except Exception:
                    item_warnings.append(
                        "Gemini unavailable or invalid output; deterministic extraction used."
                    )
            if get_settings().nlp_mode == "transformers":
                try:
                    fusion = TransformerFusion(
                        get_settings().hf_hinglish_model,
                        get_settings().hf_indic_model,
                        get_settings().comet_model,
                    )
                    embeddings = await asyncio.to_thread(fusion.embeddings, content)
                    inferences = await asyncio.to_thread(fusion.commonsense, content)
                    method += " + local-encoder-fusion"
                    item_warnings.append(
                        f"Context embeddings: {len(embeddings)}; commonsense hypotheses: {len(inferences)}. Hypotheses do not establish clinical facts."
                    )
                except Exception:
                    item_warnings.append(
                        "Local model weights unavailable; deterministic extraction used."
                    )
            signal = Signal(
                id=str(uuid4()),
                platform=data["platform"],
                source_url=data.get("source_url", ""),
                timestamp=data["timestamp"],
                product_name=request.product_name,
                text=content,
                evidence_type=data.get("evidence_type", "complaint"),
                entities=entities,
                clinical=extract_causality(content),
                extraction_method=method,
                redacted_fields=sorted(set(fields + item.get("redacted_fields", []))),
                warnings=item_warnings,
            )
            cleaned.append(signal)
        case_id = None
        async with Session() as session:
            if cleaned:
                key = product_key(request)
                if session.bind.dialect.name == "postgresql":
                    await session.execute(
                        sql_text("SELECT pg_advisory_xact_lock(:key)"),
                        {"key": int(key[:15], 16)},
                    )
                case_id = "LIVE-" + key[:12].upper()
                case = await session.get(CaseFile, case_id)
                now = utcnow()
                if not case:
                    data = {
                        "id": case_id,
                        "title": request.product_name,
                        "subtitle": "Live product scan",
                        "product_name": request.product_name,
                        "brand_name": request.brand or "Brand not established",
                        "synthetic": False,
                        "products": [
                            {
                                "name": request.product_name,
                                "brand": request.brand or "Unresolved",
                            }
                        ],
                        "batches": [],
                        "cities": [],
                        "status": "investigating",
                        "summary": "Public signals collected for analyst review. Source reports are allegations unless corroborated.",
                        "created_at": now.isoformat(),
                    }
                    case = CaseFile(
                        id=case_id,
                        product_key=key,
                        title=request.product_name,
                        data=data,
                        risk_score=0,
                        synthetic=False,
                    )
                    session.add(case)
                    await session.flush()
                    product = Product(
                        id="P-" + key,
                        case_id=case_id,
                        brand=request.brand or "Unresolved",
                        name=request.product_name,
                        data={},
                    )
                    session.add(product)
                    await persist_product_edges(session, product)
                for signal in cleaned:
                    signal.case_id = case_id
                    fingerprint = hashlib.sha256(
                        (key + signal.source_url + signal.text).encode()
                    ).hexdigest()
                    if not await session.scalar(
                        select(Evidence.id).where(Evidence.fingerprint == fingerprint)
                    ):
                        session.add(
                            Evidence(
                                id=signal.id,
                                case_id=case_id,
                                fingerprint=fingerprint,
                                timestamp=signal.timestamp,
                                data=signal.model_dump(mode="json"),
                            )
                        )
                await session.flush()
                await reassess_case(session, case)
                if get_settings().graph_backend == "cognee":
                    try:
                        await sync_cognee(await graph_view(session, case_id))
                    except Exception:
                        warnings.append(
                            "Cognee sync unavailable; durable NetworkX-compatible graph retained."
                        )
            job = await session.get(ScanJob, identifier)
            successful = sum(
                value["status"] in {"ok", "empty"} for value in outcomes.values()
            )
            job.state = (
                "completed"
                if successful == len(outcomes)
                else "partial"
                if successful or source_findings
                else "failed"
            )
            job.results = {
                "sources": outcomes,
                "source_findings": source_findings,
                "collected_count": len(raw),
                "relevant_count": len(cleaned),
                "case_ids": [case_id] if case_id else [],
                "warnings": warnings,
                "message": (
                    "Source reviews found; no complaint investigation was created."
                    if source_findings
                    else "No relevant evidence found."
                )
                if not cleaned
                else "Evidence collected and assessed.",
            }
            job.updated_at = utcnow()
            await session.commit()
    except asyncio.CancelledError:
        raise
    except Exception:
        async with Session() as session:
            job = await session.get(ScanJob, identifier)
            if job:
                job.state, job.updated_at = "failed", utcnow()
                job.results = {
                    "message": "Processing failed. Retry the scan; no fabricated results were inserted.",
                    "case_ids": [],
                }
                await session.commit()


async def reassess_case(session, case: CaseFile):
    if case.synthetic:
        return
    now = utcnow()
    rows = (
        await session.scalars(select(Evidence).where(Evidence.case_id == case.id))
    ).all()
    signals = [row.data for row in rows]
    complaints = [
        signal
        for signal in signals
        if signal["evidence_type"] in {"complaint", "support"}
    ]
    from datetime import datetime

    def date(signal):
        return datetime.fromisoformat(signal["timestamp"].replace("Z", "+00:00"))

    current = sum(now - timedelta(hours=48) <= date(s) <= now for s in complaints)
    prior = sum(
        now - timedelta(hours=96) <= date(s) < now - timedelta(hours=48)
        for s in complaints
    )
    baseline = bool(prior) or bool(
        await session.scalar(
            select(Snapshot.id)
            .where(
                Snapshot.case_id == case.id,
                Snapshot.captured_at <= now - timedelta(hours=48),
            )
            .limit(1)
        )
    )
    growth = velocity(current, prior if baseline else None)
    records = [
        row.data
        for row in (
            await session.scalars(
                select(Regulation).where(Regulation.case_id == case.id)
            )
        ).all()
    ]
    scores, policy = evidence_subscores(signals, records, growth, current)
    attribution = classify(signals)
    from app.ingestion.regulatory_hub import packaging_claim_flags

    claim_flags = packaging_claim_flags(" ".join(signal["text"] for signal in signals))
    assessment = risk_score(scores, growth)
    cities = sorted(
        {s["geography"]["city"] for s in signals if s.get("geography", {}).get("city")}
    )
    history = case.data.get("score_history", [])[-11:] + [
        {"label": now.strftime("%H:%M"), "risk": assessment["score"]}
    ]
    case.data = {
        **case.data,
        "risk_score": assessment["score"],
        "sub_scores": scores.model_dump(),
        "attribution": attribution["attribution"],
        "dominant_vector": attribution["dominant_vector"],
        "attribution_reasons": attribution["reasons"],
        "claim_flags": claim_flags,
        "delta_velocity_48h": growth,
        "complaint_count_48h": current,
        "cities": cities,
        "assessment": {
            **assessment,
            "evidence_policy": policy,
            "baseline_available": baseline,
        },
        "score_history": history,
        "updated_at": now.isoformat(),
    }
    case.risk_score, case.updated_at = assessment["score"], now
    session.add(
        Snapshot(
            id=str(uuid4()),
            case_id=case.id,
            captured_at=now,
            complaint_count_48h=current,
            risk_score=case.risk_score,
            data=assessment,
        )
    )
    session.add(
        AuditEvent(
            id=str(uuid4()),
            case_id=case.id,
            event="case_reassessed",
            data={"score": case.risk_score, "policy": assessment["policy_version"]},
        )
    )
    await ensure_packets(session, case.data)
