import pytest
from app.nlp_engine.hinglish_extractor import extract_entities
from app.triage_engine.tri_vector_classifier import classify


def signal(text, city="Mumbai", platform="Amazon.in", node=None):
    return {
        "text": text,
        "platform": platform,
        "verified_purchase": True,
        "entities": [e.model_dump() for e in extract_entities(text)],
        "geography": {
            "city": city,
            "node_id": node,
            "radius_km": 2.5 if node else None,
        },
    }


def test_counterfeit_cues_separate_from_batch_hazards():
    result = classify(
        [
            signal(
                "Missing hologram; QR code fails to scan; spelling errors; unauthorized third-party seller. Powder clumping."
            )
        ]
    )
    assert result["dominant_vector"] == "counterfeit"
    assert result["attribution"]["counterfeit"] > 0.8


def test_dark_store_cold_chain_clusters_remain_separate_nodes():
    result = classify(
        [
            signal(
                "Blinkit sour curdled milk, pest-damaged carton",
                city="Hyderabad",
                platform="Blinkit",
                node="ram-koti",
            ),
            signal(
                "Zepto sour milk", city="Mumbai", platform="Zepto", node="malad-west"
            ),
        ]
    )
    assert result["dominant_vector"] == "dark_store"
    assert result["attribution"]["dark_store"] > 0.8
    assert any("2 separate" in reason for reason in result["reasons"]["dark_store"])


def test_common_batch_across_verified_cities_identifies_factory():
    result = classify(
        [
            signal("lot-MX-02 hives and itchy throat; ferbam residue", "Delhi"),
            signal("lot-MX-02 hives and vomiting", "Mumbai"),
        ]
    )
    assert result["dominant_vector"] == "batch"
    assert result["attribution"]["batch"] > 0.8


def test_unknown_evidence_requires_review_and_probabilities_sum_to_one():
    result = classify([])
    assert result["dominant_vector"] == "review"
    assert sum(result["attribution"].values()) == pytest.approx(1)


def test_negated_symptoms_and_implicit_distress_do_not_become_anaphylaxis():
    entities = extract_entities(
        "No vomiting. Tension me tha, heart racing on empty street. Nut-free bar tastes like badam."
    )
    names = {e.normalized for e in entities}
    assert "vomiting" not in names
    assert "anaphylaxis" not in names
    assert "suspected undeclared allergen" in names
