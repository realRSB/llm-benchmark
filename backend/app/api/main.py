from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.routes.leaderboard import router as leaderboard_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.raw_data import router as raw_data_router

from app.benchmark.run_service import execute_benchmark_run
from app.benchmark.scheduler import create_scheduler, shutdown_scheduler, start_scheduler
from app.benchmark.schemas import BenchmarkRun
from app.database import get_total_benchmark_call_counts, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = create_scheduler()
    app.state.scheduler = scheduler
    start_scheduler(scheduler)
    yield
    shutdown_scheduler(scheduler)


# FastAPI entrypoint. Routers are included from app/api/routes.
app = FastAPI(title="LLM Benchmark API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics_router)
app.include_router(leaderboard_router)
app.include_router(raw_data_router)


@app.get("/health")
async def health() -> dict:
    # Simple liveness endpoint for the frontend / uptime checks.
    return {"status": "ok"}


@app.get("/stats/benchmark-calls", tags=["stats"])
async def benchmark_calls_totals() -> dict:
    # Defined on the app root so this route is always present with main:app (avoids stale-router 404s).
    items, n_runs = get_total_benchmark_call_counts()
    total_calls = sum(int(i["benchmark_calls"]) for i in items)
    return {
        "ok": True,
        "n_runs": n_runs,
        "total_benchmark_calls": total_calls,
        "items": items,
    }


class RunResponse(BaseModel):
    ok: bool
    run_id: str
    targets: list[dict]
    samples: int
    metrics: int


@app.post("/run", response_model=RunResponse)
async def run_benchmark() -> RunResponse:
    run: BenchmarkRun = await execute_benchmark_run()
    return RunResponse(
        ok=True,
        run_id=run.run_id,
        targets=[t.model_dump() for t in run.targets],
        samples=len(run.samples),
        metrics=len(run.metrics),
    )