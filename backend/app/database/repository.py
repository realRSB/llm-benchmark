# Save and load benchmark runs (used by FastAPI and CLI).

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.benchmark.schemas import (
    BenchmarkRun,
    BenchmarkTarget,
    MetricRow,
    TimingSample,
    TTFTStats,
)
from app.database.db import SessionLocal
from app.database.models import BenchmarkRunRow, TTFTMetricRow, TimingSampleRow


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
