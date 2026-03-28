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

## Backend Stack

Python backend: FastAPI, HTTP client for provider calls, SQLAlchemy + PostgreSQL for time-series style storage, NumPy for aggregates, APScheduler for periodic runs. See `pyproject.toml` for dependencies.

## How to run

1. **Install dependencies** (from this `backend/` directory, with [uv](https://github.com/astral-sh/uv)):

   ```bash
   cd backend
   uv sync
   ```

2. **Start PostgreSQL.** Easiest is Docker from this directory (Compose v2: `docker compose`; v1: `docker-compose`):

   ```bash
   docker compose up -d postgres
   ```

3. **Configure environment.** Copy the example file and set at least `DATABASE_URL` (and provider API keys for real benchmarks):

   ```bash
   cp .env.example .env
   ```

   The app loads `backend/.env` on startup (and when the benchmark runner reads env vars). Use a URL like:

   `postgresql+psycopg2://llm_bench:llm_bench@localhost:5432/llm_bench`

   matching the `docker-compose.yml` defaults.

4. **Run the API** (creates tables on startup, starts the optional scheduler):

   ```bash
   uv run uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Trigger a run manually** (optional; scheduled runs also call the same path):

   ```bash
   curl -X POST http://localhost:8000/run
   ```

**Scheduler:** With `LLM_BENCH_SCHEDULER_ENABLED=1` (default), the process runs `execute_benchmark_run` on an interval (`LLM_BENCH_SCHEDULE_INTERVAL_SECONDS`, default `300`). Set `LLM_BENCH_SCHEDULER_ENABLED=0` to disable periodic runs while keeping `POST /run`.

**Benchmark targets:** See `app/benchmark/runner.py` — `OPENAI_API_KEY` plus optional `LLM_BENCH_TARGETS` or per-provider `*_BENCH_MODEL` variables.

**API — latest vs history:** `GET /metrics/latest` and `GET /leaderboard/` use the **most recent** run only. **`GET /metrics/history`** returns TTFT scores **per model over many saved runs** (query params: `limit_runs`, `metric`, optional `provider` / `model`). The Streamlit app charts this under **TTFT over time**.

## Project layout (high level)

- **`app/providers/llm/`** — LLM adapters (OpenAI, Anthropic, shared helpers). Other provider types can live under **`app/providers/`** (e.g. TTS/STT) when you add them.  
- **`app/prompts/`** — Prompt definitions (e.g. `prompts.json`) loaded by the runner.  
- **`app/benchmark/`** — Run orchestration, metric math, shared schemas (`runner`, `metrics`, `ttft_scores`, `schemas`), `run_service` (persist + state), and `scheduler` (interval jobs).  
- **`app/env.py`** — Loads `backend/.env` once before other modules read environment variables.  
- **`app/database/`** — Persistence.  
- **`app/api/`** — FastAPI app (`main.py`) and **`app/api/routes/`** — public endpoints (e.g. leaderboard, rolled-up metrics, raw series, **`/metrics/history`**).  
- **`frontend/`** — Streamlit dashboard (`streamlit run app.py`).  
- **`app/log_config.py`** — Central logging configuration.

This README will evolve as the LLM slice solidifies and TTS/STT are added.
