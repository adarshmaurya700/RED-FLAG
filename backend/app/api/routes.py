import hashlib
import hmac
from datetime import datetime, timedelta
from uuid import uuid4
from typing import Annotated
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import Response
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.models.database import (
    get_session,
    CaseFile,
    Evidence,
    ScanJob,
    Regulation,
    ActionPacket,
    Grievance,
    AuditEvent,
    Snapshot,
)
from app.models.schemas import (
    CaseSummary,
    ScanRequest,
    GrievanceUpdate,
    QueryRequest,
    PacketRequest,
    RecallDecisionRequest,
    WeeklyReportRequest,
    utcnow,
)
from app.ingestion.brightdata_scraper import validate_public_url
from app.ingestion.dpdpa_scrubber import scrub_payload, scrub_text, safe_source_url
from app.ingestion.regulatory_hub import parse_records, packaging_claim_flags
from app.pipeline import process_scan, reassess_case
from app.triage_engine.cognee_graph import graph_view
from app.triggerware.foscos_schedule1 import ensure_packets, render_pdf, KINDS
from app.triggerware.nodal_interceptor import grievance_view


async def authenticate(authorization: str = Header(default="")):
    key = get_settings().internal_api_key
    if key and not hmac.compare_digest(
        authorization.encode(), ("Bearer " + key).encode()
    ):
        raise HTTPException(401, "Invalid internal API credentials")


router = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticate)])
DB = Annotated[AsyncSession, Depends(get_session)]


@router.get("/reference-cases")
async def reference_cases(q: str = Query("", max_length=160)):
    from app.reference_cases import load_reference_cases, search_reference_cases

    catalog = load_reference_cases()
    return {
        "items": search_reference_cases(q),
        "reviewed_at": catalog["reviewed_at"],
        "notice": catalog["notice"],
    }


@router.get("/reference-cases/{identifier}")
async def reference_case(identifier: str):
    from app.reference_cases import load_reference_cases

    catalog = load_reference_cases()
    case = next((item for item in catalog["cases"] if item["id"] == identifier), None)
    if not case:
        raise HTTPException(404, "Reference case not found")
    return {**case, "reviewed_at": catalog["reviewed_at"], "notice": catalog["notice"]}


async def case_or_404(session, identifier):
    case = await session.get(CaseFile, identifier)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


def summary(case):
    return CaseSummary.model_validate(
        {key: case.data[key] for key in CaseSummary.model_fields if key in case.data}
    )


@router.get("/telemetry")
async def telemetry(session: DB):
    cases = (await session.scalars(select(CaseFile))).all()
    grievances = (await session.scalars(select(Grievance))).all()
    count = await session.scalar(select(func.count()).select_from(Evidence))
    return {
        "active_cases": len(cases),
        "high_risk_cases": sum(c.risk_score >= 70 for c in cases),
        "velocity_alerts": sum(c.data["delta_velocity_48h"] >= 0.5 for c in cases),
        "pending_grievances": sum(g.status == "open" for g in grievances),
        "evidence_count": count,
        "privacy_status": "Edge scrubber enabled",
        "synthetic_cases": sum(c.synthetic for c in cases),
        "live_cases": sum(not c.synthetic for c in cases),
        "last_updated": max(
            (c.data["updated_at"] for c in cases), default=utcnow().isoformat()
        ),
        "providers": {
            "tinyfish": bool(get_settings().tinyfish_api_key),
            "brightdata": bool(get_settings().brightdata_api_key),
            "gemini": bool(get_settings().gemini_api_key),
            "sarvam": bool(get_settings().sarvam_api_key),
        },
        "task_mode": get_settings().task_mode,
    }


@router.get("/cases", response_model=list[CaseSummary])
async def cases(
    session: DB,
    mode: str = Query("all", pattern="^(all|demo|live)$"),
    q: str = Query("", max_length=160),
    vector: str = Query("all", pattern="^(all|batch|counterfeit|dark_store|review)$"),
):
    rows = (
        await session.scalars(select(CaseFile).order_by(CaseFile.risk_score.desc()))
    ).all()
    return [
        summary(row)
        for row in rows
        if (mode == "all" or row.synthetic == (mode == "demo"))
        and (vector == "all" or row.data["dominant_vector"] == vector)
        and q.casefold()
        in (row.title + row.data["product_name"] + row.data["brand_name"]).casefold()
    ]


