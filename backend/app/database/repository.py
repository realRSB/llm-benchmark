# Save and load benchmark runs (used by FastAPI and CLI).

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import Integer, cast, delete, func, select
from sqlalchemy.orm import Session

from app.benchmark.schemas import (
    BenchmarkRun,
    BenchmarkTarget,
    LatencyStats,
    MetricRow,
    TimingSample,
    TTFTStats,
)
from app.benchmark.ttft_scores import normalize_ttft_metric_key, ttft_score_ms
from app.database.db import SessionLocal
from app.database.models import (
    BenchmarkRunRow,
    TTFTMetricRow,
    TimingSampleRow,
    TotalLatencyMetricRow,
)


def save_benchmark_run(run: BenchmarkRun) -> None:
    with SessionLocal() as session:
        _save_benchmark_run_session(session, run)
        session.commit()


def _save_benchmark_run_session(session: Session, run: BenchmarkRun) -> None:
    # Replace if re-run with same run_id (unlikely; run_id is UUID).
    existing = session.scalar(
        select(BenchmarkRunRow).where(BenchmarkRunRow.run_id == run.run_id)
    )
    if existing:
        session.execute(
            delete(TimingSampleRow).where(TimingSampleRow.run_id == run.run_id)
        )
        session.execute(delete(TTFTMetricRow).where(TTFTMetricRow.run_id == run.run_id))
        session.execute(
            delete(TotalLatencyMetricRow).where(TotalLatencyMetricRow.run_id == run.run_id)
        )
        session.execute(
            delete(BenchmarkRunRow).where(BenchmarkRunRow.run_id == run.run_id)
        )
        session.flush()

    session.add(
        BenchmarkRunRow(
            run_id=run.run_id,
            started_at=run.started_at,
            finished_at=run.finished_at,
            targets_json=[t.model_dump() for t in run.targets],
        )
    )

    for s in run.samples:
        session.add(
            TimingSampleRow(
                run_id=run.run_id,
                provider=s.provider,
                model=s.model,
                prompt_id=s.prompt_id,
                prompt_category=s.prompt_category,
                ttft_ms=s.ttft_ms,
                total_latency_ms=s.total_latency_ms,
                input_tokens=s.input_tokens,
                output_tokens=s.output_tokens,
                success=s.success,
                error_message=s.error_message,
                output_text=s.output_text,
            )
        )

    for m in run.metrics:
        session.add(
            TTFTMetricRow(
                run_id=run.run_id,
                provider=m.provider,
                model=m.model,
                prompt_id=m.prompt_id,
                prompt_category=m.prompt_category,
                n=m.ttft.n,
                avg_ms=m.ttft.avg_ms,
                median_ms=m.ttft.median_ms,
                p90_ms=m.ttft.p90_ms,
                p95_ms=m.ttft.p95_ms,
                variance_ms=m.ttft.variance_ms,
            )
        )
        session.add(
            TotalLatencyMetricRow(
                run_id=run.run_id,
                provider=m.provider,
                model=m.model,
                prompt_id=m.prompt_id,
                prompt_category=m.prompt_category,
                n=m.total_latency.n,
                avg_ms=m.total_latency.avg_ms,
                median_ms=m.total_latency.median_ms,
                p90_ms=m.total_latency.p90_ms,
                p95_ms=m.total_latency.p95_ms,
                variance_ms=m.total_latency.variance_ms,
            )
        )


def get_latest_benchmark_run() -> BenchmarkRun | None:
    with SessionLocal() as session:
        row = session.scalar(
            select(BenchmarkRunRow).order_by(BenchmarkRunRow.finished_at.desc()).limit(1)
        )
        if row is None:
            return None
        return _benchmark_run_from_row(session, row)


