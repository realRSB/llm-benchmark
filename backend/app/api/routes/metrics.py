from fastapi import APIRouter, Query

# Metrics endpoints for rolled-up latency stats (p50/p90/p95, etc.).
router: APIRouter = APIRouter(prefix="/metrics", tags=["metrics"])

__all__ = ["router"]


@router.get("/latest")
async def latest_metrics(limit: int = Query(default=20, ge=1, le=500)) -> dict:
    # Placeholder until benchmark runner + DB persistence are wired.
    return {
        "ok": True,
        "items": [],
        "limit": limit,
        "note": "runner/DB not wired yet",
    }