@router.get("/cases/{identifier}")
async def case_detail(identifier: str, session: DB):
    case = await case_or_404(session, identifier)
    records = (
        await session.scalars(
            select(Regulation).where(Regulation.case_id == identifier)
        )
    ).all()
    packets = (
        await session.scalars(
            select(ActionPacket)
            .where(ActionPacket.case_id == identifier)
            .order_by(ActionPacket.created_at.desc())
        )
    ).all()
    grievances = (
        await session.scalars(select(Grievance).where(Grievance.case_id == identifier))
    ).all()
    events = (
        await session.scalars(
            select(AuditEvent)
            .where(AuditEvent.case_id == identifier)
            .order_by(AuditEvent.timestamp.desc())
            .limit(30)
        )
    ).all()
    return {
        **case.data,
        "regulatory_records": [r.data for r in records],
        "packets": [
            {
                "id": p.id,
                "kind": p.kind,
                "version": p.version,
                "title": p.data["content"]["title"],
                "created_at": p.created_at.isoformat(),
            }
            for p in packets
        ],
        "grievances": [grievance_view(g) for g in grievances],
        "audit_events": [
            {"event": e.event, "timestamp": e.timestamp.isoformat(), "data": e.data}
            for e in events
        ],
    }


@router.get("/cases/{identifier}/evidence")
async def evidence(
    identifier: str,
    session: DB,
    platform: str = Query("all", max_length=60),
    kind: str = Query("all", max_length=30),
    q: str = Query("", max_length=160),
    offset: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
):
    await case_or_404(session, identifier)
    rows = (
        await session.scalars(
            select(Evidence)
            .where(Evidence.case_id == identifier)
            .order_by(Evidence.timestamp.desc())
        )
    ).all()
    signals = [row.data for row in rows]
    selected = [
        s
        for s in signals
        if (platform == "all" or s["platform"] == platform)
        and (kind == "all" or s["evidence_type"] == kind)
        and q.casefold() in s["text"].casefold()
    ]
    return {
        "items": selected[offset : offset + limit],
        "total": len(selected),
        "platforms": sorted({s["platform"] for s in signals}),
    }


@router.get("/cases/{identifier}/graph")
async def graph(identifier: str, session: DB):
    await case_or_404(session, identifier)
    return await graph_view(session, identifier)


@router.post("/scans", status_code=202)
async def start_scan(
    payload: ScanRequest,
    session: DB,
    background: BackgroundTasks,
    idempotency_key: str | None = Header(None, max_length=128),
):
    for url in payload.product_urls:
        try:
            validate_public_url(url)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    clean, fields = scrub_payload(payload.model_dump())
    clean["product_urls"] = [safe_source_url(url) for url in clean["product_urls"]]
    clean = ScanRequest(**clean).model_dump()
    if idempotency_key:
        old = await session.scalar(
            select(ScanJob).where(ScanJob.idempotency_key == idempotency_key)
        )
        if old:
            if old.request != clean:
                raise HTTPException(
                    409, "Idempotency key was already used for a different scan"
                )
            return {"id": old.id, "state": old.state}
    # Short-lived result cache avoids repeated outbound queries from double clicks.
    recent = (
        await session.scalars(
            select(ScanJob)
            .where(
                ScanJob.created_at >= utcnow() - timedelta(minutes=5),
                ScanJob.state.in_(["queued", "running", "completed", "partial"]),
            )
            .order_by(ScanJob.created_at.desc())
            .limit(30)
        )
    ).all()
    for old in recent:
        if old.request == clean:
            return {"id": old.id, "state": old.state, "cached": True}
    active = await session.scalar(
        select(func.count())
        .select_from(ScanJob)
        .where(ScanJob.state.in_(["queued", "running"]))
    )
    if active >= get_settings().max_concurrent_scans:
        raise HTTPException(
            429, "Scan capacity reached. Wait for an active scan to finish."
        )
    job = ScanJob(
        id=str(uuid4()),
        request=clean,
        idempotency_key=idempotency_key,
        results={"redacted_fields": fields},
    )
    session.add(job)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            409, "Concurrent duplicate request; retry with the same idempotency key"
        )
    if get_settings().task_mode == "celery":
        from app.worker import scan_task

        try:
            await __import__("asyncio").to_thread(scan_task.delay, job.id)
        except Exception:
            job.state, job.results = (
                "failed",
                {"message": "Worker queue unavailable. Retry when Redis is ready."},
            )
            await session.commit()
            raise HTTPException(503, "Worker queue unavailable")
    else:
        background.add_task(process_scan, job.id)
    return {"id": job.id, "state": "queued"}


