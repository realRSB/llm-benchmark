from fastapi import FastAPI
from pydantic import BaseModel

from app.api.routes.leaderboard import router as leaderboard_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.raw_data import router as raw_data_router

from app.benchmark.runner import run_benchmark_once
from app.benchmark.state import benchmark_state

# FastAPI entrypoint. Routers are included from app/api/routes.
app = FastAPI(title="LLM Benchmark API", version="0.1.0")

app.include_router(metrics_router)
app.include_router(leaderboard_router)
app.include_router(raw_data_router)


@app.get("/health")
async def health() -> dict:
    # Simple liveness endpoint for the frontend / uptime checks.
    return {"status": "ok"}


class RunResponse(BaseModel):
    ok: bool
    run_id: str
    targets: list[dict]
    samples: int
    metrics: int


@app.post("/run", response_model=RunResponse)
async def run_benchmark() -> RunResponse:
    run = await run_benchmark_once()
    benchmark_state.set_latest(run)
    return RunResponse(
        ok=True,
        run_id=run.run_id,
        targets=[t.model_dump() for t in run.targets],
        samples=len(run.samples),
        metrics=len(run.metrics),
    )