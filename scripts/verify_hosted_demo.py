"""Check the free demo's API contract against a local production Next.js build."""

import base64
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def verify():
    origin = "http://127.0.0.1:3100"
    password = os.environ["HOSTED_OPERATOR_PASSWORD"]
    authorization = (
        "Basic " + base64.b64encode(f"operator:{password}".encode()).decode()
    )

    def request(path, *, method="GET", status=200, auth=True):
        headers = {"Authorization": authorization} if auth else {}
        req = Request(origin + path, method=method, headers=headers)
        try:
            response = urlopen(req, timeout=15)
        except HTTPError as error:
            response = error
        assert response.code == status, (path, response.code, status)
        with response:
            return response.read(), response.headers

    def get(path):
        return json.loads(request("/api/v1" + path)[0])

    request("/", status=401, auth=False)
    request("/api/v1/cases", status=401, auth=False)
    assert b"red flag" in request("/")[0]
    request("/health", auth=False)
    telemetry = get("/telemetry")
    assert telemetry["hosted_demo"] and telemetry["task_mode"] == "readonly"
    cases = get("/cases")
    assert len(cases) == 3 and all(case["synthetic"] for case in cases)
    assert sorted(case["risk_score"] for case in cases) == [74, 79, 88]
    assert get("/cases?mode=live") == []
    assert len(get("/cases?vector=batch")) == 1
    reports = get("/reference-cases?q=pari%20case")["items"]
    assert len(reports) == 1 and reports[0]["brand"] == "Priyagold"
    assert any("thehindu.com" in source["url"] for source in reports[0]["sources"])
    assert len(get("/reference-cases")["items"]) == 3
    assert get("/reference-cases?q=unknownzebra")["items"] == []
    findings = get("/source-findings?q=MDH&source=trustified&outcome=fail")
    assert findings["total"] >= 1 and all(
        item["source"] == "trustified" and item["outcome"] == "fail"
        for item in findings["items"]
    )
    reviewed = get("/source-findings?source=foodpharmer&limit=1")
    assert reviewed["total"] >= 1 and len(reviewed["items"]) == 1
    assert reviewed["items"][0]["proof_links"][0]["url"].startswith(
        "https://foodpharmer.health/"
    )
    request("/api/v1/source-findings?outcome=unsafe", status=422)
    request("/api/v1/source-findings", status=401, auth=False)
    report = get("/reference-cases/" + reports[0]["id"])
    assert len(report["sources"]) >= 3
    request("/reports/" + report["id"])
    packet_count = 0
    for case in cases:
        case_id = case["id"]
        detail = get("/cases/" + case_id)
        graph = get(f"/cases/{case_id}/graph")
        nodes = {node["id"] for node in graph["nodes"]}
        assert nodes and all(
            edge["source"] in nodes and edge["target"] in nodes
            for edge in graph["edges"]
        )
        evidence = get(f"/cases/{case_id}/evidence?limit=1")
        assert len(evidence["items"]) == 1 and evidence["total"] >= 1
        assert all(signal["synthetic"] for signal in evidence["items"])
        assert get(f"/cases/{case_id}/evidence?platform=unknown")["items"] == []
        request(f"/api/v1/cases/{case_id}/evidence?limit=-1", status=422)
        request(f"/cases/{case_id}")
        for packet in detail["packets"]:
            packet_id = packet["id"]
            assert get("/packets/" + packet_id)["synthetic"]
            content, headers = request(f"/api/v1/packets/{packet_id}?format=pdf")
            assert (
                content.startswith(b"%PDF-")
                and headers["Content-Type"] == "application/pdf"
            )
            packet_count += 1
    assert packet_count == 6
    for path, method in [
        ("scans", "POST"),
        ("grievances/anything", "PATCH"),
        ("cases/anything/recall-decision", "POST"),
    ]:
        body = json.loads(request("/api/v1/" + path, method=method, status=405)[0])
        assert "read-only" in body["detail"]
    request("/api/v1/cases/not-a-case", status=404)
    request("/api/v1/cases/constructor", status=404)
    print(
        "Hosted demo verified: authentication, 3 synthetic cases, 3 real profiles, graphs, filtered evidence, 6 PDF/JSON exports, and rejected writes."
    )


if __name__ == "__main__":
    verify()