def _benchmark_run_from_row(session: Session, row: BenchmarkRunRow) -> BenchmarkRun:
    targets = [BenchmarkTarget(**t) for t in row.targets_json]

    sample_rows = session.scalars(
        select(TimingSampleRow)
        .where(TimingSampleRow.run_id == row.run_id)
        .order_by(TimingSampleRow.id.asc())
    ).all()
    samples = [
        TimingSample(
            provider=r.provider,
            model=r.model,
            prompt_id=r.prompt_id,
            prompt_category=r.prompt_category,  # type: ignore[arg-type]
            ttft_ms=r.ttft_ms,
            total_latency_ms=r.total_latency_ms,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            success=r.success,
            error_message=r.error_message,
            output_text=r.output_text,
        )
        for r in sample_rows
    ]

    metric_rows = session.scalars(
        select(TTFTMetricRow)
        .where(TTFTMetricRow.run_id == row.run_id)
        .order_by(
            TTFTMetricRow.prompt_category.asc(),
            TTFTMetricRow.prompt_id.asc(),
            TTFTMetricRow.provider.asc(),
            TTFTMetricRow.model.asc(),
        )
    ).all()

    latency_rows = session.scalars(
        select(TotalLatencyMetricRow)
        .where(TotalLatencyMetricRow.run_id == row.run_id)
        .order_by(
            TotalLatencyMetricRow.prompt_category.asc(),
            TotalLatencyMetricRow.prompt_id.asc(),
            TotalLatencyMetricRow.provider.asc(),
            TotalLatencyMetricRow.model.asc(),
        )
    ).all()
    latency_by_key = {
        (r.provider, r.model, r.prompt_id, r.prompt_category): r for r in latency_rows
    }

    metrics = [
        MetricRow(
            provider=r.provider,
            model=r.model,
            prompt_id=r.prompt_id,
            prompt_category=r.prompt_category,  # type: ignore[arg-type]
            ttft=TTFTStats(
                n=r.n,
                avg_ms=r.avg_ms,
                median_ms=r.median_ms,
                p90_ms=r.p90_ms,
                p95_ms=r.p95_ms,
                variance_ms=r.variance_ms,
            ),
            total_latency=LatencyStats(
                n=latency_by_key[(r.provider, r.model, r.prompt_id, r.prompt_category)].n
                if (r.provider, r.model, r.prompt_id, r.prompt_category) in latency_by_key
                else 0,
                avg_ms=latency_by_key[(r.provider, r.model, r.prompt_id, r.prompt_category)].avg_ms
                if (r.provider, r.model, r.prompt_id, r.prompt_category) in latency_by_key
                else -1.0,
                median_ms=latency_by_key[(r.provider, r.model, r.prompt_id, r.prompt_category)].median_ms
                if (r.provider, r.model, r.prompt_id, r.prompt_category) in latency_by_key
                else -1.0,
                p90_ms=latency_by_key[(r.provider, r.model, r.prompt_id, r.prompt_category)].p90_ms
                if (r.provider, r.model, r.prompt_id, r.prompt_category) in latency_by_key
                else -1.0,
                p95_ms=latency_by_key[(r.provider, r.model, r.prompt_id, r.prompt_category)].p95_ms
                if (r.provider, r.model, r.prompt_id, r.prompt_category) in latency_by_key
                else -1.0,
                variance_ms=latency_by_key[(r.provider, r.model, r.prompt_id, r.prompt_category)].variance_ms
                if (r.provider, r.model, r.prompt_id, r.prompt_category) in latency_by_key
                else -1.0,
            ),
        )
        for r in metric_rows
    ]

    return BenchmarkRun(
        run_id=row.run_id,
        started_at=row.started_at,
        finished_at=row.finished_at,
        targets=targets,
        samples=samples,
        metrics=metrics,
    )


def get_total_benchmark_call_counts() -> tuple[list[dict[str, int | str]], int]:
    # All rows in timing_samples (every prompt × model call across all saved runs).
    with SessionLocal() as session:
        n_runs = session.scalar(select(func.count()).select_from(BenchmarkRunRow))
        n_runs = int(n_runs or 0)
        stmt = (
            select(
                TimingSampleRow.provider,
                TimingSampleRow.model,
                func.count().label("benchmark_calls"),
                func.sum(cast(TimingSampleRow.success, Integer)).label("successful"),
            )
            .group_by(TimingSampleRow.provider, TimingSampleRow.model)
            .order_by(TimingSampleRow.provider.asc(), TimingSampleRow.model.asc())
        )
        rows = session.execute(stmt).all()

    items: list[dict[str, int | str]] = []
    for provider, model, calls, succ in rows:
        calls_i = int(calls or 0)
        succ_i = int(succ or 0)
        items.append(
            {
                "provider": provider,
                "model": model,
                "benchmark_calls": calls_i,
                "successful": succ_i,
                "failed": max(calls_i - succ_i, 0),
            }
        )
    return items, n_runs


def get_ttft_history_series(
    *,
    limit_runs: int,
    metric_key: str,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Per (provider, model) time series of TTFT scores across saved runs (oldest → newest)."""
    mk = normalize_ttft_metric_key(metric_key)
    prov_f = provider.strip() if provider else None
    mod_f = model.strip() if model else None

    with SessionLocal() as session:
        run_rows = session.scalars(
            select(BenchmarkRunRow)
            .order_by(BenchmarkRunRow.finished_at.desc())
            .limit(limit_runs)
        ).all()

        if not run_rows:
            return {
                "metric": mk,
                "limit_runs": limit_runs,
                "n_runs_loaded": 0,
                "series": [],
            }

        runs_chrono = list(reversed(run_rows))
        run_ids = [r.run_id for r in run_rows]
        finished_map = {r.run_id: r.finished_at for r in run_rows}

        sample_rows = session.scalars(
            select(TimingSampleRow).where(TimingSampleRow.run_id.in_(run_ids))
        ).all()

    bucket: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for s in sample_rows:
        if not s.success or s.ttft_ms < 0:
            continue
        if prov_f is not None and s.provider != prov_f:
            continue
        if mod_f is not None and s.model != mod_f:
            continue
        bucket[(s.run_id, s.provider, s.model)].append(s.ttft_ms)

    series_map: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in runs_chrono:
        rid = run.run_id
        ft = finished_map[rid]
        for (r2, prov, mod), vals in bucket.items():
            if r2 != rid:
                continue
            score = ttft_score_ms(vals, mk)
            if score < 0:
                continue
            series_map[(prov, mod)].append(
                {
                    "run_id": rid,
                    "finished_at": ft.isoformat(),
                    "score_ms": round(score, 3),
                    "n_samples": len(vals),
                }
            )

    series: list[dict[str, Any]] = []
    for (prov, mod) in sorted(series_map.keys()):
        series.append(
            {
                "provider": prov,
                "model": mod,
                "points": series_map[(prov, mod)],
            }
        )

    return {
        "metric": mk,
        "limit_runs": limit_runs,
        "n_runs_loaded": len(run_rows),
        "series": series,
    }
