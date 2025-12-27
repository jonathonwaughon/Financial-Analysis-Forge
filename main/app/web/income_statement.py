from __future__ import annotations

import io
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from quart import Blueprint, render_template, request, Response, redirect, url_for

from main.globals.global_state import State


bp = Blueprint("income_statement", __name__)


def _status() -> str:
    s = State.find("status", default="")
    return str(s) if s is not None else ""


def _income_statement_root() -> Dict[str, Dict[str, Any]]:
    root = State.find("income_statement", default={})
    if isinstance(root, dict):
        return root
    return {}


def _periods_list() -> List[str]:
    """
    Returns periods in display order (most recent first) if possible.
    Since Capital IQ is usually rightmost = most recent, your parser likely inserted
    periods in that right-to-left order. Dicts preserve insertion order in Python 3.7+,
    so we keep the dict key order.
    """
    root = _income_statement_root()
    periods = [str(p) for p in root.keys() if str(p).strip()]
    return periods


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


def _coerce_numeric(x: object) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except Exception:
        return None


def _period_table(period: str) -> pd.DataFrame:
    """
    Builds a table for one period:
        line_item | value | value_numeric
    Your income_statement dict stores value as numeric when possible, raw otherwise.
    We set both value and value_numeric based on that.
    """
    root = _income_statement_root()
    period_dict = root.get(period, None)

    if not isinstance(period_dict, dict) or not period_dict:
        return pd.DataFrame(columns=["line_item", "value", "value_numeric"])

    rows: List[Dict[str, Any]] = []
    for line_item, val in period_dict.items():
        vn = _coerce_numeric(val)
        rows.append({
            "line_item": str(line_item),
            "value": val if val is not None else "",
            "value_numeric": vn,
        })

    df = pd.DataFrame(rows, columns=["line_item", "value", "value_numeric"])
    df = df.where(pd.notna(df), "")
    return df.reset_index(drop=True)


def _raw_income_long() -> pd.DataFrame:
    """
    Builds a long-form table from nested dicts:
        line_item | period | value | value_numeric
    """
    root = _income_statement_root()
    if not root:
        return pd.DataFrame(columns=["line_item", "period", "value", "value_numeric"])

    records: List[Dict[str, Any]] = []
    for period, period_dict in root.items():
        if not isinstance(period_dict, dict):
            continue
        for line_item, val in period_dict.items():
            vn = _coerce_numeric(val)
            records.append({
                "line_item": str(line_item),
                "period": str(period),
                "value": val if val is not None else "",
                "value_numeric": vn,
            })

    df = pd.DataFrame(records, columns=["line_item", "period", "value", "value_numeric"])
    df = df.where(pd.notna(df), "")
    return df.reset_index(drop=True)


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


def _resolve_line_item(raw_df: pd.DataFrame, line_item: str) -> Optional[str]:
    """
    Try to match a line_item from the URL to an actual row label.
    First tries exact match, then case-insensitive match.
    """
    if raw_df.empty or "line_item" not in raw_df.columns:
        return None

    candidates = raw_df["line_item"].dropna().astype(str).tolist()

    if line_item in candidates:
        return line_item

    li_lower = line_item.lower().strip()
    for c in candidates:
        if str(c).lower().strip() == li_lower:
            return str(c)

    return None


def _series_for_line_item(raw_df: pd.DataFrame, periods: List[str], line_item: str) -> pd.DataFrame:
    """
    Build series dataframe:
        period | value_numeric | value_display
    periods are expected in display order (most recent first).
    """
    if raw_df.empty:
        return pd.DataFrame(columns=["period", "value_numeric", "value_display"])

    if not {"period", "line_item"}.issubset(set(raw_df.columns)):
        return pd.DataFrame(columns=["period", "value_numeric", "value_display"])

    df = raw_df.copy()
    df["line_item"] = df["line_item"].astype(str)
    df["period"] = df["period"].astype(str)

    view = df[df["line_item"] == line_item].copy()
    if view.empty:
        return pd.DataFrame(columns=["period", "value_numeric", "value_display"])

    view["value_numeric"] = pd.to_numeric(view.get("value_numeric", None), errors="coerce")

    rows: List[Dict[str, Any]] = []
    for p in periods:
        sub = view[view["period"] == p]
        if sub.empty:
            rows.append({"period": p, "value_numeric": None, "value_display": "—"})
            continue

        vn = None
        for x in sub["value_numeric"].tolist():
            if pd.notna(x):
                vn = float(x)
                break

        rows.append({"period": p, "value_numeric": vn, "value_display": _fmt_number(vn)})

    out = pd.DataFrame(rows, columns=["period", "value_numeric", "value_display"])
    return out