@router.get("/scans/{identifier}")
async def scan_status(identifier: str, session: DB):
    job = await session.get(ScanJob, identifier)
    if not job:
        raise HTTPException(404, "Scan not found")
    return {
        "id": job.id,
        "state": job.state,
        "request": job.request,
        "results": job.results,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


@router.post("/cases/{identifier}/packets")
async def generate_packet(identifier: str, payload: PacketRequest, session: DB):
    case = await case_or_404(session, identifier)
    if (
        payload.kind not in KINDS.get(case.data["dominant_vector"], [])
        or case.risk_score < 70
    ):
        raise HTTPException(
            409, "Risk threshold or attribution does not support this packet"
        )
    packets = await ensure_packets(session, case.data)
    await session.commit()
    packet = next(p for p in packets if p.kind == payload.kind)
    return {
        "id": packet.id,
        "version": packet.version,
        "kind": packet.kind,
        "data": packet.data,
    }


@router.get("/packets/{identifier}")
async def download_packet(
    identifier: str, session: DB, format: str = Query("json", pattern="^(json|pdf)$")
):
    packet = await session.get(ActionPacket, identifier)
    if not packet:
        raise HTTPException(404, "Packet not found")
    if format == "json":
        return {
            "id": packet.id,
            "version": packet.version,
            "content_hash": packet.content_hash,
            **packet.data,
        }
    return Response(
        render_pdf(packet.data),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="red-flag-{packet.case_id}-{packet.kind}-v{packet.version}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )


@router.patch("/grievances/{identifier}")
async def update_grievance(identifier: str, payload: GrievanceUpdate, session: DB):
    row = await session.get(Grievance, identifier)
    if not row:
        raise HTTPException(404, "Grievance not found")
    row.status = payload.status
    session.add(
        AuditEvent(
            id=str(uuid4()),
            case_id=row.case_id,
            event="grievance_" + payload.status,
            data={"grievance_id": row.id},
        )
    )
    await session.commit()
    return grievance_view(row)


@router.post("/cases/{identifier}/authority-queries")
async def authority_query(identifier: str, payload: QueryRequest, session: DB):
    case = await case_or_404(session, identifier)
    if payload.received_at.tzinfo is None or payload.received_at > utcnow():
        raise HTTPException(
            422, "Query receipt must have a timezone and cannot be in the future"
        )
    entry = {
        "id": str(uuid4()),
        "reference": scrub_text(payload.reference)[0],
        "received_at": payload.received_at.isoformat(),
        "due_at": (payload.received_at + timedelta(hours=24)).isoformat(),
        "status": "open",
    }
    case.data = {
        **case.data,
        "authority_queries": case.data.get("authority_queries", []) + [entry],
    }
    session.add(
        AuditEvent(
            id=str(uuid4()),
            case_id=identifier,
            event="authority_query_received",
            data=entry,
        )
    )
    await session.commit()
    return entry


@router.patch("/cases/{identifier}/authority-queries/{query_id}/responded")
async def query_responded(identifier: str, query_id: str, session: DB):
    case = await case_or_404(session, identifier)
    queries = [dict(item) for item in case.data.get("authority_queries", [])]
    query = next((item for item in queries if item.get("id") == query_id), None)
    if not query:
        raise HTTPException(404, "Authority query not found")
    query.update(status="responded", responded_at=utcnow().isoformat())
    case.data = {**case.data, "authority_queries": queries}
    session.add(
        AuditEvent(
            id=str(uuid4()),
            case_id=identifier,
            event="authority_query_responded",
            data={"query_id": query_id},
        )
    )
    await session.commit()
    return query


@router.post("/cases/{identifier}/recall-decision")
async def recall_decision(identifier: str, payload: RecallDecisionRequest, session: DB):
    case = await case_or_404(session, identifier)
    if case.data["dominant_vector"] != "batch" or case.risk_score < 70:
        raise HTTPException(
            409,
            "Recall workflow requires a factory-attributed case at risk 70 or above",
        )
    if payload.decision_at.tzinfo is None or payload.decision_at > utcnow():
        raise HTTPException(
            422, "Decision time must have a timezone and cannot be in the future"
        )
    if case.data.get("recall_workflow"):
        return case.data["recall_workflow"]
    workflow = {
        "decision_at": payload.decision_at.isoformat(),
        "notification_due_at": (payload.decision_at + timedelta(hours=24)).isoformat(),
        "next_weekly_status_due_at": (
            payload.decision_at + timedelta(days=7)
        ).isoformat(),
        "reports": [],
        "synthetic": case.synthetic,
        "external_submission": False,
    }
    case.data = {**case.data, "recall_workflow": workflow}
    session.add(
        AuditEvent(
            id=str(uuid4()),
            case_id=identifier,
            event="recall_decision_recorded",
            data={"decision_at": workflow["decision_at"], "synthetic": case.synthetic},
        )
    )
    await session.commit()
    return workflow


@router.post("/cases/{identifier}/weekly-status")
async def record_weekly_status(
    identifier: str, payload: WeeklyReportRequest, session: DB
):
    case = await case_or_404(session, identifier)
    workflow = case.data.get("recall_workflow")
    if not workflow:
        raise HTTPException(409, "Record a recall decision first")
    if payload.submitted_at.tzinfo is None or payload.submitted_at > utcnow():
        raise HTTPException(
            422, "Submission time must have a timezone and cannot be in the future"
        )
    report = payload.model_dump(mode="json")
    report["effectiveness_notes"] = scrub_text(report["effectiveness_notes"])[0]
    workflow = {
        **workflow,
        "reports": workflow.get("reports", []) + [report],
        "next_weekly_status_due_at": (
            payload.submitted_at + timedelta(days=7)
        ).isoformat(),
    }
    case.data = {**case.data, "recall_workflow": workflow}
    session.add(
        AuditEvent(
            id=str(uuid4()),
            case_id=identifier,
            event="weekly_status_recorded",
            data={"submitted_at": report["submitted_at"]},
        )
    )
    await session.commit()
    return workflow


@router.post("/regulatory/import")
async def import_regulatory(
    session: DB,
    file: UploadFile = File(...),
    source: str = Query(...),
    format: str = Query("json"),
    case_id: str | None = Query(None),
):
    case = await case_or_404(session, case_id) if case_id else None
    if case and case.synthetic:
        raise HTTPException(
            409, "Live imports cannot modify synthetic demonstration cases"
        )
    try:
        records = parse_records(await file.read(5_000_001), format, source)
    except Exception:
        raise HTTPException(
            422,
            "Import failed strict source validation. Check the documented regulatory schema and required fields.",
        )
    count = 0
    for record in records:
        if record.synthetic:
            raise HTTPException(
                422,
                "Synthetic records must be loaded through the demo seed, not live imports",
            )
        if not await session.get(Regulation, record.id):
            session.add(
                Regulation(
                    id=record.id,
                    case_id=case_id,
                    source=record.source,
                    fssai_license_no=record.fssai_license_no,
                    data=record.model_dump(mode="json"),
                )
            )
            if (
                case_id
                and record.source == "food_safety_connect"
                and record.action_type == "Grievance"
            ):
                session.add(
                    Grievance(
                        id=record.id,
                        case_id=case_id,
                        received_at=record.start_date,
                        due_at=record.start_date + timedelta(days=15),
                        data={
                            "category": record.grievance_category or "Packaged Food",
                            "priority": case.risk_score >= 70,
                            "synthetic": False,
                            "description": record.reason_for_recall,
                        },
                    )
                )
            count += 1
    await session.flush()
    if case:
        await reassess_case(session, case)
    await session.commit()
    return {"imported": count, "duplicates": len(records) - count}


@router.post("/audio/transcribe")
async def audio_transcribe(
    file: UploadFile = File(...),
    provider: str = Query("sarvam"),
    language: str = Query("hi"),
    lawful_basis: str = Query(...),
):
    from app.nlp_engine.multimodal_asr import transcribe

    try:
        return await transcribe(
            await file.read(10_000_001),
            provider=provider,
            language=language,
            lawful_basis=lawful_basis,
        )
    except LookupError as exc:
        raise HTTPException(503, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception:
        raise HTTPException(
            502, "Transcription provider unavailable; audio has not been persisted"
        )
