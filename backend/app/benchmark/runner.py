from __future__ import annotations

import os
from datetime import datetime, timezone

from app.env import load_dotenv_if_needed

load_dotenv_if_needed()
from typing import Iterable, Optional
from uuid import uuid4

from app.benchmark.metrics import aggregate_ttft_metrics
from app.benchmark.schemas import BenchmarkRun, BenchmarkTarget, TimingSample
from app.prompts.loader import list_prompts
from app.providers.llm import LLMRunResult, get_provider


def _render_prompt_from_messages(messages: Iterable[object]) -> str:
    # messages items come from Pydantic prompt loader (ChatMessage model).
    system_parts: list[str] = []
    user_parts: list[str] = []

    for m in messages:
        role = getattr(m, "role", None)
        content = getattr(m, "content", "")
        if role == "system":
            system_parts.append(str(content))
        elif role == "user":
            user_parts.append(str(content))

    # Providers in this repo take a single prompt string (not a messages array).
    # We preserve system/user separation by explicitly labeling them.
    system_text = "\n\n".join(f"System:\n{txt}" for txt in system_parts).strip()
    user_text = "\n\n".join(f"User:\n{txt}" for txt in user_parts).strip()

    if system_text and user_text:
        return f"{system_text}\n\n{user_text}"
    return system_text or user_text


def _parse_targets_from_env() -> list[BenchmarkTarget]:
    targets_raw = os.getenv("LLM_BENCH_TARGETS", "").strip()
    targets: list[BenchmarkTarget] = []

    if targets_raw:
        # Accept comma/semicolon separated: openai:model,anthropic:model;gemini:model
        parts = [p.strip() for p in targets_raw.replace(";", ",").split(",") if p.strip()]
        for part in parts:
            if ":" not in part:
                continue
            provider, model = part.split(":", 1)
            provider = provider.strip()
            model = model.strip()
            if provider and model:
                targets.append(BenchmarkTarget(provider=provider, model=model))
        return targets

    # Defaults: only enable OpenAI by default, unless you set other bench models.
    openai_bench_model = os.getenv("OPENAI_BENCH_MODEL", "").strip() or "gpt-4o-mini"
    if os.getenv("OPENAI_API_KEY"):
        targets.append(BenchmarkTarget(provider="openai", model=openai_bench_model))

    anthropic_bench_model = os.getenv("ANTHROPIC_BENCH_MODEL", "").strip()
    if anthropic_bench_model and os.getenv("ANTHROPIC_API_KEY"):
        targets.append(BenchmarkTarget(provider="anthropic", model=anthropic_bench_model))

    gemini_bench_model = os.getenv("GEMINI_BENCH_MODEL", "").strip()
    if gemini_bench_model and os.getenv("GEMINI_API_KEY"):
        targets.append(BenchmarkTarget(provider="gemini", model=gemini_bench_model))

    return targets


def _parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _should_store_output_text() -> bool:
    raw = os.getenv("LLM_BENCH_STORE_OUTPUT_TEXT", "0").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _output_text_max_chars() -> int:
    return _parse_int_env("LLM_BENCH_OUTPUT_TEXT_MAX_CHARS", 2000)


async def run_benchmark_once() -> BenchmarkRun:
    run_id = str(uuid4())
    started_at = datetime.now(timezone.utc)

    targets = _parse_targets_from_env()
    if not targets:
        finished_at = datetime.now(timezone.utc)
        return BenchmarkRun(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            targets=[],
            samples=[],
            metrics=[],
        )

    prompts = list_prompts()
    max_prompts = _parse_int_env("LLM_BENCH_MAX_PROMPTS", len(prompts))
    prompts = prompts[:max_prompts]

    store_output = _should_store_output_text()
    max_chars = _output_text_max_chars()

    samples: list[TimingSample] = []

    # Sequential execution for correctness and predictable TTFT measurement.
    for prompt in prompts:
        rendered = _render_prompt_from_messages(prompt.messages)

        for target in targets:
            provider = get_provider(target.provider, target.model)
            result: LLMRunResult = await provider.generate(rendered)

            output_text: Optional[str] = None
            if store_output and result.output_text:
                output_text = result.output_text[:max_chars]

            samples.append(
                TimingSample(
                    provider=result.provider,
                    model=result.model,
                    prompt_id=prompt.id,
                    prompt_category=prompt.category,  # type: ignore[arg-type]
                    ttft_ms=result.ttft_ms,
                    total_latency_ms=result.total_latency_ms,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    success=result.success,
                    error_message=result.error_message,
                    output_text=output_text,
                )
            )

    metrics = aggregate_ttft_metrics(samples)
    finished_at = datetime.now(timezone.utc)

    return BenchmarkRun(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        targets=targets,
        samples=samples,
        metrics=metrics,
    )
