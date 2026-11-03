from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from app.config import get_settings
from app.models.database import create_tables, Session, engine
from app.api.routes import router


@asynccontextmanager
async def lifespan(app):
    if get_settings().initialize_database:
        await create_tables()
    if get_settings().seed_demo:
        from seed_demo_data import seed

        await seed()
    yield
    await engine.dispose()


app = FastAPI(
    title="red flag API",
    version="1.0.0",
    description="Evidence-first Indian product safety triage. Synthetic demo data is explicitly labeled.",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "red-flag-api"}


@app.get("/ready")
async def ready():
    from fastapi.responses import JSONResponse

    try:
        async with Session() as session:
            await session.execute(text("SELECT 1"))
        if get_settings().task_mode == "celery":
            from redis.asyncio import Redis

            async with Redis.from_url(
                get_settings().redis_url, socket_connect_timeout=3
            ) as redis:
                await redis.ping()
        return {"status": "ready"}
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response
