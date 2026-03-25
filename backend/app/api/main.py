from fastapi import FastAPI

from app.api.routes.leaderboard import router as leaderboard_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.raw_data import router as raw_data_router

# FastAPI entrypoint. Routers are included from app/api/routes.
app = FastAPI(title="LLM Benchmark API", version="0.1.0")

app.include_router(metrics_router)
app.include_router(leaderboard_router)
app.include_router(raw_data_router)


@app.get("/health")
async def health() -> dict:
    # Simple liveness endpoint for the frontend / uptime checks.
    return {"status": "ok"}