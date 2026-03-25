from typing import Literal

from fastapi import APIRouter, Query

from app.benchmark.state import benchmark_state
from app.database import get_latest_benchmark_run

# Raw-series endpoints are useful for transparency/debugging (per-run TTFT samples, etc.).
router: APIRouter = APIRouter(prefix="/rawdata", tags=["rawdata"])

__all__ = ["router"]


@router.get("/")
async def raw_data(
    model: str | None = None,
    prompt_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=2000),
    include_output: Literal["0", "1"] = Query(default="0", description="0=no output_text, 1=include output_text"),
) -> dict:
    latest = get_latest_benchmark_run() or benchmark_state.get_latest()
    if latest is None:
        return {
            "ok": True,
            "items": [],
            "limit": limit,
            "filter": {"model": model, "prompt_id": prompt_id},
            "note": "No benchmark run yet. Call POST /run first.",
        }

    items = []
    store_output = include_output == "1"
    for s in latest.samples:
        if model is not None and s.model != model:
            continue
        if prompt_id is not None and s.prompt_id != prompt_id:
            continue

        d = s.model_dump()
        if not store_output:
            d["output_text"] = None
        items.append(d)

    return {
        "ok": True,
        "run_id": latest.run_id,
        "items": items[:limit],
        "limit": limit,
        "filter": {"model": model, "prompt_id": prompt_id},
        "note": "latest run from database (or in-memory if no DB row)",
    }