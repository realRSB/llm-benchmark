from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import numpy as np

from app.benchmark.schemas import LatencyStats, MetricRow, TimingSample, TTFTStats

# Roll-up rules:
# - One TimingSample contributes at most once per (provider, model, prompt_id, category).
# - Only successful calls with both ttft_ms and total_latency_ms measured (>= 0) are included
#   so TTFT and total_latency stats always share the same n per bucket.
# - avg / median / p90 / p95 use numpy; variance is population variance (ddof=0), same units as ms².


def _ttft_stats(values_ms: list[float]) -> TTFTStats:
    # Assumes values_ms already filtered to successful samples with valid timings.
    arr = np.asarray(values_ms, dtype=float)
    n = int(arr.shape[0])
    if n == 0:
        return TTFTStats(
            n=0,
            avg_ms=-1.0,
            median_ms=-1.0,
            p90_ms=-1.0,
            p95_ms=-1.0,
            variance_ms=-1.0,
        )

    return TTFTStats(
        n=n,
        avg_ms=float(np.mean(arr)),
        median_ms=float(np.median(arr)),
        p90_ms=float(np.percentile(arr, 90)),
        p95_ms=float(np.percentile(arr, 95)),
        variance_ms=float(np.var(arr, ddof=0)),
    )


def _latency_stats(values_ms: list[float]) -> LatencyStats:
    arr = np.asarray(values_ms, dtype=float)
    n = int(arr.shape[0])
    if n == 0:
        return LatencyStats(
            n=0,
            avg_ms=-1.0,
            median_ms=-1.0,
            p90_ms=-1.0,
            p95_ms=-1.0,
            variance_ms=-1.0,
        )

    return LatencyStats(
        n=n,
        avg_ms=float(np.mean(arr)),
        median_ms=float(np.median(arr)),
        p90_ms=float(np.percentile(arr, 90)),
        p95_ms=float(np.percentile(arr, 95)),
        variance_ms=float(np.var(arr, ddof=0)),
    )


def aggregate_ttft_metrics(samples: Iterable[TimingSample]) -> list[MetricRow]:
    # Group by (provider, model, prompt_id, prompt_category).
    grouped_ttft: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    grouped_total: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)

    for s in samples:
        if not s.success:
            continue
        # Providers use -1.0 for "not measured"; keep TTFT and total_latency lists aligned.
        if s.ttft_ms < 0 or s.total_latency_ms < 0:
            continue
        key = (s.provider, s.model, s.prompt_id, s.prompt_category)
        grouped_ttft[key].append(s.ttft_ms)
        grouped_total[key].append(s.total_latency_ms)

    rows: list[MetricRow] = []
    for (provider, model, prompt_id, prompt_category), ttft_values in grouped_ttft.items():
        ttft_stats = _ttft_stats(ttft_values)
        total_stats = _latency_stats(grouped_total.get((provider, model, prompt_id, prompt_category), []))
        rows.append(
            MetricRow(
                provider=provider,
                model=model,
                prompt_id=prompt_id,
                prompt_category=prompt_category,  # type: ignore[arg-type]
                ttft=ttft_stats,
                total_latency=total_stats,
            )
        )

    # Stable ordering for UI tables.
    rows.sort(
        key=lambda r: (
            r.prompt_category,
            r.prompt_id,
            r.provider,
            r.model,
        )
    )
    return rows