@bp.get("/income-statement")
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

    # You no longer have income_statement_details in the new system (unless you add it)
    details_cols: List[str] = []
    details_rows: List[Dict[str, Any]] = []

    rows = table_df.to_dict(orient="records")
    columns = list(table_df.columns)

    return await render_template(
        "income_statement.html",
        status=_status(),
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


@bp.get("/income_statement")
async def income_statement_alias():
    return redirect(url_for("income_statement.income_statement"))


@bp.get("/income_statement/<path:line_item>")
async def income_statement_line_item(line_item: str):
    raw_df = _raw_income_long()
    periods = _periods_list()

    resolved = _resolve_line_item(raw_df, line_item)
    if resolved is None:
        return await render_template(
            "income_statement_item.html",
            status=_status(),
            line_item=line_item,
            resolved_line_item=None,
            periods=periods,
            latest_display="—",
            avg_display="—",
            series_rows=[],
        )

    series_df = _series_for_line_item(raw_df, periods, resolved)

    latest_val = None
    for x in series_df["value_numeric"].tolist():
        if x is not None and pd.notna(x):
            latest_val = float(x)
            break

    nums = [float(x) for x in series_df["value_numeric"].tolist() if x is not None and pd.notna(x)]
    avg_val = (sum(nums) / len(nums)) if nums else None

    latest_display = _fmt_number(latest_val)
    avg_display = _fmt_number(avg_val)

    series_rows = series_df.where(pd.notna(series_df), "").to_dict(orient="records")

    return await render_template(
        "income_statement_item.html",
        status=_status(),
        line_item=line_item,
        resolved_line_item=resolved,
        periods=periods,
        latest_display=latest_display,
        avg_display=avg_display,
        series_rows=series_rows,
    )


@bp.get("/income_statement/<path:line_item>/plot.png")
async def income_statement_line_item_plot(line_item: str):
    raw_df = _raw_income_long()
    periods = _periods_list()

    resolved = _resolve_line_item(raw_df, line_item)
    if resolved is None:
        return Response(b"", mimetype="image/png")

    series_df = _series_for_line_item(raw_df, periods, resolved)
    if series_df.empty:
        return Response(b"", mimetype="image/png")

    plot_df = series_df.copy()
    plot_df["value_numeric"] = pd.to_numeric(plot_df["value_numeric"], errors="coerce")
    plot_df = plot_df.iloc[::-1].reset_index(drop=True)  # oldest -> newest

    x = plot_df["period"].tolist()
    y = plot_df["value_numeric"].tolist()

    max_ticks = 6
    xs = list(range(len(x)))

    fig = plt.figure(figsize=(10, 4.5))
    ax = fig.add_subplot(111)
    ax.plot(xs, y, marker="o")

    n = len(xs)
    if n <= max_ticks:
        tick_pos = xs
        tick_labels = x
    else:
        step = (n - 1) / (max_ticks - 1)
        tick_pos = [int(round(i * step)) for i in range(max_ticks)]
        tick_labels = [x[i] for i in tick_pos]

    ax.set_xticks(tick_pos)
    ax.set_xticklabels(tick_labels, rotation=35, fontsize=8)

    ax.set_title(f"{resolved} over time")
    ax.set_xlabel("Period")
    ax.set_ylabel("Value (numeric)")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)

    return Response(buf.read(), mimetype="image/png")


@bp.get("/income-statement/plot.png")
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
