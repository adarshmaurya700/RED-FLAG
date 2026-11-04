"""Bounded, resumable public-source scanner used locally and by GitHub Actions."""

import asyncio
from datetime import datetime, timezone
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
import httpx
from app.ingestion.source_parser import (
    HOSTS,
    PublicPage,
    canonical_url,
    category_urls,
    category_criteria,
    detail_urls,
    parse_finding,
)
from app.models.source_findings import SourceCatalog, SourceHealth, FindingChange

USER_AGENT = "RedFlagSourceScanner/1.0 (+https://github.com/adarshmaurya700/RED-FLAG; public search index)"
STARTS = {
    "trustified": [
        "https://www.trustified.in/passandfail",
        "https://www.trustified.in/nmr-reports",
    ],
    "foodpharmer": ["https://foodpharmer.health/"],
}


class CrawlLimit(Exception):
    pass


class SourceBlocked(Exception):
    pass


def merge_finding(previous, current):
    if previous is None:
        return current
    current.first_seen_at = previous.first_seen_at
    current.history = previous.history
    current.revision = previous.revision
    if previous.content_hash != current.content_hash:
        current.revision += 1
        current.history = (
            previous.history
            + [
                FindingChange(
                    changed_at=current.fetched_at,
                    outcome=previous.outcome,
                    testing_status=previous.testing_status,
                    content_hash=previous.content_hash,
                )
            ]
        )[-5:]
    else:
        current.updated_at = previous.updated_at
    return current


