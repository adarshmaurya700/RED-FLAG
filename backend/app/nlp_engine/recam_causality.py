"""Extract reported temporal cues; this does not calculate validated RECAM/RUCAM causality."""

import re
from app.models.schemas import ClinicalCues


def extract_causality(text: str) -> ClinicalCues:
    value = text.lower()
    onset = re.search(
        r"(?:after|within|in|baad|के बाद)?\s*(\d+(?:\.\d+)?)\s*(minutes?|mins?|min|m\b|मिनट|hours?|hrs?|घंटे|ghante)",
        value,
    )
    duration = re.search(
        r"(?:lasted|for|duration|तक)\s*(\d+(?:\.\d+)?)\s*(days?|din|दिन)", value
    )
    positive_dechallenge = bool(
        re.search(
            r"stopp?ed.{0,55}(?:better|subsid|resolved|gone)|(?:band|छोड़|बंद).{0,40}(?:theek|ठीक)|dechallenge[: ]+positive",
            value,
        )
    )
    negative_dechallenge = bool(
        re.search(
            r"(?:stopp?ed|band).{0,35}(?:no improvement|did not improve|not better)",
            value,
        )
    )
    positive_rechallenge = bool(
        re.search(
            r"(?:restart|tried again|dobara|दोबारा).{0,55}(?:return|again|wapas|फिर)|rechallenge[: ]+positive",
            value,
        )
    )
    concomitant = re.search(
        r"(?:also taking|along with|concomitant products?[: ]+)\s*([^.;\n]{2,100})",
        value,
    )
    hours = None
    if onset:
        hours = float(onset.group(1)) / (
            60 if onset.group(2).startswith(("min", "m", "मिनट")) else 1
        )
    return ClinicalCues(
        onset_latency_hours=round(hours, 4) if hours is not None else None,
        symptom_duration_days=float(duration.group(1)) if duration else None,
        dechallenge_status="negative"
        if negative_dechallenge
        else "positive"
        if positive_dechallenge
        else "unknown",
        rechallenge_status="positive" if positive_rechallenge else "unknown",
        concomitant_products=[
            part.strip() for part in re.split(r",| and ", concomitant.group(1))
        ]
        if concomitant
        else [],
    )
