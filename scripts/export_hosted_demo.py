"""Export only newly seeded fictional records for the free read-only frontend."""

import asyncio
import base64
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


async def export(destination: Path):
    import httpx
    from app.main import app
    from app.models.database import create_tables, engine
    from app.models.schemas import utcnow
    from seed_demo_data import seed

    await create_tables()
    await seed()
    snapshot = {
        "captured_at": utcnow().isoformat(),
        "details": {},
        "evidence": {},
        "graphs": {},
        "packets": {},
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://demo"
    ) as client:

        async def get(path):
            response = await client.get("/api/v1" + path)
            response.raise_for_status()
            return response

        snapshot["telemetry"] = (await get("/telemetry")).json()
        snapshot["telemetry"].update(
            hosted_demo=True,
            privacy_status="Synthetic demo data",
            task_mode="readonly",
            providers={},
        )
        snapshot["cases"] = (await get("/cases?mode=demo")).json()
        assert len(snapshot["cases"]) == 3
        for case in snapshot["cases"]:
            assert case["synthetic"]
            identifier = case["id"]
            snapshot["details"][identifier] = (await get(f"/cases/{identifier}")).json()
            snapshot["evidence"][identifier] = (
                await get(f"/cases/{identifier}/evidence?limit=100")
            ).json()
            snapshot["graphs"][identifier] = (
                await get(f"/cases/{identifier}/graph")
            ).json()
            for packet in snapshot["details"][identifier]["packets"]:
                identifier = packet["id"]
                data = (await get(f"/packets/{identifier}")).json()
                assert data["synthetic"]
                snapshot["packets"][identifier] = {
                    "json": data,
                    "pdf_base64": base64.b64encode(
                        (await get(f"/packets/{identifier}?format=pdf")).content
                    ).decode(),
                }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "demo-snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (destination / "real-cases.json").write_text(
        (ROOT / "data/real_cases.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    source_catalog = ROOT / "data/source-catalog.json"
    if source_catalog.exists():
        (destination / "source-catalog.json").write_text(
            source_catalog.read_text(encoding="utf-8"), encoding="utf-8"
        )
    await engine.dispose()
    print(
        f"Exported {len(snapshot['cases'])} synthetic cases and {len(snapshot['packets'])} packets for the free hosted demo"
    )


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="red-flag-demo-") as temporary:
        os.environ.update(
            DATABASE_URL="sqlite+aiosqlite:///"
            + str(Path(temporary) / "demo.db").replace("\\", "/"),
            APP_ENV="development",
            INTERNAL_API_KEY="",
            TASK_MODE="local",
            SEED_DEMO="true",
        )
        asyncio.run(export(ROOT / "frontend/src/data"))
