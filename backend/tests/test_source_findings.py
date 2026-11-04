"""Publisher parsing, collection recovery, and score-boundary regressions."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import asyncio
import json
import time
import httpx
import pytest
from app.ingestion.source_parser import PublicPage, canonical_url, parse_finding
from app.ingestion.source_scanner import SourceScanner, CrawlLimit, merge_finding
from app.models.source_findings import SourceCatalog, SourceHealth
from app.source_catalog import CatalogRepository, search_catalog

FIXTURES = Path(__file__).parent / "fixtures/source_pages"
URLS = {
    "trust-pass": "https://www.trustified.in/passandfail/naturalteincreamag",
    "trust-fail": "https://www.trustified.in/passandfail/mdhkitchenking",
    "trust-expired": "https://www.trustified.in/passandfail/bgreenplantproteinexpired",
    "trust-nmr": "https://www.trustified.in/nmr-reports/vedakahoney",
    "food-label": "https://foodpharmer.health/c/biscuits/millet-jaggery-cookies",
    "food-lab": "https://foodpharmer.health/c/paneer/amul-malai-paneer",
}
NOW = datetime(2026, 11, 5, 3, tzinfo=timezone.utc)


def finding(name, checked_at=NOW):
    return parse_finding(
        "trustified" if name.startswith("trust") else "foodpharmer",
        URLS[name],
        (FIXTURES / f"{name}.html").read_text(encoding="utf-8"),
        checked_at=checked_at,
    )


def catalog():
    return SourceCatalog(
        generated_at=NOW,
        sources={
            name: SourceHealth(
                status="ok",
                last_attempt_at=NOW,
                last_success_at=NOW,
                discovered=3,
                checked=3,
            )
            for name in ("trustified", "foodpharmer")
        },
        items=[finding(name) for name in URLS],
    )


@pytest.mark.parametrize(
    "name,outcome,status,method",
    [
        ("trust-pass", "pass", "passed", "independent_test"),
        ("trust-fail", "fail", "failed", "independent_test"),
        ("trust-expired", "unknown", "expired", "independent_test"),
        ("trust-nmr", "unknown", "unknown", "independent_test"),
        ("food-label", "recommended", "unknown", "label_reviewed"),
        ("food-lab", "recommended", "unknown", "reported_lab_test"),
    ],
)
def test_real_visible_metadata(name, outcome, status, method):
    item = finding(name)
    assert (item.outcome, item.testing_status, item.review_method) == (
        outcome,
        status,
        method,
    )
    assert item.proof_links[0].url == URLS[name]
    assert item.fetched_at == NOW
    if name == "trust-pass":
        assert item.brand == "Naturaltein" and item.batch == "NCMU260301"
        assert item.published_at == "2026-08-13"
    if name == "food-label":
        assert item.brand == "Early Foods" and item.last_verified_at == "2026-04-27"
    if name == "trust-nmr":
        assert "exogenous sugar" in item.excerpt and item.laboratory == "Eurofins"


def test_missing_fields_and_scripts_cannot_supply_claims():
    html = "<main><h1>Product</h1><p>Product Name – Product</p><script>Testing Status - Failed</script></main>"
    item = parse_finding("trustified", URLS["trust-pass"], html)
    assert (
        item.outcome == "unknown" and item.batch is None and item.published_at is None
    )
    with pytest.raises(ValueError, match="fields missing"):
        parse_finding(
            "trustified", URLS["trust-pass"], "<main><h1>Empty template</h1></main>"
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/",
        "https://www.trustified.in.evil.test/",
        "https://user:pass@www.trustified.in/",
        "file:///etc/passwd",
        "https://foodpharmer.health:8443/",
    ],
)
def test_crawl_allowlist(url):
    with pytest.raises(ValueError):
        canonical_url(url)


def test_updates_keep_identity_and_revision_history():
    old = finding("trust-pass")
    same = merge_finding(old, finding("trust-pass", NOW + timedelta(days=1)))
    assert (
        same.id == old.id and same.revision == 1 and same.updated_at == old.updated_at
    )
    modified_html = (
        (FIXTURES / "trust-pass.html")
        .read_text(encoding="utf-8")
        .replace("Passed", "Failed")
    )
    changed = parse_finding(
        "trustified",
        URLS["trust-pass"],
        modified_html,
        checked_at=NOW + timedelta(days=2),
    )
    changed = merge_finding(same, changed)
    assert changed.id == old.id and changed.revision == 2
    assert changed.outcome == "fail" and changed.history[0].outcome == "pass"
    assert changed.first_seen_at == old.first_seen_at


def test_search_outcomes_scope_and_staleness():
    data = catalog()
    assert search_catalog(data, q="MDH Kitchen", now=NOW).total == 1
    assert search_catalog(data, q="cream", now=NOW).total == 0
    assert search_catalog(data, source="foodpharmer", now=NOW).total == 2
    expired = search_catalog(data, outcome="expired", now=NOW)
    assert expired.total == 1 and expired.items[0].outcome == "unknown"
    assert search_catalog(data, outcome="fail", now=NOW).total == 1
    assert len(search_catalog(data, limit=1, offset=1, now=NOW).items) == 1
    assert all(
        item.stale for item in search_catalog(data, now=NOW + timedelta(hours=49)).items
    )


def transport(block=False):
    def handle(request):
        url = str(request.url)
        if block and request.url.host == "www.trustified.in":
            return httpx.Response(403)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if url in URLS.values():
            name = next(name for name, link in URLS.items() if link == url)
            return httpx.Response(
                200, text=(FIXTURES / f"{name}.html").read_text(encoding="utf-8")
            )
        if url == "https://www.trustified.in/passandfail":
            return httpx.Response(
                200,
                text="".join(
                    f'<a href="{URLS[name]}">{name}</a>'
                    for name in ("trust-pass", "trust-fail", "trust-expired")
                ),
            )
        if url == "https://www.trustified.in/nmr-reports":
            return httpx.Response(200, text=f'<a href="{URLS["trust-nmr"]}">NMR</a>')
        if url == "https://foodpharmer.health/":
            return httpx.Response(200, text='<a href="/c/biscuits">Biscuits</a>')
        if url == "https://foodpharmer.health/c/biscuits":
            return httpx.Response(
                200,
                text=f'<main><li>✓No maida</li><a href="{URLS["food-label"]}">Cookies</a></main>',
            )
        return httpx.Response(404)

    return httpx.MockTransport(handle)


@pytest.mark.asyncio
async def test_bounded_scan_resumes_and_preserves_blocked_records():
    async with httpx.AsyncClient(transport=transport()) as client:
        scanner = SourceScanner(client, max_pages=6, interval=0)
        partial = await scanner.run()
        assert scanner.pages == 6
        assert any(info.pending_urls for info in partial.sources.values())
        completed = await SourceScanner(client, interval=0).run(partial)
    assert len(completed.items) == 5 and all(
        info.status == "ok" for info in completed.sources.values()
    )
    assert len({item.id for item in completed.items}) == 5
    async with httpx.AsyncClient(transport=transport(block=True)) as client:
        blocked = await SourceScanner(client, interval=0).run(completed)
    assert blocked.sources["trustified"].status == "blocked"
    old = {item.id: item for item in completed.items}
    assert all(
        item.fetched_at == old[item.id].fetched_at
        for item in blocked.items
        if item.source == "trustified"
    )


@pytest.mark.asyncio
async def test_host_rate_and_total_deadline():
    times = []

    def handler(request):
        times.append(time.monotonic())
        return httpx.Response(200, text="ok")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        scanner = SourceScanner(client)
        await scanner.get("https://www.trustified.in/robots.txt")
        await scanner.get("https://www.trustified.in/passandfail")
    assert times[1] - times[0] >= 0.95

    async def slow(request):
        await asyncio.sleep(2)
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(slow)) as client:
        scanner = SourceScanner(client, max_seconds=1.1, interval=0)
        with pytest.raises(CrawlLimit):
            await scanner.get("https://www.trustified.in/robots.txt")


@pytest.mark.asyncio
async def test_malformed_published_catalogue_keeps_last_good(monkeypatch, tmp_path):
    payload = catalog().model_dump_json()
    original = httpx.AsyncClient

    class Client(original):
        def __init__(self, **kwargs):
            super().__init__(
                **kwargs,
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, text=payload)
                ),
            )

    monkeypatch.setattr("app.source_catalog.httpx.AsyncClient", Client)
    repo = CatalogRepository(tmp_path / "none.json")
    first, origin = await repo.load()
    assert origin == "published" and len(first.items) == 6
    repo.expires = 0
    payload = '{"schema_version": 999}'
    second, origin = await repo.load()
    assert origin == "last_good" and second == first
    fallback = tmp_path / "saved.json"
    fallback.write_text(catalog().model_dump_json())
    loaded, origin = await CatalogRepository(fallback).load()
    assert origin == "bundled" and len(loaded.items) == 6


def test_findings_api_and_source_only_scan_do_not_create_investigations(
    client, monkeypatch
):
    data = catalog()

    class Repository:
        async def load(self):
            return data, "bundled"

    monkeypatch.setattr("app.source_catalog.repository", lambda: Repository())
    response = client.get("/api/v1/source-findings?q=MDH")
    assert response.status_code == 200 and response.json()["total"] == 1
    assert client.get("/api/v1/source-findings?source=other").status_code == 422
    assert client.get("/api/v1/source-findings?limit=101").status_code == 422
    before = client.get("/api/v1/cases").json()

    async def collect(request):
        return [
            {
                "record_kind": "source_finding",
                "finding": finding("trust-fail").model_dump(mode="json"),
            }
        ], {"trustified": {"status": "ok", "count": 1, "message": ""}}

    monkeypatch.setattr("app.pipeline.collect_sources", collect)
    monkeypatch.setattr(
        "app.pipeline.extract_entities",
        lambda text: pytest.fail("Reference findings entered clinical extraction"),
    )
    started = client.post(
        "/api/v1/scans",
        json={"product_name": "MDH Kitchen King", "sources": ["trustified"]},
    )
    assert started.status_code == 202
    scan = client.get("/api/v1/scans/" + started.json()["id"]).json()
    assert scan["state"] == "completed" and scan["results"]["case_ids"] == []
    assert len(scan["results"]["source_findings"]) == 1
    assert client.get("/api/v1/cases").json() == before
