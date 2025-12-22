# File name: app_state.py
# Created: 12/21/2025 04:34 PM
# Purpose: Global application state shared across modules (excel path, parsed tables, progress)
# Notes:
# - Stores DataFrames by name, current Excel path, and a websocket-friendly progress bus
# Used: Yes

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable

import pandas as pd


@dataclass
class AppState:
    lock: threading.Lock
    excel_path: Optional[str] = None
    tables: Dict[str, pd.DataFrame] = field(default_factory=dict)

    # UI / progress
    status: str = ""
    _progress_queues: List[asyncio.Queue] = field(default_factory=list)

    async def push_progress(self, message: str) -> None:
        """
        Async progress push (safe to call in the event loop).
        """
        with self.lock:
            queues = list(self._progress_queues)

        for q in queues:
            try:
                q.put_nowait(message)
            except Exception:
                pass

    def push_progress_sync(self, message: str) -> None:
        """
        Sync progress push for worker threads. Schedules into event loop.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.push_progress(message))
        except RuntimeError:
            # No running loop in this thread; we can't push.
            # This is okay in worst-case; status will still update.
            pass

    def subscribe_progress(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        with self.lock:
            self._progress_queues.append(q)
        return q


STATE = AppState(lock=threading.Lock())


def set_excel_path(path: Optional[str]) -> None:
    with STATE.lock:
        STATE.excel_path = path


def get_excel_path() -> Optional[str]:
    with STATE.lock:
        return STATE.excel_path


def set_status(s: str) -> None:
    with STATE.lock:
        STATE.status = s


def get_status() -> str:
    with STATE.lock:
        return STATE.status


def set_table(name: str, df: pd.DataFrame) -> None:
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()

    with STATE.lock:
        STATE.tables[name] = df.copy()


def get_table(name: str) -> pd.DataFrame:
    with STATE.lock:
        df = STATE.tables.get(name)

    if df is None:
        return pd.DataFrame()

    return df.copy()


def clear_all() -> None:
    with STATE.lock:
        STATE.tables.clear()
        STATE.excel_path = None
        STATE.status = ""
