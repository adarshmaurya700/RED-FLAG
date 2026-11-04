"""Run the same free scanner locally or in GitHub Actions."""

import argparse
import asyncio
import json
from pathlib import Path
import sys
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.ingestion.source_scanner import SourceScanner
from app.models.source_findings import SourceCatalog


async def run(args):
    previous = (
        SourceCatalog.model_validate_json(args.output.read_text(encoding="utf-8"))
        if args.output.exists()
        else None
    )
    if args.from_published:
        from app.source_catalog import CATALOG_URL, MAX_BYTES

        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.get(CATALOG_URL)
        if response.status_code == 404:
            bundled = ROOT / "data/source-catalog.json"
            if previous is None and bundled.exists():
                previous = SourceCatalog.model_validate_json(
                    bundled.read_text(encoding="utf-8")
                )
        else:
            response.raise_for_status()
            if len(response.content) > MAX_BYTES:
                raise ValueError("Published catalogue exceeded size limit")
            previous = SourceCatalog.model_validate_json(response.content)
    async with httpx.AsyncClient(
        follow_redirects=False, limits=httpx.Limits(max_connections=4)
    ) as client:
        catalog = await SourceScanner(
            client, max_pages=args.max_pages, max_seconds=args.max_seconds
        ).run(previous)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(catalog.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    for source, health in catalog.sources.items():
        count = sum(item.source == source for item in catalog.items)
        print(
            f"{source}: {health.status}; {count} stored, {health.checked} checked, {len(health.pending_urls)} pending, {health.failed} failed",
            flush=True,
        )
        for error in health.errors[:3]:
            print(f"  {error}", flush=True)
    if not catalog.items:
        raise SystemExit("No source records collected; inspect source errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/source-catalog.json"
    )
    parser.add_argument("--max-pages", type=int, default=600)
    parser.add_argument("--max-seconds", type=int, default=1200)
    parser.add_argument(
        "--from-published",
        action="store_true",
        help="Resume the published data branch; fail safely if it cannot be read",
    )
    options = parser.parse_args()
    if not 1 <= options.max_pages <= 600 or not 1 <= options.max_seconds <= 1200:
        parser.error("Maximum is 600 pages and 1200 seconds")
    asyncio.run(run(options))
