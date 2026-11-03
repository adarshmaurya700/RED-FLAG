"""Idempotent fictional scenarios. Relative timestamps keep the demo's windows useful."""

import asyncio
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select
from app.config import get_settings
from app.models.database import (
    Session,
    CaseFile,
    Product,
    Evidence,
    Regulation,
    Snapshot,
    Grievance,
    create_tables,
)
from app.models.schemas import SubScores, Signal, Geography, RegulatoryRecord, utcnow
from app.nlp_engine.hinglish_extractor import extract_entities
from app.nlp_engine.recam_causality import extract_causality
from app.triage_engine.risk_scorer import risk_score
from app.triage_engine.cognee_graph import persist_product_edges
from app.triggerware.foscos_schedule1 import ensure_packets

EVIDENCE = {
    "IND-FSSAI-01": [
        (
            "Amazon.in",
            "Mumbai",
            "Verified D2C pack, lot-MX-02. Khane ke 20 minutes baad hives aur gale me khujli. Stopped the product and symptoms subsided.",
            True,
            "complaint",
        ),
        (
            "Reddit",
            "Delhi",
            "Same batch lot-MX-02 in Delhi. Itchy throat and vomiting within 1 hour. Tried again and the hives returned.",
            False,
            "complaint",
        ),
        (
            "1mg",
            "Bengaluru",
            "lot-MX-02: bachche ko vomiting. Stopped the product and he got better. Symptoms lasted for 2 days.",
            True,
            "complaint",
        ),
        (
            "YouTube",
            "Pune",
            "Creator lab screen alleges ferbam residue in lot-MX-02. Accredited confirmatory testing is pending.",
            False,
            "video",
        ),
        (
            "Reddit",
            "Pune",
            "SnackLab chilli mix from the shared contract plant. Hives after 30 minutes. FSSAI manufacturing license 10012021000518.",
            False,
            "complaint",
        ),
    ],
    "IND-FSSAI-02": [
        (
            "Amazon.in",
            "Delhi",
            "Ek dum bekar protein hai, pet kharab ho gaya, nakli seal hai. Missing 3D hologram; QR code fails to scan. BulkWell Deals is an unauthorized third-party seller.",
            True,
            "complaint",
        ),
        (
            "Flipkart",
            "Mumbai",
            "Whey powder clumping in room-temperature water, residue remains. Spelling errors on tub. QR redirects to wrong domain.",
            True,
            "complaint",
        ),
        (
            "HealthKart",
            "Hyderabad",
            "Broken inner seal and blurry hologram on PeakFuel tub from an unverified seller. Pet kharab after 2 hours.",
            False,
            "complaint",
        ),
        (
            "YouTube",
            "Delhi",
            "Creator NMR screen alleges C3/C4 rice-syrup in BeeTheory honey from unauthorized seller BulkWell Deals. Laboratory confirmation pending.",
            False,
            "video",
        ),
        (
            "Reddit",
            "Mumbai",
            "Official D2C QR works; marketplace pack QR fails. Stopped the product and stomach symptoms got better.",
            False,
            "complaint",
        ),
    ],
}


