from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel

# Outcome of one streaming LLM call: TTFT, total time, optional token counts, success/error.


class LLMRunResult(BaseModel):
    provider: str
    model: str
    prompt: str

    output_text: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    ttft_ms: float
    total_latency_ms: float
    tokens_per_second: Optional[float] = None

    success: bool
    error_message: Optional[str] = None


# Abstract adapter: each vendor implements generate() with the same result shape.


class BaseLLMProvider(ABC):
    def __init__(self, model: str) -> None:
        self.model = model

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate(self, prompt: str) -> LLMRunResult:
        raise NotImplementedError
