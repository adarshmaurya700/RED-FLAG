from datetime import timedelta, datetime
from app.models.schemas import utcnow


def test_factory_decision_starts_separate_notification_and_weekly_clocks(client):
    now = utcnow() - timedelta(minutes=1)
    response = client.post(
        "/api/v1/cases/IND-FSSAI-01/recall-decision",
        json={"decision_at": now.isoformat()},
    )
    assert response.status_code == 200
    data = response.json()
    assert datetime.fromisoformat(data["notification_due_at"]) - now == timedelta(
        hours=24
    )
    assert datetime.fromisoformat(data["next_weekly_status_due_at"]) - now == timedelta(
        days=7
    )
    assert data["synthetic"] is True and data["external_submission"] is False
    wrong = client.post(
        "/api/v1/cases/IND-FSSAI-03/recall-decision",
        json={"decision_at": now.isoformat()},
    )
    assert wrong.status_code == 409


def test_authority_query_has_own_receipt_based_deadline_and_response(client):
    received = utcnow() - timedelta(hours=2)
    response = client.post(
        "/api/v1/cases/IND-FSSAI-01/authority-queries",
        json={"reference": "DEMO-QUERY-001", "received_at": received.isoformat()},
    )
    data = response.json()
    assert datetime.fromisoformat(data["due_at"]) - received == timedelta(hours=24)
    resolved = client.patch(
        f"/api/v1/cases/IND-FSSAI-01/authority-queries/{data['id']}/responded"
    )
    assert resolved.json()["status"] == "responded"


def test_weekly_recovery_report_checks_quantities_and_scrubs_notes(client):
    client.post(
        "/api/v1/cases/IND-FSSAI-01/recall-decision",
        json={"decision_at": (utcnow() - timedelta(days=1)).isoformat()},
    )
    payload = {
        "submitted_at": utcnow().isoformat(),
        "distributed_units": 4800,
        "recovered_units": 600,
        "effectiveness_notes": "Recovery checked; contact private@example.com",
    }
    response = client.post("/api/v1/cases/IND-FSSAI-01/weekly-status", json=payload)
    assert response.status_code == 200
    assert (
        "private@example.com"
        not in response.json()["reports"][-1]["effectiveness_notes"]
    )
    assert (
        client.post(
            "/api/v1/cases/IND-FSSAI-01/weekly-status",
            json={**payload, "recovered_units": 5000},
        ).status_code
        == 422
    )
