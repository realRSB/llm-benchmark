# Load the prompt definitions from prompts.json

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

_PROMPTS_PATH = Path(__file__).resolve().parent / "prompts.json"


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class PromptSpec(BaseModel):
    id: str
    category: Literal["short", "medium", "long"]
    label: str
    messages: list[ChatMessage] = Field(min_length=1)


class PromptsFile(BaseModel):
    version: int
    description: str
    prompts: list[PromptSpec] = Field(min_length=1)


@lru_cache
def load_prompts() -> PromptsFile:
    # Load and validate prompts.json (cached).
    raw = _PROMPTS_PATH.read_text(encoding="utf-8")
    return PromptsFile.model_validate_json(raw)


def list_prompts(*, category: str | None = None) -> list[PromptSpec]:
    # Return all prompts, optionally filtered by category (short | medium | long).
    file = load_prompts()
    prompts = file.prompts
    if category is None:
        return prompts
    return [p for p in prompts if p.category == category]
