from typing import Literal

from fastapi import APIRouter, Query

from app.benchmark.state import benchmark_state

# Metrics endpoints for rolled-up latency stats (p50/p90/p95, etc.).
router: APIRouter = APIRouter(prefix="/metrics", tags=["metrics"])

__all__ = ["router"]


@router.get("/latest")
async def latest_metrics(
    limit: int = Query(default=50, ge=1, le=500),
    category: Literal["short", "medium", "long"] | None = Query(default=None),
) -> dict:
    latest = benchmark_state.get_latest()
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