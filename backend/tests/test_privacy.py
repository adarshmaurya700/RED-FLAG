from app.ingestion.dpdpa_scrubber import scrub_payload, scrub_text, safe_source_url
from app.nlp_engine.recam_causality import extract_causality


def test_strips_personal_identifiers_preserves_safety_metadata():
    payload = {
        "username": "private_handle",
        "phone_number": "+919876543210",
        "email": "person@example.com",
        "exact_street_address": "Flat 4 MG Road",
        "voice_biometrics": [1, 2, 3],
        "text": "@private_handle email person@example.com phone 9876543210. Hives after 20 minutes. Batch lot-MX-02; license 10012021000518. Delivery PIN 500001.",
        "platform": "Blinkit",
        "geography": {"pin_code_prefix": "500001", "city": "Hyderabad"},
    }
    clean, removed = scrub_payload(payload)
    rendered = str(clean)
    for value in (
        "private_handle",
        "person@example.com",
        "9876543210",
        "Flat 4 MG Road",
        "500001",
    ):
        assert value not in rendered
    assert "voice_biometrics" not in clean
    assert clean["geography"]["pin_code_prefix"] == "500"
    assert "Hives" in clean["text"] and "lot-MX-02" in clean["text"]
    assert "10012021000518" in clean["text"]
    assert extract_causality(clean["text"]).onset_latency_hours == 0.3333
    assert {"username", "email", "phone_number"}.issubset(removed)


def test_personal_url_paths_tracking_and_credentials_are_removed():
    assert (
        safe_source_url(
            "https://reddit.com/user/private-person?q=email@example.com#secret"
        )
        == "https://reddit.com/profile/redacted"
    )
    assert safe_source_url("https://user:password@example.com/private") == ""
    assert safe_source_url("javascript:alert(1)") == ""


def test_private_contact_and_address_in_free_text():
    result, fields = scrub_text(
        "My name is Raj Sharma. Flat 4 MG Road. Call +91 98765 43210. pet kharab ho gaya."
    )
    assert "Raj Sharma" not in result
    assert "Flat 4 MG Road" not in result
    assert "98765 43210" not in result
    assert "pet kharab" in result


def test_iso_timestamp_microseconds_are_not_mistaken_for_pin_codes():
    timestamp = "2026-11-03T12:30:00.987654+00:00"
    result, _ = scrub_payload({"timestamp": timestamp})
    assert result["timestamp"] == timestamp
