# File name: income_statement_table.py
# Created: 12/21/2025 04:35 PM
# Purpose: Parse Capital IQ Income Statement into long table + period list
# Notes:
# - Most recent period is the RIGHTMOST column
# - Extracts ALL periods into long rows: line_item | period | value | value_numeric
# Used: Yes

from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Any, Callable

import pandas as pd

from main.globals.app_state import set_table


def _norm(text: object) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    return " ".join(str(text).strip().lower().split())


def _clean_cell(value: object):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        s = value.strip()
        if s == "" or s == "-":
            return None
        return s
    return value


def _parse_numeric(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not (isinstance(value, float) and pd.isna(value)):
        return float(value)

    s = str(value).strip()
    if s == "":
        return None

    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]

    s = s.replace(",", "")
    try:
        num = float(s)
        return -num if neg else num
    except Exception:
        return None


def _find_income_statement_start(raw: pd.DataFrame) -> Optional[int]:
    for i in range(len(raw)):
        if _norm(raw.iat[i, 0]) == "income statement":
            return i

    for i in range(len(raw)):
        for j in range(min(raw.shape[1], 12)):
            if _norm(raw.iat[i, j]) == "income statement":
                return i

    return None


def _build_period_labels(raw: pd.DataFrame, start_row: int) -> List[Optional[str]]:
    labels: List[Optional[str]] = [None] * raw.shape[1]
    r1 = start_row + 1
    r2 = start_row + 2

    if r2 >= len(raw):
        return labels

    for c in range(1, raw.shape[1]):
        top = _clean_cell(raw.iat[r1, c]) if r1 < len(raw) else None
        bot = _clean_cell(raw.iat[r2, c]) if r2 < len(raw) else None

        if top and bot:
            labels[c] = f"{top} {bot}"
        else:
            labels[c] = str(top or bot) if (top or bot) else None

    return labels


def _extract_periods_and_colmap(period_labels: List[Optional[str]]) -> Tuple[List[str], Dict[int, str]]:
    """
    Capital IQ: most recent is RIGHTMOST column.
    Period display order is right-to-left column order.
    """
    col_to_period: Dict[int, str] = {}

    for c, lab in enumerate(period_labels):
        if c == 0:
            continue
        if lab is None:
            continue
        p = str(lab).strip()
        if not p:
            continue
        col_to_period[c] = p

    periods: List[str] = []
    seen = set()

    for c in sorted(col_to_period.keys(), reverse=True):
        p = col_to_period[c]
        if p not in seen:
            seen.add(p)
            periods.append(p)

    return periods, col_to_period


def parse_income_statement_tables_from_path(
    path: str,
    progress_cb: Optional[Callable[[str], None]] = None
) -> None:
    """
    Parses the workbook at path and stores:
    - income_statement_raw (long)
    - income_statement_details (key/value)
    - income_statement_periods (period column)

    progress_cb: optional callback for progress messages.
    """
    def push(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    push("Opening Excel...")
    xl = pd.ExcelFile(path)

    sheet_candidates = [s for s in xl.sheet_names if "income" in s.lower()]
    sheet_name = sheet_candidates[0] if sheet_candidates else xl.sheet_names[0]

    push(f"Reading sheet: {sheet_name}")
    raw = pd.read_excel(xl, sheet_name=sheet_name, header=None)

    push("Locating Income Statement header...")
    start_row = _find_income_statement_start(raw)
    if start_row is None:
        set_table("income_statement_raw", pd.DataFrame())
        set_table("income_statement_details", pd.DataFrame([{"key": "error", "value": f"Could not find 'Income Statement' in '{sheet_name}'"}]))
        set_table("income_statement_periods", pd.DataFrame())
        push("Failed: Income Statement header not found.")
        return

    period_labels = _build_period_labels(raw, start_row)
    periods, col_to_period = _extract_periods_and_colmap(period_labels)

    push(f"Detected periods: {len(periods)}")
    if periods:
        push(f"Most recent period: {periods[0]}")

    records: List[Dict[str, Any]] = []
    line_item_seen: set[str] = set()

    push("Extracting line items and values...")
    for r in range(start_row + 3, len(raw)):
        label = _clean_cell(raw.iat[r, 0])
        label_norm = _norm(label)

        if not label_norm:
            continue

        if label_norm in {"for the fiscal period ending", "currency"}:
            continue

        line_item = str(label).strip()
        if not line_item:
            continue

        line_item_seen.add(line_item)

        for c in range(1, raw.shape[1]):
            period = col_to_period.get(c)
            if not period:
                continue

            cell = _clean_cell(raw.iat[r, c])
            if cell is None:
                continue

            records.append({
                "line_item": line_item,
                "period": period,
                "value": cell,
                "value_numeric": _parse_numeric(cell),
                "col_index": c
            })

    raw_table = pd.DataFrame(
        records,
        columns=["line_item", "period", "value", "value_numeric", "col_index"]
    ).reset_index(drop=True)

    details_rows = [
        {"key": "sheet_name", "value": sheet_name},
        {"key": "periods", "value": ", ".join(periods)},
        {"key": "most_recent_period", "value": periods[0] if periods else ""},
        {"key": "period_count", "value": len(periods)},
        {"key": "line_item_count", "value": len(line_item_seen)},
        {"key": "data_points", "value": int(len(raw_table))}
    ]
    details_table = pd.DataFrame(details_rows, columns=["key", "value"])

    periods_table = pd.DataFrame({"period": periods})

    push("Saving tables into app_state...")
    set_table("income_statement_raw", raw_table)
    set_table("income_statement_details", details_table)
    set_table("income_statement_periods", periods_table)

    push("Income Statement parsing done.")
