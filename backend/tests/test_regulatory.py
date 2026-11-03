import json
import pytest
from app.ingestion.regulatory_hub import (
    parse_records,
    packaging_claim_flags,
    ayush_cues,
    SUPPORTED_LANGUAGES,
)
from app.nlp_engine.recam_causality import extract_causality


def row(**extra):
    return {
        "fbo_name": "Fictional Foods",
        "fssai_license_no": "10012021000518",
        "food_category_code": "102",
        "action_type": "Improvement Notice",
        "reason_for_recall": "Synthetic inspection",
        "start_date": "2026-11-01",
        **extra,
    }


def test_strict_license_and_extended_food_categories():
    parsed = parse_records(json.dumps([row()]).encode(), "json", "foscos")
    assert parsed[0].fssai_license_no == "10012021000518"
    assert parsed[0].food_category_code == "102"
    with pytest.raises(ValueError):
        parse_records(
            json.dumps([row(fssai_license_no="123")]).encode(), "json", "foscos"
        )


def test_csv_and_official_html_table_imports():
    content = b"fbo_name,action_type,reason_for_recall,start_date\nFictional Foods,Improvement Notice,Cold chain,2026-11-01"
    assert parse_records(content, "csv", "foscos")[0].fbo_name == "Fictional Foods"
    html = b"<table><tr><th>fbo_name</th><th>action_type</th><th>reason</th><th>date</th></tr><tr><td>Demo</td><td>BIS Recall</td><td>Testing</td><td>2026-11-01</td></tr></table>"
    assert parse_records(html, "html", "bis")[0].source == "bis"


def test_claim_flag_and_ayush_dual_tracking_cues():
    assert packaging_claim_flags("FSSAI Approved")[-1]["requires_review"] is True
    assert packaging_claim_flags("FSSAI licensed") == []
    assert {
        "suspected HILI",
        "heavy metals",
        "suspected drug spiking",
        "misleading advertisement",
    } == set(ayush_cues("Jaundice, lead, steroid spiking, misleading cure-all"))
    assert len(SUPPORTED_LANGUAGES - {"en"}) == 10


def test_clinical_cues_preserve_unknown_and_positive_temporal_reports():
    cues = extract_causality(
        "Hives after 20 minutes. Stopped the product and symptoms subsided. Tried again and hives returned. Symptoms lasted for 2 days. Also taking vitamin C."
    )
    assert cues.onset_latency_hours == 0.3333
    assert cues.symptom_duration_days == 2
    assert cues.dechallenge_status == "positive"
    assert cues.rechallenge_status == "positive"
    assert cues.concomitant_products == ["vitamin c"]
    assert extract_causality("No timing provided").onset_latency_hours is None
