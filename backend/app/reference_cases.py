import json
import re
from functools import lru_cache
from app.config import get_settings


def load_reference_cases() -> dict:
    return json.loads(
        (get_settings().data_directory / "real_cases.json").read_text(encoding="utf-8")
    )


def search_reference_cases(query: str) -> list[dict]:
    cases = load_reference_cases()["cases"]
    terms = [
        word
        for word in re.findall(r"[\w]+", query.casefold())
        if word not in {"case", "cases", "the", "report", "reports"}
    ]
    if not terms:
        return cases

    def score(case):
        text = " ".join(
            [case["brand"], case["product"], case["summary"], *case["aliases"]]
        ).casefold()
        return sum(
            bool(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text))
            for term in terms
        )

    # All meaningful terms match, so a generic 'case' does not make unrelated profiles appear.
    return sorted(
        [case for case in cases if score(case) == len(terms)], key=score, reverse=True
    )
