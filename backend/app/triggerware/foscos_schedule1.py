import hashlib
import io
import json
from xml.sax.saxutils import escape
from uuid import uuid4
from sqlalchemy import select
from app.models.database import ActionPacket
from app.triggerware.marketplace_actions import (
    marketplace_notice,
    authentication_advisory,
    laboratory_request,
    dark_store_alert,
)

KINDS = {
    "batch": ["recall", "consumer_notice"],
    "counterfeit": ["marketplace", "authentication", "lab_request"],
    "dark_store": ["dark_store"],
    "review": [],
}
RECALL_SOURCE = (
    "https://www.fssai.gov.in/upload/uploadfiles/files/Food_Recall_Regulations.pdf"
)


def recall_information(case: dict) -> dict:
    fbo = case.get("fbo", {})
    missing = [
        field
        for field in (
            "name",
            "business_address",
            "license_no",
            "coordinator",
            "business_contact",
        )
        if not fbo.get(field)
    ]
    if not case.get("batches"):
        missing.append("implicated batch details")
    return {
        "title": "Schedule I - Food Recall Information",
        "recipients": [
            "CEO, Food Safety and Standards Authority of India",
            "Commissioner of Food Safety, concerned State / Union territory",
        ],
        "routing": fbo.get("license_type", "unknown")
        + " license; confirm responsible authorities before submission",
        "fbo": fbo,
        "food_category_code": case.get("food_category_code"),
        "implicated_foods": case.get("products", []),
        "batches": case.get("batches", []),
        "quantity_affected": case.get("quantity_affected", "Not established"),
        "distribution_footprint": case.get("cities", []),
        "complaint_count_48h": case.get("complaint_count_48h", 0),
        "reported_illnesses": case.get("reported_illnesses", "Not established"),
        "reason": case.get("summary", ""),
        "proposed_recall_class": "Class I - operator/authority review required",
        "risk_assessment": case.get("assessment", {}),
        "proposed_actions": [
            "Identify implicated lots and distribution accounts",
            "Stop distribution of stock determined to require recall",
            "Notify the concerned authorities and supply-chain contacts",
            "Record recovery and effectiveness checks",
        ],
        "missing_fields": missing,
        "legal_reference": "FSS (Food Recall Procedure) Regulations, 2017, Regulation 6(3) and Schedule I",
        "source_url": RECALL_SOURCE,
    }


def consumer_notice(case: dict) -> dict:
    return {
        "title": "URGENT FOOD RECALL NOTICE - DRAFT",
        "fbo": case.get("fbo", {}),
        "product": case["product_name"],
        "brands": case.get("products", []),
        "affected_batches": case.get("batches", []),
        "reason": case.get("summary", ""),
        "consumer_message": "Do not consume the identified affected batch. Keep the package and contact the recall coordinator for return instructions.",
        "health_warning": "Reported allergic reactions and contamination concerns require review. Anyone with severe symptoms should seek urgent medical care.",
        "distribution_locations": case.get("cities", []),
        "contact": case.get("fbo", {}).get(
            "business_contact", "Required before release"
        ),
        "release_status": "Requires factual verification and authorized release",
        "source_url": RECALL_SOURCE,
    }


def packet_content(case: dict, kind: str) -> dict:
    builders = {
        "recall": recall_information,
        "consumer_notice": consumer_notice,
        "marketplace": marketplace_notice,
        "authentication": authentication_advisory,
        "lab_request": laboratory_request,
        "dark_store": dark_store_alert,
    }
    if kind not in KINDS.get(case.get("dominant_vector", "review"), []):
        raise ValueError("Packet type does not match this case's attribution")
    return {
        "brand": "red flag",
        "case_id": case["id"],
        "status": "draft",
        "synthetic": case.get("synthetic", False),
        "assessment_version": case.get("assessment", {}).get(
            "policy_version", "continuous-hazard-v1"
        ),
        "notice": "Synthetic demonstration - not an actual recall or enforcement action."
        if case.get("synthetic")
        else "Draft for authorized operator review; not submitted or issued by an authority.",
        "content": builders[kind](case),
    }


async def ensure_packets(session, case: dict) -> list[ActionPacket]:
    if case["risk_score"] < 70:
        return []
    packets = []
    for kind in KINDS.get(case["dominant_vector"], []):
        data = packet_content(case, kind)
        content_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        previous = await session.scalar(
            select(ActionPacket)
            .where(ActionPacket.case_id == case["id"], ActionPacket.kind == kind)
            .order_by(ActionPacket.version.desc())
            .limit(1)
        )
        if previous and previous.content_hash == content_hash:
            packets.append(previous)
            continue
        packet = ActionPacket(
            id=str(uuid4()),
            case_id=case["id"],
            kind=kind,
            version=previous.version + 1 if previous else 1,
            content_hash=content_hash,
            data=data,
        )
        session.add(packet)
        packets.append(packet)
    await session.flush()
    return packets


def render_pdf(packet: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=(210 * mm, 297 * mm),
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=27 * mm,
        bottomMargin=22 * mm,
        title=packet["content"]["title"],
        author="red flag",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Value",
            fontName="Helvetica",
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#242731"),
            spaceAfter=6,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="Label",
            parent=styles["Value"],
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#5b6070"),
        )
    )
    styles["Title"].fontName = "Helvetica-Bold"
    styles["Title"].fontSize = 23
    styles["Title"].leading = 28
    styles["Title"].alignment = TA_LEFT
    styles["Heading3"].fontName = "Helvetica-Bold"
    styles["Heading3"].fontSize = 11
    styles["Heading3"].leading = 15
    styles["Heading3"].keepWithNext = True

    def printable(value):
        if isinstance(value, list):
            return "<br/>".join(printable(item) for item in value) or "Not established"
        if isinstance(value, dict):
            return "<br/>".join(
                f"<b>{escape(k.replace('_', ' ').title())}:</b> {printable(v)}"
                for k, v in value.items()
            )
        return escape(str(value if value is not None else "Not established"))

    story = [
        Paragraph(escape(packet["content"]["title"]), styles["Title"]),
        Paragraph(escape(packet["notice"]), styles["Value"]),
        Spacer(1, 7 * mm),
    ]
    for label, value in packet["content"].items():
        if label == "title":
            continue
        story.extend(
            [
                Paragraph(escape(label.replace("_", " ").title()), styles["Heading3"]),
                Paragraph(printable(value), styles["Value"]),
                Spacer(1, 2 * mm),
            ]
        )

    def page(canvas, doc):
        canvas.setFillColor(colors.HexColor("#f04438"))
        canvas.setFont("Helvetica-Bold", 15)
        canvas.drawString(20 * mm, 282 * mm, "red flag / action desk")
        canvas.setStrokeColor(colors.HexColor("#e3e4e8"))
        canvas.line(20 * mm, 277 * mm, 190 * mm, 277 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#717784"))
        canvas.drawString(
            20 * mm,
            13 * mm,
            f"{packet['case_id']}  |  DRAFT"
            + (" / SYNTHETIC" if packet.get("synthetic") else ""),
        )
        canvas.drawRightString(190 * mm, 13 * mm, f"Page {doc.page}")

    document.build(story, onFirstPage=page, onLaterPages=page)
    return buffer.getvalue()
