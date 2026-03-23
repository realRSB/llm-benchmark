from __future__ import annotations

from app.providers.llm.anthropic import AnthropicProvider
from app.providers.llm.base import BaseLLMProvider
from app.providers.llm.gemini import GeminiProvider
from app.providers.llm.openai import OpenAIProvider


def get_provider(provider_name: str, model: str) -> BaseLLMProvider:
    # Maps a short name (e.g. "openai") to a concrete provider; keys are case-insensitive.
    normalized = provider_name.strip().lower()

    if normalized == "openai":
        return OpenAIProvider(model=model)
    if normalized == "anthropic":
        return AnthropicProvider(model=model)
    if normalized == "gemini":
        return GeminiProvider(model=model)

    raise ValueError(f"Unsupported provider: {provider_name}")
