# Shared benchmark execution: run once, update in-memory state, persist.

from __future__ import annotations

from app.benchmark.runner import run_benchmark_once
from app.benchmark.schemas import BenchmarkRun
from app.benchmark.state import benchmark_state
from app.database import save_benchmark_run


async def execute_benchmark_run() -> BenchmarkRun:
    run = await run_benchmark_once()
    benchmark_state.set_latest(run)
    save_benchmark_run(run)
    return run
