# LLM benchmark

Public, repeatable latency benchmarks for language and (eventually) voice models. The goal is to run fixed prompts on a schedule, record comparable metrics, and expose them through a simple API and frontend so results are easy to share and trust.

## Current focus

**Phase 1 — LLM inference.** Connect to multiple LLM providers, run a small set of prompts (short, medium, and long), and measure time-to-first-token (TTFT) and related statistics over time.

**Later — TTS and STT.** Extend the same ideas to text-to-speech and speech-to-text (similar TTFT-style metrics where they apply, plus any voice-specific evals or datasets you add on top).

## Metrics (LLM)

Primary signals we care about for each model and prompt class:

- Average TTFT  
- Median TTFT  
- P90 / P95 TTFT  
- Variance (or another spread measure)  

The same percentile-style breakdowns can apply to TTS TTFT when that phase ships.

## How we plan to run it

1. Define a fixed prompt set and model list.  
2. Run inference on a cadence (for example every few minutes) via a small runner or scheduler.  
3. Persist raw timings and roll up aggregates for charts and tables.  
4. Serve results from this backend and visualize them in a separate frontend.

## Stack

Python backend: FastAPI, HTTP client for provider calls, SQLAlchemy + PostgreSQL for time-series style storage, NumPy for aggregates. See `pyproject.toml` for dependencies.

## Project layout (high level)

- **`app/providers/`** — LLM adapters first; TTS/STT adapters when those phases land.  
- **`app/prompts/`** — Prompt definitions (e.g. `prompts.json`) loaded by the runner.  
- **`app/benchmark/`** — Run orchestration, metric math, and shared schemas (`runner`, `metrics`, `schemas`).  
- **`app/database/`** — Persistence.  
- **`app/api/`** — FastAPI app (`main.py`) and **`app/api/routes/`** — public endpoints (e.g. leaderboard, rolled-up metrics, raw series).  
- **`app/log_config.py`** — Central logging configuration.

This README will evolve as the LLM slice solidifies and TTS/STT are added.
