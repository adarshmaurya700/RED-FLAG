import re
from collections import Counter
from app.models.schemas import Attribution


def classify(signals: list[dict]) -> dict:
    weights = {"batch": 1.0, "counterfeit": 1.0, "dark_store": 1.0}
    reasons: dict[str, list[str]] = {key: [] for key in weights}
    batch_cities: dict[str, set] = {}
    node_counts = Counter()
    for s in signals:
        text = s.get("text", "").lower()
        entities = s.get("entities", [])
        geo = s.get("geography", {})
        counter = [e["normalized"] for e in entities if e["kind"] == "counterfeit"]
        if counter:
            weights["counterfeit"] += sum(
                1.5 if "clump" in cue else 4 for cue in counter
            )
            reasons["counterfeit"].extend(counter)
        if re.search(r"unauthori[sz]ed|unverified seller|third.party seller", text):
            weights["counterfeit"] += 5
            reasons["counterfeit"].append("Unverified marketplace seller")
        is_qcom = bool(
            re.search(
                r"blinkit|zepto|instamart|flipkart minutes|quick.commerce",
                s.get("platform", "").lower() + " " + text,
            )
        )
        spoilage = any(
            e["normalized"] in {"cold-chain spoilage", "pest damage"} for e in entities
        )
        if is_qcom and spoilage:
            weights["dark_store"] += 7
            reasons["dark_store"].append("Quick-commerce spoilage reports")
            if (
                geo.get("node_id")
                and geo.get("radius_km") is not None
                and geo["radius_km"] <= 3
            ):
                node_counts[geo["node_id"]] += 1
        for e in entities:
            if e["kind"] == "batch" and geo.get("city"):
                batch_cities.setdefault(e["normalized"].lower(), set()).add(geo["city"])
            if e["kind"] == "symptom" and e.get("severity", 0) >= 65:
                weights["batch"] += 5
                reasons["batch"].append("Acute clinical severity cue")
            if e["kind"] == "hazard" and e.get("severity", 0) >= 75:
                weights["batch"] += 6
                reasons["batch"].append(e["normalized"])
        if s.get("verified_purchase") and not is_qcom:
            weights["batch"] += 1
    for batch, cities in batch_cities.items():
        if len(cities) >= 2:
            weights["batch"] += 14
            reasons["batch"].append(f"Same batch across {len(cities)} cities: {batch}")
    if node_counts:
        weights["dark_store"] += 8 * len(node_counts)
        reasons["dark_store"].append(
            f"{len(node_counts)} separate corroborated local nodes"
        )
    total = sum(weights.values())
    batch = weights["batch"] / total
    counterfeit = weights["counterfeit"] / total
    attribution = Attribution(
        batch=batch, counterfeit=counterfeit, dark_store=1 - batch - counterfeit
    )
    dominant = max(weights, key=weights.get)
    confidence = max(attribution.model_dump().values())
    if confidence < 0.5:
        dominant = "review"
    return {
        "attribution": attribution.model_dump(),
        "dominant_vector": dominant,
        "reasons": {k: sorted(set(v)) for k, v in reasons.items()},
        "method": "heuristic-v1",
        "needs_review": dominant == "review",
    }
