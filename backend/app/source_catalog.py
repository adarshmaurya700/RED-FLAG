"""Validated catalogue access and search, independent of investigation storage."""

import asyncio
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
import re
import time
import httpx
from app.models.source_findings import (
    SourceCatalog,
    SourceHealth,
    SourceFindingsResponse,
)

CATALOG_URL = "https://raw.githubusercontent.com/adarshmaurya700/RED-FLAG/refs/heads/codex/source-data/catalog.json"
BUNDLED_PATH = Path(__file__).resolve().parents[2] / "data/source-catalog.json"
MAX_BYTES = 6_000_000


class CatalogRepository:
    def __init__(self, path=BUNDLED_PATH):
        self.path = path
        self.cached = None
        self.expires = 0
        self.origin = "bundled"
        self.lock = asyncio.Lock()

    async def load(self):
        if self.cached is not None and time.monotonic() < self.expires:
            return self.cached, self.origin
        async with self.lock:
            if self.cached is not None and time.monotonic() < self.expires:
                return self.cached, self.origin
            try:
                async with httpx.AsyncClient(
                    timeout=8, follow_redirects=False
                ) as client:
                    async with client.stream("GET", CATALOG_URL) as response:
                        response.raise_for_status()
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > MAX_BYTES:
                                raise ValueError("Catalogue size exceeded")
                catalog = SourceCatalog.model_validate_json(data)
                self.cached, self.origin = catalog, "published"
            except (httpx.HTTPError, ValueError):
                if self.cached is not None:
                    self.origin = "last_good"
                else:
                    try:
                        if self.path.stat().st_size > MAX_BYTES:
                            raise ValueError("Bundled catalogue size exceeded")
                        self.cached = SourceCatalog.model_validate_json(
                            self.path.read_text(encoding="utf-8")
                        )
                        self.origin = "bundled"
                    except (OSError, ValueError):
                        self.cached = SourceCatalog(
                            generated_at=datetime.now(timezone.utc),
                            sources={
                                name: SourceHealth()
                                for name in ("trustified", "foodpharmer")
                            },
                        )
                        self.origin = "unavailable"
            self.expires = time.monotonic() + (
                3600 if self.origin == "published" else 60
            )
            return self.cached, self.origin


@lru_cache
def repository():
    return CatalogRepository()


def search_catalog(
    catalog,
    q="",
    source="all",
    outcome="all",
    offset=0,
    limit=20,
    origin="bundled",
    now=None,
):
    now = now or datetime.now(timezone.utc)
    terms = re.findall(r"[^\W_]+", q.casefold())
    selected = []
    for item in catalog.items:
        words = set(
            re.findall(
                r"[^\W_]+",
                f"{item.product_name} {item.brand or ''} {item.category or ''}".casefold(),
            )
        )
        if source not in {"all", item.source} or not all(
            term in words for term in terms
        ):
            continue
        if outcome == "expired":
            if item.testing_status != "expired":
                continue
        elif outcome not in {"all", item.outcome}:
            continue
        selected.append(item)
    selected.sort(key=lambda item: (item.product_name.casefold(), item.source, item.id))
    health = {}
    for name, info in catalog.sources.items():
        health[name] = {
            **info.model_dump(mode="json", exclude={"pending_urls"}),
            "pending": len(info.pending_urls),
            "stale": info.last_success_at is None
            or now - info.last_success_at > timedelta(hours=48),
        }
    return SourceFindingsResponse(
        items=[
            {
                **item.model_dump(mode="json"),
                "stale": now - item.fetched_at > timedelta(hours=48),
            }
            for item in selected[offset : offset + limit]
        ],
        total=len(selected),
        generated_at=catalog.generated_at,
        sources=health,
        catalog_origin=origin,
    )


async def source_findings(**query):
    catalog, origin = await repository().load()
    return search_catalog(catalog, origin=origin, **query)
