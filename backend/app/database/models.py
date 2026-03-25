# ORM tables for benchmark runs, per-call samples, and rolled-up TTFT metrics.

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BenchmarkRunRow(Base):
    __tablename__ = "benchmark_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Serialized list[BenchmarkTarget] as JSON.
    targets_json: Mapped[list] = mapped_column(JSON)


class TimingSampleRow(Base):
    __tablename__ = "timing_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("benchmark_runs.run_id"), index=True)

    provider: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str] = mapped_column(String(256), index=True)
    prompt_id: Mapped[str] = mapped_column(String(64), index=True)
    prompt_category: Mapped[str] = mapped_column(String(16), index=True)

    ttft_ms: Mapped[float] = mapped_column(Float)
    total_latency_ms: Mapped[float] = mapped_column(Float)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    success: Mapped[bool] = mapped_column(Boolean)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class TTFTMetricRow(Base):
    __tablename__ = "ttft_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("benchmark_runs.run_id"), index=True)

    provider: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str] = mapped_column(String(256), index=True)
    prompt_id: Mapped[str] = mapped_column(String(64), index=True)
    prompt_category: Mapped[str] = mapped_column(String(16), index=True)

    n: Mapped[int] = mapped_column(Integer)
    avg_ms: Mapped[float] = mapped_column(Float)
    median_ms: Mapped[float] = mapped_column(Float)
    p90_ms: Mapped[float] = mapped_column(Float)
    p95_ms: Mapped[float] = mapped_column(Float)
    variance_ms: Mapped[float] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "provider",
            "model",
            "prompt_id",
            name="uq_ttft_metric_prompt",
        ),
    )
