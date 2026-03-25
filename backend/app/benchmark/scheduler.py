# Periodic benchmark runs (APScheduler + asyncio).

from __future__ import annotations

import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.benchmark.run_service import execute_benchmark_run

logger = logging.getLogger(__name__)


def _parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _scheduler_enabled() -> bool:
    raw = os.getenv("LLM_BENCH_SCHEDULER_ENABLED", "1").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def create_scheduler() -> AsyncIOScheduler:
    interval = _parse_int_env("LLM_BENCH_SCHEDULE_INTERVAL_SECONDS", 300)
    if interval < 1:
        interval = 300

    scheduler = AsyncIOScheduler()

    async def _job() -> None:
        try:
            run = await execute_benchmark_run()
            logger.info(
                "Scheduled benchmark finished run_id=%s samples=%s",
                run.run_id,
                len(run.samples),
            )
        except Exception:
            logger.exception("Scheduled benchmark run failed")

    scheduler.add_job(
        _job,
        IntervalTrigger(seconds=interval),
        id="llm_benchmark_run",
        replace_existing=True,
    )
    return scheduler


def start_scheduler(scheduler: AsyncIOScheduler) -> None:
    if not _scheduler_enabled():
        logger.info("LLM_BENCH_SCHEDULER_ENABLED is off; periodic runs are disabled")
        return
    scheduler.start()
    interval = _parse_int_env("LLM_BENCH_SCHEDULE_INTERVAL_SECONDS", 300)
    logger.info("Benchmark scheduler started (interval=%ss)", interval)


def shutdown_scheduler(scheduler: AsyncIOScheduler) -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
