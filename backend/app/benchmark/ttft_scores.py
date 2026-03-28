"""Shared TTFT reductions across prompts (used by leaderboard and history API)."""

from __future__ import annotations

import numpy as np


def normalize_ttft_metric_key(metric: str) -> str:
    k = metric.strip().lower()
    if k in {"mean"}:
        k = "avg"
    if k not in {"avg", "median", "p50", "p_50", "p90", "p95"}:
        return "p95"
    if k in {"p50", "p_50"}:
        return "median"
    return k


def ttft_score_ms(values_ms: list[float], metric_key: str) -> float:
    """Single score from a list of per-prompt TTFT samples (one run, one model)."""
    arr = np.asarray(values_ms, dtype=float)
    if arr.size == 0:
        return -1.0
    k = normalize_ttft_metric_key(metric_key)
    if k == "avg":
        return float(np.mean(arr))
    if k == "median":
        return float(np.median(arr))
    if k == "p90":
        return float(np.percentile(arr, 90))
    return float(np.percentile(arr, 95))
