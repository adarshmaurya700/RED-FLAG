from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from app.models.database import Grievance, AuditEvent
from uuid import uuid4


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def grievance_view(grievance: Grievance, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    due = aware(grievance.due_at)
    received = aware(grievance.received_at)
    return {
        "id": grievance.id,
        "case_id": grievance.case_id,
        "status": grievance.status,
        "received_at": received.isoformat(),
        "due_at": due.isoformat(),
        "days_elapsed": min(15, max(0, (now - received).days)),
        "seconds_remaining": max(0, int((due - now).total_seconds())),
        "escalation_due": grievance.status != "resolved" and now >= due,
        "internal_priority_due_at": (received + timedelta(hours=48)).isoformat()
        if grievance.data.get("priority")
        else None,
        **grievance.data,
    }


async def sweep_deadlines(session):
    now = datetime.now(timezone.utc)
    grievances = (
        await session.scalars(select(Grievance).where(Grievance.status == "open"))
    ).all()
    changed = 0
    for grievance in grievances:
        if aware(grievance.due_at) <= now and not grievance.data.get(
            "escalation_flagged_at"
        ):
            grievance.data = {
                **grievance.data,
                "escalation_flagged_at": now.isoformat(),
            }
            session.add(
                AuditEvent(
                    id=str(uuid4()),
                    case_id=grievance.case_id,
                    event="grievance_escalation_due",
                    data={"grievance_id": grievance.id, "external_submission": False},
                )
            )
            changed += 1
    await session.commit()
    return changed
