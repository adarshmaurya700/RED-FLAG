import io
import pytest
from app.models.schemas import utcnow


def test_demo_cases_graph_and_nodal_timer(client):
    response = client.get("/api/v1/cases")
    assert response.status_code == 200
    cases = {item["id"]: item for item in response.json()}
    assert [cases[f"IND-FSSAI-0{i}"]["risk_score"] for i in (1, 2, 3)] == [88, 79, 74]
    detail = client.get("/api/v1/cases/IND-FSSAI-01").json()
    assert detail["grievances"][0]["days_elapsed"] == 3
    assert len(detail["packets"]) == 2
    graph = client.get("/api/v1/cases/IND-FSSAI-01/graph").json()
    assert graph["facility_alerts"][0]["license"] == "10012021000518"
    assert set(graph["facility_alerts"][0]["brands"]) == {"MasalaClub", "SnackLab"}


def test_empty_and_unknown_case_results(client):
    assert client.get("/api/v1/cases?mode=live").json() == []
    assert client.get("/api/v1/cases/unknown").status_code == 404
    assert client.get("/api/v1/cases?vector=invalid").status_code == 422


def test_dark_store_has_28_complaints_and_two_distinct_nodes(client):
    data = client.get("/api/v1/cases/IND-FSSAI-03/evidence?limit=100").json()
    assert data["total"] == 28
    assert {item["geography"]["node_id"] for item in data["items"]} == {
        "ram-koti",
        "malad-west",
    }


def test_live_scan_partial_source_failure_and_redaction(client, monkeypatch):
    async def collect(request):
        return [
            {
                "platform": "Google News",
                "source_url": "https://news.google.com/articles/demo",
                "text": "TestProtein hives after 20 minutes. @private_user email private@example.com phone 9876543210.",
                "timestamp": utcnow().isoformat(),
                "evidence_type": "news",
            }
        ], {
            "reddit": {"status": "blocked", "count": 0, "message": "HTTP 403"},
            "google_news": {"status": "ok", "count": 1, "message": ""},
        }

    monkeypatch.setattr("app.pipeline.collect_sources", collect)
    response = client.post(
        "/api/v1/scans",
        json={"product_name": "TestProtein"},
        headers={"Idempotency-Key": "partial-test"},
    )
    assert response.status_code == 202
    identifier = response.json()["id"]
    scan = client.get(f"/api/v1/scans/{identifier}").json()
    assert scan["state"] == "partial"
    assert scan["results"]["sources"]["reddit"]["status"] == "blocked"
    case_id = scan["results"]["case_ids"][0]
    detail = client.get(f"/api/v1/cases/{case_id}").json()
    assert (
        detail["complaint_count_48h"] == 0
    )  # Articles must not inflate complaint counts.
    assert detail["assessment"]["baseline_available"] is False
    evidence = client.get(f"/api/v1/cases/{case_id}/evidence").json()["items"][0]
    assert "private@example.com" not in evidence["text"]
    assert "9876543210" not in evidence["text"]
    repeated = client.post(
        "/api/v1/scans",
        json={"product_name": "TestProtein"},
        headers={"Idempotency-Key": "partial-test"},
    )
    assert repeated.json()["id"] == identifier
    conflict = client.post(
        "/api/v1/scans",
        json={"product_name": "Another product"},
        headers={"Idempotency-Key": "partial-test"},
    )
    assert conflict.status_code == 409


@pytest.mark.parametrize(
    "source_status,expected_state", [("empty", "completed"), ("blocked", "failed")]
)
def test_no_results_or_blocked_sources_never_create_fake_case(
    client, monkeypatch, source_status, expected_state
):
    async def collect(request):
        return [], {"reddit": {"status": source_status, "count": 0, "message": ""}}

    monkeypatch.setattr("app.pipeline.collect_sources", collect)
    response = client.post(
        "/api/v1/scans",
        json={"product_name": "NoResults" + source_status, "sources": ["reddit"]},
    )
    scan = client.get("/api/v1/scans/" + response.json()["id"]).json()
    assert scan["state"] == expected_state
    assert scan["results"]["case_ids"] == []


def test_url_guard_blocks_local_network_targets(client):
    response = client.post(
        "/api/v1/scans",
        json={"product_name": "Demo", "product_urls": ["https://127.0.0.1/private"]},
    )
    assert response.status_code == 422


def test_wrong_vector_packet_is_rejected(client):
    response = client.post(
        "/api/v1/cases/IND-FSSAI-03/packets", json={"kind": "recall"}
    )
    assert response.status_code == 409


def test_packet_regeneration_is_idempotent_and_draft_is_explicit(client):
    path = "/api/v1/cases/IND-FSSAI-01/packets"
    first = client.post(path, json={"kind": "recall"}).json()
    second = client.post(path, json={"kind": "recall"}).json()
    assert first["id"] == second["id"]
    assert first["data"]["status"] == "draft"
    assert first["data"]["synthetic"] is True


def test_live_import_cannot_contaminate_demo(client):
    response = client.post(
        "/api/v1/regulatory/import?source=foscos&case_id=IND-FSSAI-01",
        files={"file": ("records.json", b"[]", "application/json")},
    )
    assert response.status_code == 409


def test_malformed_regulator_import_is_explicit(client):
    response = client.post(
        "/api/v1/regulatory/import?source=foscos",
        files={
            "file": ("records.json", b'{"fssai_license_no":"123"}', "application/json")
        },
    )
    assert response.status_code == 422