async def seed():
    document = json.loads(
        (get_settings().data_directory / "scenarios.json").read_text(encoding="utf-8")
    )
    async with Session() as session:
        for original in document["cases"]:
            if await session.get(CaseFile, original["id"]):
                continue
            now = utcnow()
            data = {
                **original,
                "synthetic": True,
                "created_at": (now - timedelta(days=3)).isoformat(),
                "updated_at": now.isoformat(),
                "status": "investigating",
                "provenance": document["notice"],
                "seed_score_inputs": "Supplied assessed demonstration factors; representative evidence is not a complete complaint register.",
            }
            data["assessment"] = risk_score(
                SubScores(**data["sub_scores"]), data["delta_velocity_48h"]
            )
            data["risk_score"] = data["assessment"]["score"]
            data["score_history"] = [
                {"label": label, "risk": round(data["risk_score"] * fraction)}
                for label, fraction in [
                    ("-48h", 0.42),
                    ("-36h", 0.49),
                    ("-24h", 0.65),
                    ("-12h", 0.78),
                    ("Now", 1),
                ]
            ]
            case = CaseFile(
                id=data["id"],
                product_key=data["id"],
                title=data["title"],
                risk_score=data["risk_score"],
                synthetic=True,
                data=data,
            )
            session.add(case)
            await session.flush()
            for index, item in enumerate(data["products"]):
                product = Product(
                    id=f"{case.id}-P{index}",
                    case_id=case.id,
                    brand=item["brand"],
                    name=item["name"],
                    manufacturing_fssai_license_no=data.get("fbo", {}).get(
                        "license_no"
                    ),
                    supplier_id="demo-common-spice-supplier"
                    if case.id.endswith("01")
                    else None,
                    data=item,
                )
                session.add(product)
                await persist_product_edges(session, product)
            examples = EVIDENCE.get(case.id, [])
            if case.id.endswith("03"):
                examples = []
                for index in range(28):
                    node = data["dark_store_nodes"][index % 2]
                    text = f"{'Blinkit' if index % 2 == 0 else 'Zepto'} delivery at {node['name']}: {'sour curdled milk, khatta smell' if index % 3 else 'pest-damaged cartons and thawed produce'}. Report {index + 1} in the synthetic register."
                    examples.append(
                        (
                            "Blinkit" if index % 2 == 0 else "Zepto",
                            node["city"],
                            text,
                            True,
                            "complaint",
                        )
                    )
            for index, (platform, city, text, verified, kind) in enumerate(examples):
                geography = Geography(city=city)
                if case.id.endswith("03"):
                    node = data["dark_store_nodes"][index % 2]
                    geography = Geography(
                        city=city,
                        pin_code_prefix=node["pin_code_prefix"],
                        node_id=node["id"],
                        node_name=node["name"],
                        node_latitude=node["latitude"],
                        node_longitude=node["longitude"],
                        radius_km=node["radius_km"],
                    )
                signal = Signal(
                    id=f"{case.id}-E{index:03}",
                    case_id=case.id,
                    platform=platform,
                    source_url="",
                    timestamp=now - timedelta(hours=2 + index),
                    product_name=data["product_name"],
                    text=text,
                    language="hi-en" if index % 2 == 0 else "en",
                    evidence_type=kind,
                    verified_purchase=verified,
                    lab_evidence="attachment" if kind == "video" else "none",
                    synthetic=True,
                    entities=extract_entities(text),
                    clinical=extract_causality(text),
                    geography=geography,
                    privacy_status="synthetic",
                    extraction_method="synthetic + rules-v1",
                    warnings=["Synthetic example; no actual source URL."],
                )
                session.add(
                    Evidence(
                        id=signal.id,
                        case_id=case.id,
                        fingerprint=hashlib.sha256(signal.id.encode()).hexdigest(),
                        timestamp=signal.timestamp,
                        data=signal.model_dump(mode="json"),
                    )
                )
            if data.get("regulatory_action"):
                record = RegulatoryRecord(
                    id=f"{case.id}-REG",
                    source="foscos",
                    fbo_name=data.get("fbo", {}).get(
                        "name", "DailyDrop Local Distribution (synthetic)"
                    ),
                    fssai_license_no=data.get("fbo", {}).get("license_no"),
                    brand_name=data["brand_name"],
                    food_category_code=data.get("food_category_code", "01"),
                    action_type=data["regulatory_action"],
                    reason_for_recall="Synthetic advertising-claim review"
                    if case.id.endswith("01")
                    else "Synthetic premises cold-chain improvement notice",
                    start_date=now - timedelta(days=2),
                    synthetic=True,
                )
                session.add(
                    Regulation(
                        id=record.id,
                        case_id=case.id,
                        source=record.source,
                        fssai_license_no=record.fssai_license_no,
                        data=record.model_dump(mode="json"),
                    )
                )
            session.add(
                Snapshot(
                    id=f"{case.id}-SEED",
                    case_id=case.id,
                    captured_at=now,
                    complaint_count_48h=data["complaint_count_48h"],
                    risk_score=data["risk_score"],
                    data={
                        "seeded_assessment": True,
                        "velocity": data["delta_velocity_48h"],
                    },
                )
            )
            if case.id.endswith("01"):
                session.add(
                    Grievance(
                        id="FSC-DEMO-001",
                        case_id=case.id,
                        received_at=now - timedelta(days=3),
                        due_at=now + timedelta(days=12),
                        data={
                            "category": "Packaged Food",
                            "priority": True,
                            "synthetic": True,
                            "description": "Synthetic Food Safety Connect grievance; day 3 of 15.",
                        },
                    )
                )
            await ensure_packets(session, data)
        await session.commit()


async def main():
    await create_tables()
    await seed()
    print("red flag: synthetic demo scenarios ready")


if __name__ == "__main__":
    asyncio.run(main())
