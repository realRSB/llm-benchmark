from collections import defaultdict

from fastapi import APIRouter, Query

from app.benchmark.state import benchmark_state
from app.benchmark.ttft_scores import normalize_ttft_metric_key, ttft_score_ms
from app.database import get_latest_benchmark_run

# Leaderboard endpoints show best models/providers based on aggregated metrics.
router: APIRouter = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

__all__ = ["router"]


@router.get("/")
async def leaderboard(
    limit: int = Query(default=20, ge=1, le=200),
    metric: str = Query(
        default="p95",
        description="avg|median|p90|p95 — computed across all prompt TTFTs for each model in the latest run",
    ),
) -> dict:
    latest = get_latest_benchmark_run() or benchmark_state.get_latest()
    if latest is None:
        return {
            "ok": True,
            "rows": [],
            "limit": limit,
            "note": "No benchmark run yet. Call POST /run first.",
        }

    metric_key = normalize_ttft_metric_key(metric)

    # Use raw per-call TTFTs so avg / median / p90 / p95 differ across prompts (rolled-up
    # MetricRow has n=1 per prompt, so averaging those stats made every selector identical).
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for s in latest.samples:
        if not s.success or s.ttft_ms < 0:
            continue
        buckets[(s.provider, s.model)].append(s.ttft_ms)

    scored: list[dict] = []
    for (provider, model), values in buckets.items():
        if not values:
            continue
        score = ttft_score_ms(values, metric_key)
        if score < 0:
            continue
        scored.append(
            {
                "provider": provider,
                "model": model,
                "score_ms": score,
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