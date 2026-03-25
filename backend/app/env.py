# Load backend/.env once before other app modules read os.environ.

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

_loaded = False


def load_dotenv_if_needed() -> None:
    global _loaded
    if _loaded:
        return
    backend_root = Path(__file__).resolve().parent.parent
    load_dotenv(backend_root / ".env")
    _loaded = True
