from __future__ import annotations

import json
import os
from typing import Optional

import httpx

from app.providers.llm.base import BaseLLMProvider, LLMRunResult
from app.providers.llm.helpers import (
    finalize_success_result,
    perf_counter_now,
    streaming_generate_error_result,
)

# OpenAI-compatible Chat Completions API (streaming SSE: lines starting with "data: ").


class OpenAIProvider(BaseLLMProvider):
    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
        max_tokens: int = 150,
        temperature: float = 0.0,
    ) -> None:
        super().__init__(model=model)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set.")

    @property
    def provider_name(self) -> str:
        return "openai"

    async def generate(self, prompt: str) -> LLMRunResult:
        start_time = perf_counter_now()
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        first_token_time: Optional[float] = None
        end_time: Optional[float] = None
        output_chunks: list[str] = []
        usage = None

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line.removeprefix("data: ").strip()

                        # Stream end marker from OpenAI.
                        if data_str == "[DONE]":
                            end_time = perf_counter_now()
                            break

                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        if "usage" in event:
                            usage = event["usage"]

                        choices = event.get("choices", [])
                        if not choices:
                            continue

                        delta = choices[0].get("delta", {})
                        content_piece = delta.get("content")

                        if content_piece:
                            if first_token_time is None:
                                # First model token for TTFT.
                                first_token_time = perf_counter_now()
                            output_chunks.append(content_piece)

            if end_time is None:
                end_time = perf_counter_now()

            input_tokens = usage.get("prompt_tokens") if usage else None
            output_tokens = usage.get("completion_tokens") if usage else None

            return finalize_success_result(
                provider=self.provider_name,
                model=self.model,
                prompt=prompt,
                output_text="".join(output_chunks),
                start_time=start_time,
                first_token_time=first_token_time,
                end_time=end_time,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        except Exception as exc:
            return streaming_generate_error_result(
                self.provider_name,
                self.model,
                prompt,
                start_time,
                exc,
            )
