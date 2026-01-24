# File name: app_state.py
# Created: 12/21/2025 04:34 PM
# Purpose: Global application state shared across modules (excel path, parsed tables, progress)
# Notes:
# - Global registry for extracted tables + misc app data
# - Supports shallow lookup + optional deep recursive lookup
# Used: Yes

from __future__ import annotations


class GlobalState:
    def __init__(self):
        self.excel_path = None
        self._data = {}

    # Inserts a piece of data into the data dictionary
    def insert_data(self, index: str, data) -> None:
        self._data[index] = data

    def _split_path(self, path: str) -> list[str]:
        """
        Splits a dot-path like:
            "income_statement.2025 FY.Revenue"

        Supports escaping dots in key names:
            "some_key_with_dot\\.inside.child"
        """
        if not isinstance(path, str) or not path:
            return []

        parts = []
        buf = []
        escaped = False

        for ch in path:
            if escaped:
                buf.append(ch)
                escaped = False
                continue

            if ch == "\\":
                escaped = True
                continue

            if ch == ".":
                parts.append("".join(buf))
                buf = []
                continue

            buf.append(ch)

        parts.append("".join(buf))
        return [p for p in parts if p != ""]

    def _resolve_parent(self, path: str):
        """
        Returns (parent_dict, final_key) for a path.
        If it can't resolve, returns (None, None).
        """
        keys = self._split_path(path)

        if not keys:
            return None, None

        if len(keys) == 1:
            return self._data, keys[0]

        cur = self._data
        for k in keys[:-1]:
            if not isinstance(cur, dict):
                return None, None
            if k not in cur:
                return None, None
            cur = cur[k]

        if not isinstance(cur, dict):
            return None, None

        return cur, keys[-1]

    def find(self, path: str, default=None):
        parent, final_key = self._resolve_parent(path)
        if parent is None:
            return default
        return parent.get(final_key, default)

    def update(self, path: str, value) -> bool:
        """
        Updates a value at a dot-path. Returns True if updated, False otherwise.
        """
        parent, final_key = self._resolve_parent(path)
        if parent is None:
            return False
        if final_key not in parent:
            return False
        parent[final_key] = value
        return True

    def find_all(self, key: str) -> list[tuple[str, object]]:
        """
        Finds ALL occurrences of a key anywhere in _data.
        Returns a list of (path, value).
        """
        results = []
        self._find_all_recursive(self._data, key, prefix="", out=results)
        return results

    def _find_all_recursive(self, data, key: str, prefix: str, out: list):
        if not isinstance(data, dict):
            return

        for k, v in data.items():
            path = f"{prefix}.{k}" if prefix else str(k)

            if k == key:
                out.append((path, v))

            if isinstance(v, dict):
                self._find_all_recursive(v, key, path, out)

    def update_all(self, key: str, value) -> int:
        """
        Updates ALL occurrences of a key anywhere in _data.
        Returns the number of updates performed.
        """
        return self._update_all_recursive(self._data, key, value)

    def _update_all_recursive(self, data, key: str, value) -> int:
        if not isinstance(data, dict):
            return 0

        count = 0
        for k, v in data.items():
            if k == key:
                data[k] = value
                count += 1

            if isinstance(v, dict):
                count += self._update_all_recursive(v, key, value)

        return count

    # Basic attribute access
    def set(self, key: str, value) -> None:
        setattr(self, key, value)

    def get(self, key: str):
        return getattr(self, key)



