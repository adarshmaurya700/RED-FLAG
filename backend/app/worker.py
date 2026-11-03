import asyncio
from datetime import timedelta
from celery import Celery
from sqlalchemy import select
from app.config import get_settings
from app.models.database import Session, ScanJob
from app.models.schemas import utcnow
from app.pipeline import process_scan
from app.triggerware.nodal_interceptor import sweep_deadlines

celery_app = Celery(
    "red_flag", broker=get_settings().redis_url, backend=get_settings().redis_url
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=600,
    task_soft_time_limit=570,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "deadline-sweep": {"task": "red_flag.deadlines", "schedule": 60},
        "stale-scan-sweep": {"task": "red_flag.stale_scans", "schedule": 300},
    },
)


@celery_app.task(name="red_flag.scan")
def scan_task(identifier: str):
    asyncio.run(process_scan(identifier))


@celery_app.task(name="red_flag.deadlines")
def deadline_task():
    async def run():
        async with Session() as session:
            return await sweep_deadlines(session)

    return asyncio.run(run())


@celery_app.task(name="red_flag.stale_scans")
def stale_scans_task():
    async def run():
        async with Session() as session:
            jobs = (
                await session.scalars(
                    select(ScanJob).where(
                        ScanJob.state.in_(["running", "queued"]),
                        ScanJob.updated_at < utcnow() - timedelta(minutes=15),
                    )
                )
            ).all()
            for job in jobs:
                job.state = "failed"
                job.results = {
                    "message": "Scan timed out or its worker was interrupted. Retry safely.",
                    "case_ids": [],
                }
            await session.commit()
            return len(jobs)

    return asyncio.run(run())
