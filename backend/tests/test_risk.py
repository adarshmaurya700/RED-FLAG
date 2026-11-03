import pytest
from pydantic import ValidationError
from app.models.schemas import SubScores
from app.triage_engine.risk_scorer import risk_score, velocity


@pytest.mark.parametrize(
    "values,growth,expected",
    [
        ((15, 82, 91, 86), 0.56, 88),
        ((0, 64, 88, 80), 0.93, 79),
        ((25, 58, 84, 78), 0.40, 74),
    ],
)
def test_requested_scenario_scores(values, growth, expected):
    scores = SubScores(**dict(zip(SubScores.model_fields, values)))
    assert risk_score(scores, growth)["score"] == expected


def test_pre_recall_hazard_escalates_without_regulatory_record():
    result = risk_score(
        SubScores(regulatory=0, adverse_events=90, live_web=98, credibility=95), 1
    )
    assert result["score"] > 85
    assert result["score"] > result["base_score"]


def test_amplification_is_continuous_and_not_switched_off_at_low_regulatory_score():
    values = [
        risk_score(
            SubScores(regulatory=r, adverse_events=82, live_web=91, credibility=86),
            0.56,
        )
        for r in (0, 0.01, 15, 100)
    ]
    assert abs(values[0]["score"] - values[1]["score"]) < 0.2
    assert values[2]["amplification"] > 1
    assert values[3]["amplification"] == 1


def test_velocity_increases_score_and_score_is_capped():
    scores = SubScores(regulatory=0, adverse_events=100, live_web=100, credibility=100)
    assert risk_score(scores, 1)["score"] == 100
    moderate = SubScores(regulatory=10, adverse_events=60, live_web=70, credibility=75)
    assert risk_score(moderate, 1)["score"] > risk_score(moderate, 0)["score"]


@pytest.mark.parametrize("bad", [-1, 1.1, float("nan"), float("inf")])
def test_invalid_velocity_rejected(bad):
    with pytest.raises(ValueError):
        risk_score(SubScores(), bad)


def test_bounded_growth_and_missing_history():
    assert velocity(28, 20) == 0.4
    assert velocity(100, 1) == 1
    assert velocity(10, 20) == 0
    assert velocity(30, None) == 0
    assert velocity(0, 0) == 0


def test_out_of_range_factors_rejected():
    with pytest.raises(ValidationError):
        SubScores(live_web=101)
