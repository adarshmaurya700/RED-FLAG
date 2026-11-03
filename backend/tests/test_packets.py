import io
from pypdf import PdfReader


def test_pdf_export_has_identifiable_batch_license_and_draft_label(client):
    detail = client.get("/api/v1/cases/IND-FSSAI-01").json()
    packet = next(item for item in detail["packets"] if item["kind"] == "recall")
    response = client.get("/api/v1/packets/" + packet["id"] + "?format=pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment;" in response.headers["content-disposition"]
    reader = PdfReader(io.BytesIO(response.content))
    text = "".join(page.extract_text() or "" for page in reader.pages)
    assert "lot-MX-02" in text
    assert "10012021000518" in text
    assert "DRAFT / SYNTHETIC" in text
    assert "CEO" in text and "Commissioner" in text


def test_each_vector_exports_its_own_packet_content(client):
    for case_id, kind, expected in [
        ("IND-FSSAI-02", "marketplace", "seller"),
        ("IND-FSSAI-03", "dark_store", "Ram Koti"),
    ]:
        detail = client.get("/api/v1/cases/" + case_id).json()
        packet = next(item for item in detail["packets"] if item["kind"] == kind)
        data = client.get("/api/v1/packets/" + packet["id"]).json()
        assert data["status"] == "draft"
        assert expected in str(data)
