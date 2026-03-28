from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BenchmarkTarget(BaseModel):
    # provider = openai | anthropic
    provider: str
    model: str


class TimingSample(BaseModel):
    provider: str
    model: str
    prompt_id: str
    prompt_category: Literal["short", "medium", "long"]

    ttft_ms: float
    total_latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None

    success: bool
    error_message: str | None = None

    # Optional; may be blank if you disable output storage.
    output_text: str | None = None


class TTFTStats(BaseModel):
    n: int = Field(..., description="Successful samples with valid TTFT+total latency in this bucket")

    avg_ms: float
    median_ms: float
    p90_ms: float
    p95_ms: float
    variance_ms: float = Field(..., description="Population variance of latencies in ms² (ddof=0)")


class LatencyStats(BaseModel):
    n: int = Field(..., description="Same sample count as paired TTFTStats for this row")

    avg_ms: float
    median_ms: float
    p90_ms: float
    p95_ms: float
    variance_ms: float = Field(..., description="Population variance of latencies in ms² (ddof=0)")


class MetricRow(BaseModel):
    provider: str
    model: str
    prompt_id: str
    prompt_category: Literal["short", "medium", "long"]

    ttft: TTFTStats
    total_latency: LatencyStats


class BenchmarkRun(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime

    targets: list[BenchmarkTarget]
    samples: list[TimingSample]
    metrics: list[MetricRow]
