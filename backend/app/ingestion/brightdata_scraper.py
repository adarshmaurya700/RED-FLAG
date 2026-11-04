"""Read-only collection adapters. Provider errors never become fabricated evidence."""

import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urlsplit
import httpx
from defusedxml import ElementTree
from app.config import get_settings
from app.ingestion.dpdpa_scrubber import scrub_payload
from app.models.schemas import ScanRequest, SourceOutcome

ALLOWED_HOSTS = {
    "amazon.in",
    "flipkart.com",
    "1mg.com",
    "healthkart.com",
    "blinkit.com",
    "zepto.com",
    "zeptonow.com",
    "reddit.com",
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "swiggy.com",
    "fssai.gov.in",
    "foscos.fssai.gov.in",
    "ipc.gov.in",
    "ayushsuraksha.com",
    "bis.gov.in",
    "services.bis.gov.in",
    "consumerhelpline.gov.in",
}


def validate_public_url(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if (
        parts.scheme != "https"
        or parts.username
        or parts.password
        or parts.port not in {None, 443}
    ):
        raise ValueError("Only HTTPS public product/source URLs are accepted")
    if not any(
        host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS
    ):
        raise ValueError("URL domain is not an enabled marketplace or official source")
    return url


def plain_text(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())[:12000]


def record(
    platform: str, url: str, text: str, timestamp=None, evidence_type="complaint"
) -> dict:
    clean, redacted = scrub_payload(
        {"platform": platform, "source_url": url, "text": plain_text(text)}
    )
    clean.update(
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        evidence_type=evidence_type,
        redacted_fields=redacted,
    )
    return clean


async def reddit_search(client: httpx.AsyncClient, query: str) -> list[dict]:
    settings = get_settings()
    headers = {
        "User-Agent": "web:red-flag-india:1.0 (product safety research; read only)"
    }
    host = "https://www.reddit.com"
    if settings.reddit_access_token:
        host = "https://oauth.reddit.com"
        headers["Authorization"] = f"Bearer {settings.reddit_access_token}"
    response = await client.get(
        host + "/search.json",
        params={
            "q": query,
            "sort": "new",
            "limit": settings.max_scan_items,
            "t": "month",
        },
        headers=headers,
    )
    response.raise_for_status()
    output = []
    for item in response.json().get("data", {}).get("children", []):
        data = item.get("data", {})
        text = data.get("title", "") + " " + data.get("selftext", "")
        timestamp = datetime.fromtimestamp(
            data.get("created_utc", 0), timezone.utc
        ).isoformat()
        output.append(
            record(
                "Reddit",
                "https://www.reddit.com" + data.get("permalink", ""),
                text,
                timestamp,
            )
        )
    return output


async def google_news_search(client: httpx.AsyncClient, query: str) -> list[dict]:
    response = await client.get(
        "https://news.google.com/rss/search",
        params={"q": f'"{query}" India', "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
    )
    response.raise_for_status()
    if len(response.content) > 2_000_000:
        raise ValueError("News feed exceeded size limit")
    root = ElementTree.fromstring(response.content)
    from email.utils import parsedate_to_datetime

    results = []
    for item in root.findall("./channel/item")[: get_settings().max_scan_items]:
        try:
            timestamp = parsedate_to_datetime(item.findtext("pubDate", "")).isoformat()
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc).isoformat()
        results.append(
            record(
                "Google News",
                item.findtext("link", ""),
                item.findtext("title", "") + " " + item.findtext("description", ""),
                timestamp,
                "news",
            )
        )
    return results


async def tinyfish_collect(client: httpx.AsyncClient, urls: list[str]) -> list[dict]:
    settings = get_settings()
    if not settings.tinyfish_api_key:
        raise LookupError("TINYFISH_API_KEY is not configured")
    if not urls:
        raise LookupError("TinyFish requires at least one supported product URL")
    output = []
    for url in urls:
        validate_public_url(url)
        response = await client.post(
            "https://agent.tinyfish.ai/v1/automation/run-sse",
            headers={"X-API-Key": settings.tinyfish_api_key},
            json={
                "url": url,
                "goal": "Read visible public product reviews only. Do not log in, submit forms, purchase, or navigate to private pages. Return JSON with reviews: [{text, source_url, timestamp}]. Exclude reviewer names, handles and contact details.",
                "max_steps": 12,
            },
            timeout=90,
        )
        response.raise_for_status()
        payload = None
        for line in response.text.splitlines():
            if line.startswith("data:"):
                try:
                    event = json.loads(line[5:].strip())
                    if (
                        event.get("type") == "COMPLETE"
                        or event.get("status") == "COMPLETED"
                    ):
                        payload = event.get("resultJson", event.get("result", {}))
                except json.JSONDecodeError:
                    continue
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            raise ValueError("TinyFish returned no completed structured result")
        for review in payload.get("reviews", [])[: settings.max_scan_items]:
            output.append(
                record(
                    "TinyFish / " + (urlsplit(url).hostname or "web"),
                    review.get("source_url", url),
                    str(review.get("text", "")),
                    review.get("timestamp"),
                )
            )
    return output


async def brightdata_collect(client: httpx.AsyncClient, urls: list[str]) -> list[dict]:
    settings = get_settings()
    if not settings.brightdata_api_key:
        raise LookupError("BRIGHTDATA_API_KEY is not configured")
    datasets = json.loads(settings.brightdata_dataset_ids or "{}")
    output = []
    for url in urls:
        validate_public_url(url)
        host = (urlsplit(url).hostname or "").removeprefix("www.")
        dataset_id = datasets.get(host)
        if not dataset_id:
            raise LookupError(f"No Bright Data dataset ID configured for {host}")
        response = await client.post(
            "https://api.brightdata.com/datasets/v3/scrape",
            params={"dataset_id": dataset_id, "format": "json"},
            headers={"Authorization": f"Bearer {settings.brightdata_api_key}"},
            json=[{"url": url}],
            timeout=90,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError(
                "Bright Data returned an asynchronous or unexpected response; no evidence imported"
            )
        for item in data[: settings.max_scan_items]:
            text = item.get("review_text", item.get("text", item.get("review", "")))
            if text:
                output.append(
                    record(host, item.get("url", url), str(text), item.get("timestamp"))
                )
    return output


async def collect_sources(request: ScanRequest) -> tuple[list[dict], dict[str, dict]]:
    query = " ".join(part for part in (request.brand, request.product_name) if part)
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=settings.scan_timeout_seconds,
        follow_redirects=False,
        limits=httpx.Limits(max_connections=8),
    ) as client:

        async def one(source):
            try:
                if source == "reddit":
                    items = await reddit_search(client, query)
                elif source == "google_news":
                    items = await google_news_search(client, query)
                elif source == "tinyfish":
                    items = await tinyfish_collect(client, request.product_urls)
                elif source in {"trustified", "foodpharmer"}:
                    from app.source_catalog import source_findings

                    found = await source_findings(q=query, source=source, limit=100)
                    health = found.sources.get(source, {})
                    status = health.get("status", "unavailable")
                    items = [
                        {
                            "record_kind": "source_finding",
                            "finding": item.model_dump(mode="json"),
                        }
                        for item in found.items
                    ]
                    return (
                        source,
                        items,
                        SourceOutcome(
                        status="partial"
                        if items and (status != "ok" or health.get("stale"))
                        else "ok"
                        if status == "ok"
                            else "blocked"
                            if status == "blocked"
                            else "unavailable",
                            count=len(items),
                            message=f"Daily source catalogue: {status}; {len(items)} matched review findings. "
                            + (
                                "Data older than 48 hours. "
                                if health.get("stale")
                                else ""
                            )
                            + "References do not affect risk scores.",
                        ).model_dump(),
                    )
                else:
                    items = await brightdata_collect(client, request.product_urls)
                return (
                    source,
                    items,
                    SourceOutcome(
                        status="ok" if items else "empty", count=len(items)
                    ).model_dump(),
                )
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                return (
                    source,
                    [],
                    SourceOutcome(
                        status="blocked" if code in {401, 403, 429} else "error",
                        message=f"Source returned HTTP {code}; no synthetic replacement used.",
                    ).model_dump(),
                )
            except LookupError as exc:
                return (
                    source,
                    [],
                    SourceOutcome(status="unavailable", message=str(exc)).model_dump(),
                )
            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
                ElementTree.ParseError,
            ):
                return (
                    source,
                    [],
                    SourceOutcome(
                        status="error",
                        message="Source timed out or returned an unsupported response.",
                    ).model_dump(),
                )

        collected = await asyncio.gather(*(one(source) for source in request.sources))
    return [item for _, items, _ in collected for item in items], {
        source: outcome for source, _, outcome in collected
    }
