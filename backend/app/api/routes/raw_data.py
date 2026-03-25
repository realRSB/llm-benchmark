from fastapi import APIRouter, Query

# Raw-series endpoints are useful for transparency/debugging (per-run TTFT samples, etc.).
router: APIRouter = APIRouter(prefix="/rawdata", tags=["rawdata"])

__all__ = ["router"]


@router.get("/")
async def raw_data(
    model: str | None = None,
    prompt_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=2000),
) -> dict:
    # Placeholder until benchmark runner + DB persistence are wired.
    return {
        "ok": True,
        "items": [],
        "limit": limit,
        "filter": {"model": model, "prompt_id": prompt_id},
        "note": "DB not wired yet",
    }