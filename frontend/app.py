"""
Streamlit UI for llm-benchmark FastAPI.

Run from repo: cd frontend && uv sync && uv run streamlit run app.py
Backend: cd ../backend && uv run uvicorn app.api.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import time
from typing import Any

import pandas as pd
import requests
import streamlit as st

DEFAULT_API_BASE = os.getenv("LLM_BENCH_API_BASE", "http://127.0.0.1:8000")


def _get(base: str, path: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> dict[str, Any]:
    url = f"{base.rstrip('/')}{path}"
    r = requests.get(url, params=params or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _post(base: str, path: str, timeout: float = 600.0) -> dict[str, Any]:
    url = f"{base.rstrip('/')}{path}"
    r = requests.post(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _format_elapsed(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _benchmark_status_card_html(
    *,
    run_index: int,
    total_runs: int,
    completed_runs: int,
    elapsed_s: float,
    phase: str,
) -> str:
    """waiting | between | done | stopped (user cancelled batch)."""
    total_runs = max(total_runs, 1)
    if phase == "done":
        pct = 100.0
        headline = f"{completed_runs} / {total_runs}"
        sub = "All benchmark runs finished"
    elif phase == "stopped":
        pct = min(100.0, 100.0 * (completed_runs / total_runs))
        headline = f"{completed_runs} / {total_runs}"
        sub = "Batch stopped — remaining runs skipped"
    elif phase == "waiting":
        pct = min(100.0, 100.0 * ((run_index - 1) / total_runs))
        headline = f"Run {run_index} / {total_runs}"
        sub = "Calling API (POST /run)…"
    else:
        pct = min(100.0, 100.0 * (completed_runs / total_runs))
        headline = f"{completed_runs} / {total_runs}"
        sub = "Run saved · continuing batch…"

    return f"""
