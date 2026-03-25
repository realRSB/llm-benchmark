from collections import defaultdict
from statistics import mean

from fastapi import APIRouter, Query

from app.benchmark.state import benchmark_state

# Leaderboard endpoints show best models/providers based on aggregated metrics.
router: APIRouter = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

__all__ = ["router"]


@router.get("/")
async def leaderboard(
    limit: int = Query(default=20, ge=1, le=200),
    metric: str = Query(default="p95", description="median|p90|p95|avg"),
) -> dict:
    latest = benchmark_state.get_latest()
    if latest is None:
        return {
            "ok": True,
            "rows": [],
            "limit": limit,
            "note": "No benchmark run yet. Call POST /run first.",
        }

    metric_key = metric.strip().lower()
    if metric_key in {"avg", "mean"}:
        selector = lambda s: s.avg_ms
    elif metric_key in {"median", "p50", "p_50"}:
        selector = lambda s: s.median_ms
    elif metric_key in {"p90"}:
        selector = lambda s: s.p90_ms
    else:
        # default p95
        selector = lambda s: s.p95_ms

    # Aggregate per (provider, model) by averaging the selected per-prompt metric.
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in latest.metrics:
        if row.ttft.n <= 0:
            continue
        buckets[(row.provider, row.model)].append(selector(row.ttft))

    scored: list[dict] = []
    for (provider, model), values in buckets.items():
        if not values:
            continue
        scored.append(
            {
                "provider": provider,
                "model": model,
                "score_ms": float(mean(values)),
                "n_prompts": len(values),
            }
        )

    scored.sort(key=lambda r: r["score_ms"])
    return {
        "ok": True,
        "run_id": latest.run_id,
        "rows": scored[:limit],
        "limit": limit,
        "metric": metric_key,
    }