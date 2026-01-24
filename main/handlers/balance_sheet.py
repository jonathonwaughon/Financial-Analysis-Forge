# File name: income_statement_table.py
# Created: 12/22/2025 08:xx PM
# Purpose: Parse Capital IQ Income Statement into nested dicts by period in GlobalState._data
# Notes:
# - Stores output at: State._data["income_statement"][<period>][<line_item>] = <value_numeric_or_raw>
# - Periods are derived from the 2 header rows under "Income Statement"
# - Most recent period is typically the RIGHTMOST column in Capital IQ
# Used: Yes

from __future__ import annotations

import os

import pandas as pd

from main.globals.global_state import State


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


def _parse_numeric(value: object):
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


def _find_income_statement_start(raw: pd.DataFrame) -> int | None:
    # Fast pass: first column
    for r in range(len(raw)):
        if _norm(raw.iat[r, 0]) == "income statement":
            return r

    # Wider pass: check first ~12 columns
    max_c = min(raw.shape[1], 12)
    for r in range(len(raw)):
        for c in range(max_c):
            if _norm(raw.iat[r, c]) == "income statement":
                return r

    return None


def _build_period_labels(raw: pd.DataFrame, start_row: int) -> list[str | None]:
    """
    Capital IQ typically has two header rows under the "Income Statement" header.
    We combine them into one string per column: "<top> <bottom>".
    """
    labels: list[str | None] = [None] * raw.shape[1]

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


def _extract_col_to_period(period_labels: list[str | None]) -> dict[int, str]:
    col_to_period: dict[int, str] = {}
    for c, lab in enumerate(period_labels):
        if c == 0:
            continue
        if lab is None:
            continue
        p = str(lab).strip()
        if not p:
            continue
        col_to_period[c] = p
    return col_to_period


def parse_income_statement_tables_from_path(path: str, progress_cb=None) -> None:
    """
    Reads the income statement sheet and saves the extracted values to:
        State._data["income_statement"][period][line_item] = value_numeric_or_raw

    If numeric parsing fails, we store the cleaned raw cell.
    """
    def push(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    push("Opening Excel...")
    xl = pd.ExcelFile(path)

    # Pick a sheet likely to be the income statement
    sheet_candidates = [s for s in xl.sheet_names if "income" in s.lower()]
    sheet_name = sheet_candidates[0] if sheet_candidates else xl.sheet_names[0]

    push(f"Reading sheet: {sheet_name}")
    raw = pd.read_excel(xl, sheet_name=sheet_name, header=None)

    push("Locating Income Statement header...")
    start_row = _find_income_statement_start(raw)
    if start_row is None:
        # Store an error payload in the same structure the UI expects
        State.insert_data("income_statement", {"_error": f"Could not find 'Income Statement' in '{sheet_name}'"})
        push("Failed: Income Statement header not found.")
        return

    push("Building period labels...")
    period_labels = _build_period_labels(raw, start_row)
    col_to_period = _extract_col_to_period(period_labels)

    # Create root dict
    income_statement: dict[str, dict[str, object]] = {}

    # Pre-create period dicts so order is stable-ish
    # (Most recent period is typically the rightmost column, but dict order isn’t used for logic.)
    for c in sorted(col_to_period.keys(), reverse=True):
        period = col_to_period[c]
        if period not in income_statement:
            income_statement[period] = {}

    push("Extracting line items and values...")
    for r in range(start_row + 3, len(raw)):
        label = _clean_cell(raw.iat[r, 0])
        label_norm = _norm(label)

        if not label_norm:
            continue

        # Skip common non-line-item header rows
        if label_norm in {"for the fiscal period ending", "currency"}:
            continue

        line_item = str(label).strip()
        if not line_item:
            continue

        for c, period in col_to_period.items():
            cell = _clean_cell(raw.iat[r, c])
            if cell is None:
                continue

            num = _parse_numeric(cell)
            value_to_store = num if num is not None else cell

            # Ensure period dict exists
            if period not in income_statement:
                income_statement[period] = {}

            income_statement[period][line_item] = value_to_store

    push("Saving income_statement into State._data...")
    State.insert_data("income_statement", income_statement)

    push("Income Statement parsing done.")
