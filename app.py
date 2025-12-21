# File name: app.py
# Created: 12/21/2025 04:56 PM
# Purpose: Quart app with server-rendered Income Statement by period (no JS)
# Notes:
# - Upload -> parse immediately -> redirect to income statement page
# - Income statement page uses a normal form select to switch periods
# Used: Yes

from __future__ import annotations

import os
from typing import Optional, List

import pandas as pd
from quart import Quart, render_template, request, redirect, url_for

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

    # keep original order as extracted; or sort if you want
    # view = view.sort_values(["line_item"], ascending=True)

    view = view.where(pd.notna(view), "")
    return view.reset_index(drop=True)


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
        # Parse immediately (no background, no websocket, no JS)
        parse_income_statement_tables_from_path(save_path, progress_cb=None)
        set_status(f"Uploaded: {f.filename} | Parse complete.")
    except Exception as e:
        set_status(f"Parse failed: {e}")

    return redirect(url_for("income_statement"))


@app.get("/income-statement")
async def income_statement():
    periods = _periods_list()

    # Read selected index instead of the period string
    period_idx_raw = request.args.get("period_idx", None)

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
        # Clamp to valid bounds
        if selected_idx < 0:
            selected_idx = 0
        if selected_idx >= len(periods):
            selected_idx = 0

        selected_period = periods[selected_idx]
        table_df = _period_table(selected_period)

    rows = table_df.to_dict(orient="records")
    columns = list(table_df.columns)

    return await render_template(
        "income_statement.html",
        status=get_status(),
        periods=periods,
        selected_idx=selected_idx,
        selected_period=selected_period,
        columns=columns,
        rows=rows
    )



if __name__ == "__main__":
    app.run()
