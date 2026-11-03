from app.reference_cases import search_reference_cases, load_reference_cases


def test_pari_husk_search_resolves_priyagold_not_parle():
    for query in ("pari case", "Priyagold", "husk", "cattle feed", "प्रियागोल्ड"):
        results = search_reference_cases(query)
        assert results[0]["id"] == "priyagold-bran-2026"
    assert search_reference_cases("Parle") == []


def test_real_profiles_have_direct_sources_and_no_invented_scores():
    cases = load_reference_cases()["cases"]
    assert len(cases) == 3
    for case in cases:
        assert len(case["sources"]) >= 2
        assert "risk_score" not in case
        assert all(source["url"].startswith("https://") for source in case["sources"])
    priya = cases[0]
    assert any("dftqc.gov.np" in source["url"] for source in priya["sources"])
    assert priya["published_at"] == "2026-10-17"
