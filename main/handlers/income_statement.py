# File name: income_statement.py
# Created: 12/21/2025 3:16 PM
# Purpose: Extract basic Income Statement metrics (Revenue, COGS, Gross Profit, etc.) from Capital IQ Excel
# Notes:
# - Reads the current Excel file path from app_state
# - Uses flexible row-label matching (Capital IQ is consistent but labels can vary slightly)
# Used: Yes


from __future__ import annotations

from typing import Dict, Optional, Tuple
import pandas as pd

from main.app_state import get_excel_path


ROW_ALIASES = {
    "revenue": ["Revenue", "Total Revenue", "Net Revenue", "Sales"],
    "cogs": ["Cost of Goods Sold", "COGS", "Cost of Revenue", "Cost of Sales"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income", "Operating Profit", "EBIT"],
    "ebitda": ["EBITDA"],
    "net_income": ["Net Income", "Net Income (GAAP)", "Net Profit"],
}


def _normalize(text: str) -> str:
    """
    Normalize text for reliable matching.
    """
    return " ".join(str(text).strip().lower().split())


def _find_matching_row(label_to_row: Dict[str, int], aliases: list[str]) -> Optional[int]:
    """
    Find the row index that best matches any alias.
    """
    for alias in aliases:
        key = _normalize(alias)
        if key in label_to_row:
            return label_to_row[key]

    for alias in aliases:
        key = _normalize(alias)
        for existing_label, idx in label_to_row.items():
            if key in existing_label or existing_label in key:
                return idx

    return None


def _parse_number(value):
    """
    Convert Excel cell values to floats.
    Handles commas, parentheses, blanks, and NaN.
    """
    if pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]

    text = text.replace(",", "")

    try:
        num = float(text)
        return -num if negative else num
    except Exception:
        return None


def _extract_latest_period_metrics(df: pd.DataFrame) -> Tuple[Dict[str, Optional[float]], str]:
    """
    Extract metrics for the latest (rightmost) period column.
    """
    label_to_row = {}
    for idx, label in enumerate(df.iloc[:, 0].astype(str)):
        norm = _normalize(label)
        if norm and norm not in label_to_row:
            label_to_row[norm] = idx

    period_columns = list(df.columns[1:])
    latest_column = next((c for c in reversed(period_columns) if str(c).strip()), period_columns[-1])

    results: Dict[str, Optional[float]] = {}

    for metric, aliases in ROW_ALIASES.items():
        row_idx = _find_matching_row(label_to_row, aliases)
        if row_idx is None:
            results[metric] = None
            continue

        raw_value = df.iloc[row_idx, df.columns.get_loc(latest_column)]
        results[metric] = _parse_number(raw_value)

    return results, str(latest_column)


def _extract_fiscal_period_label(raw_df: pd.DataFrame) -> Optional[str]:
    """
    Extract the fiscal period text from the top of the sheet.
    """
    for i in range(min(len(raw_df), 20)):
        for cell in raw_df.iloc[i]:
            if isinstance(cell, str):
                text = cell.strip()
                if "fiscal period" in text.lower() or "months ending" in text.lower():
                    return text
    return None


def extract_income_statement_metrics() -> Dict[str, str]:
    """
    Public API used by main.py.
    """
    path = get_excel_path()
    if not path:
        return {"error": "No Excel file loaded."}

    try:
        xl = pd.ExcelFile(path)
        sheet_candidates = [s for s in xl.sheet_names if "income" in s.lower()]
        sheet_name = sheet_candidates[0] if sheet_candidates else xl.sheet_names[0]

        raw = pd.read_excel(xl, sheet_name=sheet_name, header=None)

        header_row = next(
            (i for i in range(min(len(raw), 50)) if raw.iloc[i].notna().sum() >= 3),
            None,
        )

        if header_row is None:
            return {"error": "Could not detect header row."}

        df = pd.read_excel(xl, sheet_name=sheet_name, header=header_row)
        df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")

        fiscal_period = _extract_fiscal_period_label(raw)
        metrics, latest_column = _extract_latest_period_metrics(df)

        return {
            "sheet_used": sheet_name,
            "fiscal_period": fiscal_period or "Unknown",
            "latest_period_column": latest_column,
            "revenue": str(metrics.get("revenue")),
            "cogs": str(metrics.get("cogs")),
            "gross_profit": str(metrics.get("gross_profit")),
            "operating_income": str(metrics.get("operating_income")),
            "ebitda": str(metrics.get("ebitda")),
            "net_income": str(metrics.get("net_income")),
        }

    except Exception as e:
        return {"error": f"Failed to parse Income Statement: {e}"}