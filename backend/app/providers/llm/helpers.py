from __future__ import annotations

import time
from typing import Optional

import httpx

from app.providers.llm.base import LLMRunResult

# Shared timing and LLMRunResult builders for all streaming providers.


def perf_counter_now() -> float:
    # Monotonic clock for latency.
    return time.perf_counter()


def safe_word_count(text: str) -> int:
    # Rough output size when the API does not return token counts (not real tokens).
    if not text.strip():
        return 0
    return len(text.split())


def build_error_result(
    provider: str,
    model: str,
    prompt: str,
    start_time: float,
    error_message: str,
) -> LLMRunResult:
    # Failed run: ttft_ms = -1 means "not measured".
    return LLMRunResult(
        provider=provider,
        model=model,
        prompt=prompt,
        output_text="",
        input_tokens=None,
        output_tokens=None,
        ttft_ms=-1.0,
        total_latency_ms=(perf_counter_now() - start_time) * 1000,
        tokens_per_second=None,
        success=False,
        error_message=error_message,
    )


def finalize_success_result(
    provider: str,
    model: str,
    prompt: str,
    output_text: str,
    start_time: float,
    first_token_time: Optional[float],
    end_time: float,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
) -> LLMRunResult:
    # No first chunk means we treat the run as failed even if the HTTP stream completed.
    if first_token_time is None:
        return LLMRunResult(
            provider=provider,
            model=model,
            prompt=prompt,
            output_text=output_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            ttft_ms=-1.0,
            total_latency_ms=(end_time - start_time) * 1000,
            tokens_per_second=None,
            success=False,
            error_message="No streamed token or text chunk was received.",
        )

    if output_tokens is None:
        output_tokens = safe_word_count(output_text)

    generation_seconds = max(end_time - first_token_time, 1e-9)
    tps = output_tokens / generation_seconds if output_tokens > 0 else 0.0

    return LLMRunResult(
        provider=provider,
        model=model,
        prompt=prompt,
        output_text=output_text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        ttft_ms=(first_token_time - start_time) * 1000,
        total_latency_ms=(end_time - start_time) * 1000,
        tokens_per_second=tps,
        success=True,
        error_message=None,
    )


def streaming_generate_error_result(
    provider: str,
    model: str,
    prompt: str,
    start_time: float,
    exc: BaseException,
) -> LLMRunResult:
    # Normalize httpx (and anything else) into the same LLMRunResult error shape.
    if isinstance(exc, httpx.HTTPStatusError):
        return build_error_result(
            provider,
            model,
            prompt,
            start_time,
            f"HTTP error {exc.response.status_code}: {exc.response.text}",
        )
    if isinstance(exc, httpx.HTTPError):
        return build_error_result(
            provider,
            model,
            prompt,
            start_time,
            f"HTTP client error: {str(exc)}",
        )
    return build_error_result(
        provider,
        model,
        prompt,
        start_time,
        f"Unexpected error: {str(exc)}",
    )
