from math import isfinite
from app.models.schemas import SubScores

POLICY_VERSION = "continuous-hazard-v1"


def risk_score(scores: SubScores, delta_velocity_48h: float = 0) -> dict:
    if not isfinite(delta_velocity_48h) or not 0 <= delta_velocity_48h <= 1:
        raise ValueError("48-hour velocity must be finite and between 0 and 1")
    base = (
        0.20 * scores.regulatory
        + 0.25 * scores.adverse_events
        + 0.35 * scores.live_web
        + 0.20 * scores.credibility
    )
    factor = max(0.0, 1.0 - scores.regulatory / 100)
    phi = 1.0 + 0.25 * factor * ((scores.live_web * scores.credibility) / 10000) * (
        1 + 0.50 * delta_velocity_48h
    )
    return {
        "score": min(100.0, round(phi * base, 1)),
        "base_score": round(base, 4),
        "amplification": round(phi, 6),
        "pre_recall_factor": factor,
        "velocity": delta_velocity_48h,
        "policy_version": POLICY_VERSION,
    }


def velocity(current: int, previous: int | None) -> float:
    if current < 0 or (previous is not None and previous < 0):
        raise ValueError("Counts must be nonnegative")
    return (
        0.0
        if previous is None
        else max(0.0, min(1.0, (current - previous) / max(previous, 1)))
    )


REGULATORY_WEIGHT = {
    "Advertising & Claims Notice": 15,
    "Misleading Advertisement": 15,
    "Improvement Notice": 25,
    "Premises License Suspension": 60,
    "Section 36(3)(b) Prohibition Order": 80,
    "BIS Recall": 75,
}


def evidence_subscores(
    signals: list[dict], records: list[dict], growth: float, current_count: int
) -> tuple[SubScores, dict]:
    reg = max(
        [0]
        + [
            (
                {
                    "Class I": 100,
                    "Class II": 75,
                    "Class III": 50,
                    "Market Withdrawal": 40,
                }.get(
                    r.get("recall_class"),
                    REGULATORY_WEIGHT.get(r.get("action_type"), 0),
                )
            )
            for r in records
        ]
    )
    clinical = []
    for signal in signals:
        severity = max(
            [0]
            + [
                e.get("severity", 0)
                for e in signal.get("entities", [])
                if e.get("kind") == "symptom"
            ]
        )
        cues = signal.get("clinical", {})
        if severity:
            severity += (
                5 * (cues.get("onset_latency_hours") is not None)
                + 5 * (cues.get("dechallenge_status") == "positive")
                + 10 * (cues.get("rechallenge_status") == "positive")
            )
        clinical.append(min(100, severity))
    platforms = len({s["platform"] for s in signals})
    cities = len(
        {
            s.get("geography", {}).get("city")
            for s in signals
            if s.get("geography", {}).get("city")
        }
    )
    web = 40 * min(current_count / 30, 1) + 40 * growth + 20 * min(cities / 3, 1)
    verified = sum(bool(s.get("verified_purchase")) for s in signals) / max(
        len(signals), 1
    )
    lab = max(
        [0]
        + [
            {"none": 0, "attachment": 0.5, "verified": 1}.get(
                s.get("lab_evidence", "none"), 0
            )
            for s in signals
        ]
    )
    credibility = 35 * min(platforms / 4, 1) + 35 * verified + 30 * lab
    scores = SubScores(
        regulatory=reg,
        adverse_events=max(clinical, default=0),
        live_web=round(web, 1),
        credibility=round(credibility, 1),
    )
    return scores, {
        "policy_version": "evidence-rubric-v1",
        "provisional": True,
        "regulatory_status": "matched" if records else "not_observed",
        "source_count": platforms,
        "verified_purchase_ratio": verified,
        "lab_weight": lab,
        "complaint_count": current_count,
        "note": "Engineering triage rubric; not a clinical causality or legal determination.",
    }
