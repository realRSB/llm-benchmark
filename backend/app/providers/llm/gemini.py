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

# Google Generative Language API: streamGenerateContent with SSE "data:" JSON chunks.


class GeminiProvider(BaseLLMProvider):
    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout: float = 60.0,
        max_output_tokens: int = 150,
        temperature: float = 0.0,
    ) -> None:
        super().__init__(model=model)
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def generate(self, prompt: str) -> LLMRunResult:
        start_time = perf_counter_now()
        # Key is passed as a query param (typical for this REST surface).
        url = (
            f"{self.base_url}/models/{self.model}:streamGenerateContent"
            f"?alt=sse&key={self.api_key}"
        )
        headers = {
            "Content-Type": "application/json",
        }
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_output_tokens,
            },
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

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line.removeprefix("data: ").strip()

                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        candidates = event.get("candidates", [])
                        if candidates:
                            content = candidates[0].get("content", {})
                            parts = content.get("parts", [])
                            for part in parts:
                                text_piece = part.get("text")
                                if text_piece:
                                    if first_token_time is None:
                                        first_token_time = perf_counter_now()
                                    output_chunks.append(text_piece)

                        usage = event.get("usageMetadata", {})
                        if usage:
                            input_tokens = usage.get("promptTokenCount", input_tokens)
                            output_tokens = usage.get("candidatesTokenCount", output_tokens)

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
