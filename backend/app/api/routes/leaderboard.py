from fastapi import APIRouter, Query

# Leaderboard endpoints show best models/providers based on aggregated metrics.
router: APIRouter = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

__all__ = ["router"]


@router.get("/")
async def leaderboard(
    limit: int = Query(default=20, ge=1, le=200),
) -> dict:
    # Placeholder until aggregation logic + DB persistence are wired.
    return {
        "ok": True,
        "rows": [],
        "limit": limit,
        "note": "aggregations not wired yet",
    }