<div style="
  background: linear-gradient(145deg, #0c1222 0%, #1a2744 48%, #132337 100%);
  border-radius: 14px;
  padding: 1.1rem 1.35rem;
  margin: 0 0 1rem 0;
  border: 1px solid rgba(56, 189, 248, 0.22);
  box-shadow:
    0 0 0 1px rgba(255,255,255,0.04) inset,
    0 12px 40px -12px rgba(15, 23, 42, 0.85);
  font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
">
  <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:flex-end; gap:1rem 1.5rem;">
    <div>
      <div style="font-size:0.68rem; font-weight:600; letter-spacing:0.14em; text-transform:uppercase; color:#64748b; margin-bottom:0.35rem;">
        Batch progress
      </div>
      <div style="font-size:1.65rem; font-weight:700; color:#f8fafc; line-height:1.1;">
        <span style="color:#38bdf8;">{headline}</span>
        <span style="font-size:0.95rem; font-weight:500; color:#475569;"> runs</span>
      </div>
      <div style="font-size:0.82rem; color:#94a3b8; margin-top:0.45rem;">{sub}</div>
    </div>
    <div style="text-align:right; min-width:7rem;">
      <div style="font-size:0.68rem; font-weight:600; letter-spacing:0.14em; text-transform:uppercase; color:#64748b; margin-bottom:0.35rem;">
        Elapsed
      </div>
      <div style="font-size:1.65rem; font-weight:700; font-variant-numeric:tabular-nums; font-family:ui-monospace, 'Cascadia Code', monospace; color:#e2e8f0; line-height:1.1;">
        {_format_elapsed(elapsed_s)}
      </div>
    </div>
  </div>
  <div style="margin-top:1rem; height:6px; background:rgba(148,163,184,0.12); border-radius:999px; overflow:hidden;">
    <div style="
      width:{pct}%;
      height:100%;
      border-radius:999px;
      background: linear-gradient(90deg, #22d3ee 0%, #38bdf8 35%, #818cf8 100%);
      box-shadow: 0 0 16px rgba(56, 189, 248, 0.45);
      transition: width 0.35s ease;
    "></div>
  </div>
</div>
"""


def _batch_state_clear() -> None:
    for k in (
        "_batch_in_progress",
        "_batch_remaining",
        "_batch_total",
        "_batch_t0",
        "_batch_results",
        "_batch_api_base",
        "_batch_user_cancelled",
    ):
        st.session_state.pop(k, None)


st.set_page_config(page_title="LLM Benchmark", layout="wide")
st.title("LLM Benchmark dashboard")

with st.sidebar:
    base = st.text_input("API base URL", DEFAULT_API_BASE, help="FastAPI server URL (same machine: http://127.0.0.1:8000)")
    run_count = st.number_input(
        "Benchmark runs",
        min_value=1,
        max_value=200,
        value=1,
        step=1,
        help="How many times to call POST /run in a row. Use 1 for a single run.",
    )
    col_a, col_b = st.columns(2)
    with col_a:
        do_run = st.button("Run benchmark", type="primary")
    with col_b:
        do_refresh = st.button("Refresh")

if do_run:
    n_start = int(run_count)
    st.session_state["_batch_in_progress"] = True
    st.session_state["_batch_remaining"] = n_start
    st.session_state["_batch_total"] = n_start
    st.session_state["_batch_results"] = []
    st.session_state["_batch_t0"] = time.perf_counter()
    st.session_state["_batch_api_base"] = base
    st.session_state["_batch_user_cancelled"] = False
    st.rerun()

# One POST per rerun so the Stop button can run between API calls.
if st.session_state.get("_batch_in_progress"):
    total_b = int(st.session_state.get("_batch_total") or 0)
    rem = int(st.session_state.get("_batch_remaining") or 0)
    t0_b = float(st.session_state.get("_batch_t0") or time.perf_counter())
    results_b: list[dict[str, Any]] = list(st.session_state.get("_batch_results") or [])
    base_b = str(st.session_state.get("_batch_api_base") or base)
    user_cancelled = bool(st.session_state.get("_batch_user_cancelled"))
    elapsed_b = time.perf_counter() - t0_b

    if rem == 0:
        status_final = st.empty()
        if user_cancelled:
            done_n = len(results_b)
            status_final.markdown(
                _benchmark_status_card_html(
                    run_index=min(done_n + 1, total_b),
                    total_runs=total_b,
                    completed_runs=done_n,
                    elapsed_s=elapsed_b,
                    phase="stopped",
                ),
                unsafe_allow_html=True,
            )
            if results_b:
                st.session_state["last_run"] = results_b[-1]
                st.session_state["last_batch_run_ids"] = [r.get("run_id", "") for r in results_b]
            st.warning(
                f"Batch **stopped** after **{done_n}** / **{total_b}** run(s). "
                "Anything already finished is saved on the server."
            )
            if done_n > 1:
                with st.expander("Run IDs before stop"):
                    st.code("\n".join(r.get("run_id", "") for r in results_b), language="text")
        else:
            status_final.markdown(
                _benchmark_status_card_html(
                    run_index=total_b,
                    total_runs=total_b,
                    completed_runs=total_b,
                    elapsed_s=elapsed_b,
                    phase="done",
                ),
                unsafe_allow_html=True,
            )
            if results_b:
                st.session_state["last_run"] = results_b[-1]
                st.session_state["last_batch_run_ids"] = [r.get("run_id", "") for r in results_b]
                last_b = results_b[-1]
                if total_b == 1:
                    st.success(
                        f"Run **{last_b.get('run_id', '')}** — "
                        f"{last_b.get('samples', 0)} samples, {last_b.get('metrics', 0)} metric rows."
                    )
                else:
                    total_samples = sum(int(r.get("samples") or 0) for r in results_b)
                    st.success(
                        f"Finished **{total_b}** benchmark runs — **{total_samples}** samples total (all runs). "
                        f"Latest run_id: **{last_b.get('run_id', '')}** "
                        f"({last_b.get('samples', 0)} samples, {last_b.get('metrics', 0)} metric rows)."
                    )
                    with st.expander("Run IDs in this batch"):
                        st.code("\n".join(r.get("run_id", "") for r in results_b), language="text")
        _batch_state_clear()
    else:
        run_index = total_b - rem + 1
        completed_runs = len(results_b)
        bar_col, stop_col = st.columns([5, 1])
        with stop_col:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(
                "Stop batch",
                type="secondary",
                key="stop_benchmark_batch",
                help="Stops after the current API call finishes (cannot interrupt mid-request).",
            ):
                st.session_state["_batch_remaining"] = 0
                st.session_state["_batch_user_cancelled"] = True
                st.rerun()
        with bar_col:
            status_slot = st.empty()
            status_slot.markdown(
                _benchmark_status_card_html(
                    run_index=run_index,
                    total_runs=total_b,
                    completed_runs=completed_runs,
                    elapsed_s=elapsed_b,
                    phase="waiting",
                ),
                unsafe_allow_html=True,
            )
        try:
            run_resp = _post(base_b, "/run")
            results_b.append(run_resp)
            st.session_state["_batch_results"] = results_b
            st.session_state["_batch_remaining"] = rem - 1
            new_rem = rem - 1
            elapsed_after = time.perf_counter() - t0_b
            if new_rem > 0:
                status_slot.markdown(
                    _benchmark_status_card_html(
                        run_index=run_index,
                        total_runs=total_b,
                        completed_runs=len(results_b),
                        elapsed_s=elapsed_after,
                        phase="between",
                    ),
                    unsafe_allow_html=True,
                )
                st.rerun()
            else:
                status_slot.markdown(
                    _benchmark_status_card_html(
                        run_index=total_b,
                        total_runs=total_b,
                        completed_runs=total_b,
                        elapsed_s=elapsed_after,
                        phase="done",
                    ),
                    unsafe_allow_html=True,
                )
                st.session_state["last_run"] = results_b[-1]
                st.session_state["last_batch_run_ids"] = [r.get("run_id", "") for r in results_b]
                last_b = results_b[-1]
                if total_b == 1:
                    st.success(
                        f"Run **{last_b.get('run_id', '')}** — "
                        f"{last_b.get('samples', 0)} samples, {last_b.get('metrics', 0)} metric rows."
                    )
                else:
                    total_samples = sum(int(r.get("samples") or 0) for r in results_b)
                    st.success(
                        f"Finished **{total_b}** benchmark runs — **{total_samples}** samples total (all runs). "
                        f"Latest run_id: **{last_b.get('run_id', '')}** "
                        f"({last_b.get('samples', 0)} samples, {last_b.get('metrics', 0)} metric rows)."
                    )
                    with st.expander("Run IDs in this batch"):
                        st.code("\n".join(r.get("run_id", "") for r in results_b), language="text")
                _batch_state_clear()
        except requests.RequestException as e:
            try:
                status_slot.empty()
            except Exception:
                pass
            st.session_state["_batch_in_progress"] = False
            st.session_state["_batch_remaining"] = 0
            _batch_state_clear()
            st.error(f"POST /run failed: {e}")

if do_refresh:
    st.rerun()

# --- Health ---
try:
    health = _get(base, "/health", timeout=5.0)
    st.caption(f"API: **{health.get('status', 'unknown')}** · `{base}`")
except requests.RequestException as e:
    st.warning(f"Cannot reach API at `{base}`: {e}")
    st.stop()

try:
    raw_payload = _get(base, "/rawdata/", params={"limit": 2000})
except requests.RequestException:
    raw_payload = {"items": [], "run_id": None, "note": None}

# --- All-time benchmark calls (every saved run in the database) ---
st.subheader("Benchmark calls per provider & model (all runs)")
try:
    stats_payload = _get(base, "/stats/benchmark-calls", timeout=30.0)
except requests.RequestException as e:
    stats_payload = {"ok": False, "items": [], "n_runs": 0, "total_benchmark_calls": 0}
    st.warning(f"Could not load totals (`GET /stats/benchmark-calls`): {e}")

stat_items = stats_payload.get("items") or []
if stat_items:
    n_runs = int(stats_payload.get("n_runs") or 0)
    total_calls = int(stats_payload.get("total_benchmark_calls") or 0)
    st.caption(
        f"**{total_calls:,}** benchmark API calls across **{n_runs:,}** saved run(s) in the database "
        "(each call = one prompt × model)."
    )
    counts = pd.DataFrame(stat_items)
    display_cols = [c for c in ["provider", "model", "benchmark_calls", "successful", "failed"] if c in counts.columns]
    st.dataframe(counts[display_cols], use_container_width=True, hide_index=True)
    chart_idx = counts["provider"].astype(str) + " / " + counts["model"].astype(str)
    chart_df = pd.DataFrame({"benchmark_calls": counts["benchmark_calls"].values}, index=chart_idx)
    st.markdown("**Total benchmark calls (all runs)**")
    st.bar_chart(chart_df, horizontal=True)
else:
    if stats_payload.get("ok") and not stat_items:
        st.caption("No timing samples in the database yet. Run a benchmark from the sidebar.")

st.divider()

# --- Leaderboard ---
st.subheader("Leaderboard (TTFT — lower is better)")
metric_choice = st.selectbox("Aggregate metric", ["p95", "p90", "median", "avg"], index=0, key="lb_metric")
try:
    lb = _get(base, "/leaderboard/", params={"metric": metric_choice, "limit": 50})
except requests.RequestException as e:
    st.error(f"GET /leaderboard/ failed: {e}")
    lb = {"ok": False, "rows": [], "note": str(e)}

if lb.get("note"):
    st.info(lb["note"])

rows = lb.get("rows") or []
if rows:
    df_lb = pd.DataFrame(rows)
    df_lb["label"] = df_lb["provider"] + " / " + df_lb["model"]
    chart_df = df_lb.set_index("label")[["score_ms"]].sort_values("score_ms", ascending=True)
    st.bar_chart(chart_df, horizontal=True)
    st.dataframe(
        df_lb[["provider", "model", "score_ms", "n_prompts"]].rename(
            columns={"score_ms": f"avg_{metric_choice}_ttft_ms"}
        ),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.caption("No leaderboard rows yet.")

st.divider()

# --- TTFT history across DB runs (per model) ---
st.subheader("TTFT over time (all saved runs)")
st.caption(
    "From Postgres: one point per **saved run** per model — same TTFT roll-up as the leaderboard (aggregate over prompts in that run)."
)
hc1, hc2, hc3 = st.columns(3)
with hc1:
    hist_metric = st.selectbox("History metric", ["p95", "p90", "median", "avg"], index=0, key="hist_metric")
with hc2:
    hist_limit = st.number_input(
        "Recent runs to load",
        min_value=1,
        max_value=500,
        value=80,
        step=10,
        key="hist_limit",
        help="Newest runs first; older points appear to the left after sorting by time.",
    )
with hc3:
    hist_prov = st.text_input("Filter provider (optional)", "", key="hist_prov", placeholder="openai")
hist_model = st.text_input("Filter model (optional)", "", key="hist_model", placeholder="gpt-4o-mini")

hist_params: dict[str, Any] = {"metric": hist_metric, "limit_runs": int(hist_limit)}
if hist_prov.strip():
    hist_params["provider"] = hist_prov.strip()
if hist_model.strip():
    hist_params["model"] = hist_model.strip()

try:
    hist_payload = _get(base, "/metrics/history", params=hist_params, timeout=60.0)
except requests.RequestException as e:
    hist_payload = {"ok": False, "series": []}
    st.warning(f"GET /metrics/history failed: {e}")

hist_series = hist_payload.get("series") or []
if hist_payload.get("ok") and hist_series:
    n_loaded = int(hist_payload.get("n_runs_loaded") or 0)
    st.caption(
        f"Loaded **{n_loaded}** most recent run(s) · displayed metric: **{hist_payload.get('metric', hist_metric)}**"
    )
    long_rows: list[dict[str, Any]] = []
    for ser in hist_series:
        label = f'{ser.get("provider", "")} / {ser.get("model", "")}'
        for p in ser.get("points") or []:
            long_rows.append(
                {
                    "finished_at": pd.to_datetime(p.get("finished_at")),
                    "model": label,
                    "score_ms": float(p.get("score_ms", 0)),
                    "run_id": p.get("run_id", ""),
                    "n_samples": int(p.get("n_samples") or 0),
                }
            )
    if long_rows:
        df_hist = pd.DataFrame(long_rows)
        wide_hist = (
            df_hist.pivot_table(
                index="finished_at",
                columns="model",
                values="score_ms",
                aggfunc="first",
            )
            .sort_index()
        )
        st.markdown(f"**TTFT ({hist_payload.get('metric', hist_metric)}) — lower is faster**")
        st.line_chart(wide_hist)
        with st.expander("History data (table)"):
            show_hist = df_hist.sort_values(["finished_at", "model"]).reset_index(drop=True)
            st.dataframe(show_hist, use_container_width=True, hide_index=True)
    else:
        st.caption("No TTFT points matched your filters.")
elif hist_payload.get("ok"):
    st.caption("No multi-run history yet — run the benchmark a few times after Postgres is filled.")

st.divider()

# --- Latest metrics charts ---
st.subheader("Latest run — latency by prompt")
try:
    m = _get(base, "/metrics/latest", params={"limit": 500})
except requests.RequestException as e:
    st.error(f"GET /metrics/latest failed: {e}")
    m = {"ok": False, "items": [], "note": str(e)}

if m.get("note") and not m.get("items"):
    st.info(m["note"])

items = m.get("items") or []
if items:
    st.caption(f"Run **{m.get('run_id', '')}** · finished `{m.get('finished_at', '')}`")

    records = []
    for it in items:
        prov = it.get("provider", "")
        model = it.get("model", "")
        pid = it.get("prompt_id", "")
        cat = it.get("prompt_category", "")
        ttft = it.get("ttft") or {}
        tot = it.get("total_latency") or {}
        records.append(
            {
                "provider": prov,
                "model": model,
                "prompt_id": pid,
                "category": cat,
                "label": f"{prov}:{model}",
                "ttft_p95_ms": ttft.get("p95_ms"),
                "ttft_median_ms": ttft.get("median_ms"),
                "total_p95_ms": tot.get("p95_ms"),
                "total_median_ms": tot.get("median_ms"),
            }
        )
    df = pd.DataFrame(records)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**TTFT (p95, ms)**")
        pivot_t = df.pivot_table(
            index="prompt_id",
            columns="label",
            values="ttft_p95_ms",
            aggfunc="first",
        )
        st.bar_chart(pivot_t)
    with c2:
        st.markdown("**Total latency (p95, ms)**")
        pivot_l = df.pivot_table(
            index="prompt_id",
            columns="label",
            values="total_p95_ms",
            aggfunc="first",
        )
        st.bar_chart(pivot_l)

    with st.expander("Full metrics table"):
        st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.caption("No metric rows to chart.")

st.divider()

# --- Raw samples (optional quick view) ---
st.subheader("Raw samples (latest run)")
raw_items = raw_payload.get("items") or []
if raw_items:
    df_raw = pd.DataFrame(raw_items)
    plot_cols = ["prompt_id", "provider", "model", "ttft_ms", "total_latency_ms", "success"]
    plot_cols = [c for c in plot_cols if c in df_raw.columns]
    st.markdown("**TTFT per call (ms)**")
    df_r = df_raw.copy()
    df_r["label"] = df_r["provider"].astype(str) + ":" + df_r["model"].astype(str)
    if "prompt_id" in df_r.columns and "ttft_ms" in df_r.columns:
        pvt = df_r.pivot_table(
            index="prompt_id",
            columns="label",
            values="ttft_ms",
            aggfunc="first",
        )
        st.bar_chart(pvt)
    st.dataframe(df_raw[plot_cols] if plot_cols else df_raw, use_container_width=True, hide_index=True)
else:
    st.caption("No raw samples.")
