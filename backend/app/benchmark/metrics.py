from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import numpy as np

from app.benchmark.schemas import MetricRow, TimingSample, TTFTStats


def _ttft_stats(values_ms: list[float]) -> TTFTStats:
    # Assumes values_ms already filtered to successful samples.
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


def aggregate_ttft_metrics(samples: Iterable[TimingSample]) -> list[MetricRow]:
    # Group by (provider, model, prompt_id, prompt_category).
    grouped: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)

    for s in samples:
        if not s.success:
            continue
        # Providers use -1.0 for "ttft not measured"
        if s.ttft_ms < 0:
            continue
        key = (s.provider, s.model, s.prompt_id, s.prompt_category)
        grouped[key].append(s.ttft_ms)

    rows: list[MetricRow] = []
    for (provider, model, prompt_id, prompt_category), values in grouped.items():
        stats = _ttft_stats(values)
        rows.append(
            MetricRow(
                provider=provider,
                model=model,
                prompt_id=prompt_id,
                prompt_category=prompt_category,  # type: ignore[arg-type]
                ttft=stats,
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
