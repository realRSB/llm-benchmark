from __future__ import annotations

import threading
from typing import Optional

from app.benchmark.schemas import BenchmarkRun


class _BenchmarkState:
    # Simple in-memory singleton for prototyping. Later this can be backed by Postgres.
    _lock = threading.Lock()
    _latest_run: Optional[BenchmarkRun] = None

    def set_latest(self, run: BenchmarkRun) -> None:
        with self._lock:
            self._latest_run = run

    def get_latest(self) -> Optional[BenchmarkRun]:
        with self._lock:
            return self._latest_run


benchmark_state = _BenchmarkState()

