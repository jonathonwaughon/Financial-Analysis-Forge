# File name: app.py
# Created: 12/21/2025 04:56 PM
# Purpose: Quart app with server-rendered Income Statement by period (no JS files required)
# Notes:
# - Upload -> parse immediately -> redirect to income statement page
# - Income statement page uses a normal form select to switch periods
# - Adds a Debug toggle to show a basic matplotlib plot + details table
# Used: Yes

from __future__ import annotations

import io
import os
from typing import Optional, List, Dict, Any

import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from quart import Quart, render_template, request, redirect, url_for, Response, send_from_directory

from main.app_state import (
    set_excel_path,
    get_excel_path,
    set_table,
    get_table,
    set_status,
    get_status,
    clear_all
)
from main.handlers.income_statement_table import parse_income_statement_tables_from_path


app = Quart(__name__, template_folder="templates", static_folder="static")


@app.get("/static/<path:filename>")
async def static_files(filename: str):
    return await send_from_directory(app.static_folder, filename)


def _periods_list() -> List[str]:
    periods_df = get_table("income_statement_periods")
    if periods_df.empty or "period" not in periods_df.columns:
        return []
    return [str(p).strip() for p in periods_df["period"].tolist() if str(p).strip()]


def _period_table(period: str) -> pd.DataFrame:
    raw_df = get_table("income_statement_raw")
    if raw_df.empty or "period" not in raw_df.columns:
        return pd.DataFrame(columns=["line_item", "value", "value_numeric"])

    view = raw_df[raw_df["period"] == period].copy()

    keep_cols = [c for c in ["line_item", "value", "value_numeric"] if c in view.columns]
    view = view[keep_cols]

    view = view.where(pd.notna(view), "")
    return view.reset_index(drop=True)


def _fmt_number(x: object) -> str:
    if x is None or x == "":
        return "—"
    try:
        v = float(x)
    except Exception:
        return str(x)

    abs_v = abs(v)
    if abs_v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.2f}B"
    if abs_v >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if abs_v >= 1_000:
        return f"{v / 1_000:.2f}K"
    return f"{v:,.0f}"


def _best_metric(statement_df: pd.DataFrame, needles: List[str]) -> Optional[float]:
    if statement_df is None or statement_df.empty:
        return None
    if "line_item" not in statement_df.columns:
        return None

    for _, row in statement_df.iterrows():
        li = str(row.get("line_item", "")).lower()
        if any(n in li for n in needles):
            vn = row.get("value_numeric", None)
            if vn is None or vn == "":
                return None
            try:
                return float(vn)
            except Exception:
                return None

    return None


def _compute_key_metrics(statement_df: pd.DataFrame) -> List[Dict[str, Any]]:
    defs = [
        ("Revenue", ["total revenue", "revenues", "revenue", "net sales", "sales"]),
        ("Gross Profit", ["gross profit"]),
        ("Operating Income", ["operating income", "operating profit", "ebit"]),
        ("Net Income", ["net income", "net earnings", "net profit"]),
    ]

    metrics: List[Dict[str, Any]] = []
    for name, needles in defs:
        val = _best_metric(statement_df, needles)
        metrics.append({
            "name": name,
            "value": val,
            "display": _fmt_number(val),
        })

    max_abs = 0.0
    for m in metrics:
        if m["value"] is not None:
            max_abs = max(max_abs, abs(float(m["value"])))

    for m in metrics:
        v = m["value"]
        if v is None or max_abs == 0:
            m["pct"] = 0
        else:
            m["pct"] = int(round((abs(float(v)) / max_abs) * 100))

    return metrics


@app.get("/")
async def index():
    return await render_template(
        "index.html",
        status=get_status(),
        excel_path=get_excel_path()
    )


@app.post("/upload")
async def upload_and_parse():
    """
    Upload + parse immediately (synchronous).
    This avoids timing issues and JS.
    """
    files = await request.files
    f = files.get("file")

    if f is None:
        set_status("No file provided.")
        return await render_template("index.html", status=get_status(), excel_path=get_excel_path())

    upload_dir = os.path.join(os.getcwd(), "storage", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    save_path = os.path.join(upload_dir, f.filename)
    await f.save(save_path)

    clear_all()
    set_excel_path(save_path)
    set_status(f"Uploaded: {f.filename} | Parsing...")

    try:
        parse_income_statement_tables_from_path(save_path, progress_cb=None)
        set_status(f"Uploaded: {f.filename} | Parse complete.")
    except Exception as e:
        set_status(f"Parse failed: {e}")

    return redirect(url_for("income_statement"))


@app.get("/income-statement")
async def income_statement():
    periods = _periods_list()

    period_idx_raw = request.args.get("period_idx", None)
    debug_raw = request.args.get("debug", "0")
    debug = str(debug_raw).strip() == "1"

    selected_idx = 0
    if period_idx_raw is not None:
        try:
            selected_idx = int(period_idx_raw)
        except Exception:
            selected_idx = 0

    if not periods:
        selected_period = ""
        table_df = pd.DataFrame(columns=["line_item", "value", "value_numeric"])
    else:
        if selected_idx < 0 or selected_idx >= len(periods):
            selected_idx = 0
        selected_period = periods[selected_idx]
        table_df = _period_table(selected_period)

    key_metrics = _compute_key_metrics(table_df)

    details_df = get_table("income_statement_details")
    if details_df is None or details_df.empty:
        details_cols: List[str] = []
        details_rows: List[Dict[str, Any]] = []
    else:
        safe = details_df.where(pd.notna(details_df), "")
        details_cols = [str(c) for c in safe.columns.tolist()]
        details_rows = safe.to_dict(orient="records")

    rows = table_df.to_dict(orient="records")
    columns = list(table_df.columns)

    return await render_template(
        "income_statement.html",
        status=get_status(),
        periods=periods,
        selected_idx=selected_idx,
        selected_period=selected_period,
        debug=debug,
        key_metrics=key_metrics,
        columns=columns,
        rows=rows,
        details_cols=details_cols,
        details_rows=details_rows,
    )


@app.get("/income-statement/plot.png")
async def income_statement_plot_png():
    periods = _periods_list()
    period_idx_raw = request.args.get("period_idx", None)

    selected_idx = 0
    if period_idx_raw is not None:
        try:
            selected_idx = int(period_idx_raw)
        except Exception:
            selected_idx = 0

    if not periods:
        return Response(b"", mimetype="image/png")

    if selected_idx < 0 or selected_idx >= len(periods):
        selected_idx = 0

    period = periods[selected_idx]
    df = _period_table(period)

    if df.empty or "value_numeric" not in df.columns or "line_item" not in df.columns:
        return Response(b"", mimetype="image/png")

    tmp = df.copy()
    tmp["value_numeric"] = pd.to_numeric(tmp["value_numeric"], errors="coerce")
    tmp = tmp.dropna(subset=["value_numeric"])
    if tmp.empty:
        return Response(b"", mimetype="image/png")

    tmp["abs"] = tmp["value_numeric"].abs()
    tmp = tmp.sort_values("abs", ascending=False).head(12)

    labels = tmp["line_item"].tolist()
    vals = tmp["value_numeric"].tolist()

    fig = plt.figure(figsize=(10, 5))
    ax = fig.add_subplot(111)
    ax.barh(labels[::-1], vals[::-1])
    ax.set_title(f"Income Statement (Top Items) — {period}")
    ax.tick_params(axis="y", labelsize=8)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140)
    plt.close(fig)
    buf.seek(0)

    return Response(buf.read(), mimetype="image/png")


if __name__ == "__main__":
    app.run()