class SourceScanner:
    def __init__(self, client, *, max_pages=600, max_seconds=1200, interval=1.0):
        self.client, self.max_pages, self.max_seconds = client, max_pages, max_seconds
        self.interval, self.started, self.pages = interval, time.monotonic(), 0
        self.last_request = {}

    async def get(self, url, robots=None):
        remaining = self.max_seconds - (time.monotonic() - self.started)
        if remaining <= 0:
            raise CrawlLimit("Daily time budget reached")
        try:
            async with asyncio.timeout(remaining):
                return await self._get(url, robots)
        except TimeoutError:
            raise CrawlLimit("Daily time budget reached") from None

    async def _get(self, url, robots=None):
        url = canonical_url(url)
        for redirect in range(4):
            if robots is not None and not robots.can_fetch(USER_AGENT, url):
                raise SourceBlocked("Source robots.txt disallows this page")
            host = urlsplit(url).hostname
            for attempt in range(2):
                remaining = self.max_seconds - (time.monotonic() - self.started)
                if self.pages >= self.max_pages or remaining <= 1:
                    raise CrawlLimit("Daily page or time budget reached")
                wait = self.interval - (
                    time.monotonic() - self.last_request.get(host, 0)
                )
                if wait > 0:
                    await asyncio.sleep(min(wait, remaining))
                # Increment before yielding: both source tasks share the same global budget.
                if (
                    self.pages >= self.max_pages
                    or time.monotonic() - self.started >= self.max_seconds
                ):
                    raise CrawlLimit("Daily page or time budget reached")
                self.pages += 1
                self.last_request[host] = time.monotonic()
                try:
                    async with self.client.stream(
                        "GET",
                        url,
                        headers={"User-Agent": USER_AGENT},
                        timeout=min(20, remaining),
                    ) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            target = canonical_url(
                                response.headers.get("location", ""), url
                            )
                            if urlsplit(target).hostname != host:
                                raise ValueError(
                                    "Cross-publisher source redirect rejected"
                                )
                            url = target
                            break
                        if response.status_code in {401, 403, 429}:
                            raise SourceBlocked(
                                f"Source returned HTTP {response.status_code}"
                            )
                        response.raise_for_status()
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > 5_000_000:
                                raise ValueError("Source page exceeded 5 MB")
                        return bytes(body).decode(
                            response.encoding or "utf-8", errors="replace"
                        )
                except (httpx.TransportError, httpx.HTTPStatusError) as error:
                    if (
                        isinstance(error, httpx.HTTPStatusError)
                        and error.response.status_code < 500
                    ):
                        raise
                    if attempt == 1:
                        raise
            else:
                raise ValueError("Source request failed")
        raise ValueError("Too many source redirects")

    async def run(self, previous=None):
        now = datetime.now(timezone.utc)
        previous = previous or SourceCatalog(
            generated_at=now, sources={source: SourceHealth() for source in STARTS}
        )
        items = {item.source_url: item.model_copy(deep=True) for item in previous.items}

        async def source_scan(source):
            old = previous.sources.get(source, SourceHealth())
            health = SourceHealth(
                last_attempt_at=now, last_success_at=old.last_success_at
            )
            known = {url for url, item in items.items() if item.source == source}
            pending = set(old.pending_urls)
            discovered, criteria_by_category = set(), {}
            try:
                robot_url = f"https://{HOSTS[source]}/robots.txt"
                robots = RobotFileParser(robot_url)
                try:
                    robots.parse((await self.get(robot_url)).splitlines())
                except httpx.HTTPStatusError as error:
                    if error.response.status_code == 404:
                        robots.parse(["User-agent: *", "Allow: /"])
                    else:
                        raise
                # A declared crawl delay can increase, but never lower, our interval.
                self.interval = max(self.interval, robots.crawl_delay(USER_AGENT) or 0)
                for start in STARTS[source]:
                    page = PublicPage(await self.get(start, robots))
                    discovered.update(detail_urls(source, page, start))
                    pending.update(discovered)
                    if source == "foodpharmer":
                        for category in sorted(category_urls(page, start)):
                            category_page = PublicPage(await self.get(category, robots))
                            criteria_by_category[category] = category_criteria(
                                category_page
                            )
                            discovered.update(
                                detail_urls(source, category_page, category)
                            )
                            pending.update(discovered)
                if not discovered:
                    raise ValueError(
                        "No product links discovered; source layout may have changed"
                    )
                for missing in known - discovered:
                    items[missing].availability = "unavailable"
                pending.update(discovered)
                # Resume unchecked pages first, then oldest checked pages. No fixed first-page loop.
                queue = sorted(
                    pending,
                    key=lambda url: (
                        0 if url in old.pending_urls else 1,
                        items[url].fetched_at.timestamp() if url in items else 0,
                        url,
                    ),
                )
                for url in queue:
                    try:
                        if urlsplit(canonical_url(url)).hostname != HOSTS[source]:
                            raise ValueError(
                                "Source queue contains a different publisher"
                            )
                        html = await self.get(url, robots)
                        category = url.rsplit("/", 1)[0]
                        finding = parse_finding(
                            source,
                            url,
                            html,
                            criteria=criteria_by_category.get(category, []),
                        )
                        items[url] = merge_finding(items.get(url), finding)
                        pending.discard(url)
                        health.checked += 1
                    except CrawlLimit:
                        raise
                    except SourceBlocked:
                        raise
                    except (httpx.HTTPError, ValueError) as error:
                        health.failed += 1
                        if len(health.errors) < 20:
                            health.errors.append(f"{url}: {str(error)[:150]}")
                        if url in items:
                            items[url].availability = "unavailable"
                health.status = "ok" if not pending else "partial"
                if health.checked:
                    health.last_success_at = datetime.now(timezone.utc)
            except (CrawlLimit, SourceBlocked, httpx.HTTPError, ValueError) as error:
                health.status = (
                    "blocked"
                    if isinstance(error, SourceBlocked)
                    else "partial"
                    if isinstance(error, CrawlLimit) or health.checked
                    else "error"
                )
                health.errors = (health.errors + [str(error)[:250]])[:20]
                if health.checked:
                    health.last_success_at = datetime.now(timezone.utc)
            health.pending_urls = sorted(pending)
            health.discovered = len(discovered or known)
            # Unknown coverage must not look like a successful empty refresh.
            return source, health

        health = dict(await asyncio.gather(*(source_scan(source) for source in STARTS)))
        return SourceCatalog(
            generated_at=datetime.now(timezone.utc),
            sources=health,
            items=sorted(
                items.values(),
                key=lambda item: (item.source, item.product_name.casefold(), item.id),
            ),
        )
