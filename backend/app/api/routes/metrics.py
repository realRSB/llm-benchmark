from typing import Literal

from fastapi import APIRouter, Query

from app.benchmark.state import benchmark_state
from app.database import get_latest_benchmark_run, get_ttft_history_series

# Metrics endpoints for rolled-up latency stats (p50/p90/p95, etc.).
router: APIRouter = APIRouter(prefix="/metrics", tags=["metrics"])

__all__ = ["router"]


@router.get("/latest")
async def latest_metrics(
    limit: int = Query(default=50, ge=1, le=500),
    category: Literal["short", "medium", "long"] | None = Query(default=None),
) -> dict:
    latest = get_latest_benchmark_run() or benchmark_state.get_latest()
    if latest is None:
        return {
            "ok": True,
            "items": [],
            "limit": limit,
            "note": "No benchmark run yet. Call POST /run first.",
        }

    metrics = latest.metrics
    if category is not None:
        metrics = [m for m in metrics if m.prompt_category == category]

    items = [m.model_dump() for m in metrics[:limit]]
    return {
        "ok": True,
        "run_id": latest.run_id,
        "finished_at": latest.finished_at.isoformat(),
        "items": items,
        "limit": limit,
    }


@router.get("/history")
async def metrics_history(
    limit_runs: int = Query(default=100, ge=1, le=500, description="Most recent runs to include"),
    metric: str = Query(
        default="p95",
        description="avg|median|p90|p95 — computed over prompts in each run, per model",
    ),
    provider: str | None = Query(default=None, description="Optional filter (exact provider id)"),
    model: str | None = Query(default=None, description="Optional filter (exact model id)"),
) -> dict:
    payload = get_ttft_history_series(
        limit_runs=limit_runs,
        metric_key=metric,
        provider=provider,
        model=model,
    )
    return {"ok": True, **payload}