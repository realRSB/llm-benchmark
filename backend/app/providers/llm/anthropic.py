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

# Anthropic Messages API over SSE: optional "event:" lines plus "data:" JSON payloads.


class AnthropicProvider(BaseLLMProvider):
    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: str = "https://api.anthropic.com",
        timeout: float = 60.0,
        max_tokens: int = 150,
        anthropic_version: str = "2023-06-01",
    ) -> None:
        super().__init__(model=model)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.anthropic_version = anthropic_version

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set.")

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def generate(self, prompt: str) -> LLMRunResult:
        start_time = perf_counter_now()
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "stream": True,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        first_token_time: Optional[float] = None
        end_time: Optional[float] = None
        output_chunks: list[str] = []
        input_tokens: Optional[int] = None
        output_tokens: Optional[int] = None

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()

                    # Last seen event name when the JSON body omits "type".
                    event_type: Optional[str] = None

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        if line.startswith("event: "):
                            event_type = line.removeprefix("event: ").strip()
                            continue

                        if not line.startswith("data: "):
                            continue

                        data_str = line.removeprefix("data: ").strip()

                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        current_type = event.get("type") or event_type

                        if current_type == "content_block_delta":
                            delta = event.get("delta", {})
                            text_piece = delta.get("text")
                            if text_piece:
                                if first_token_time is None:
                                    first_token_time = perf_counter_now()
                                output_chunks.append(text_piece)

                        elif current_type == "message_start":
                            message = event.get("message", {})
                            usage = message.get("usage", {})
                            input_tokens = usage.get("input_tokens")

                        elif current_type == "message_delta":
                            usage = event.get("usage", {})
                            if usage:
                                output_tokens = usage.get("output_tokens", output_tokens)

                        elif current_type == "message_stop":
                            end_time = perf_counter_now()
                            break

            if end_time is None:
                end_time = perf_counter_now()

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
