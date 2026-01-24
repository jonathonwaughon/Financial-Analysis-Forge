# File name: config.py
# Created: 12/21/2025 6:53 Pm
# Purpose: Shared config loader/saver for Financial Analysis Forge (config in repo root)
# Notes:
# - Human-editable JSON config
# - Safe defaults merged into file values
# - Thread-safe read/write (lock)
# Used: Yes

from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from typing import Any, Dict


_LOCK = threading.Lock()
_CONFIG_PATH = os.path.join(os.getcwd(), "config")


_DEFAULTS: Dict[str, Any] = {
	"app": {
		"port" : 5000,
		"debug_mode_default": False,
		"max_plot_ticks": 6,
		"uploads_dir": "storage/uploads"
	},
	"parsing": {
		"preferred_income_sheet_keywords": ["income", "statement", "is"],
		"period_order": "most_recent_first"
	},
	"display": {
		"show_value_numeric_column": True
	},
    "DO_NOT_MODIFY" : {
        "version" : "0.1.0",
        "QARS" : "SS49"
    }
}


def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
	"""
	Deep merge src into dst (mutates dst).
	- Dict values merge recursively
	- Non-dict values overwrite
	"""
	for k, v in src.items():
		if isinstance(v, dict) and isinstance(dst.get(k), dict):
			_deep_merge(dst[k], v)
		else:
			dst[k] = v
	return dst


def _ensure_file_exists() -> None:
	if os.path.exists(_CONFIG_PATH):
		return

	with _LOCK:
		if os.path.exists(_CONFIG_PATH):
			return
		with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
			json.dump(_DEFAULTS, f, indent=2)


def read_config() -> Dict[str, Any]:
	"""
	Read config.json and merge defaults. Always returns a full config dict.
	"""
	_ensure_file_exists()

	with _LOCK:
		try:
			with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
				data = json.load(f)
		except Exception:
			data = {}

	merged = deepcopy(_DEFAULTS)
	if isinstance(data, dict):
		_deep_merge(merged, data)

	return merged


def write_config(new_config: Dict[str, Any]) -> Dict[str, Any]:
	"""
	Write config.json. Also returns the merged final config (defaults + new_config).
	"""
	if not isinstance(new_config, dict):
		new_config = {}

	final_cfg = deepcopy(_DEFAULTS)
	_deep_merge(final_cfg, new_config)

	with _LOCK:
		with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
			json.dump(final_cfg, f, indent=2)

	return final_cfg


def update_config(path: str, value: Any) -> Dict[str, Any]:
	"""
	Update a single config key by dotted path, e.g.:
		update_config("app.max_plot_ticks", 5)
	"""
	cfg = read_config()

	parts = [p for p in path.split(".") if p.strip()]
	if not parts:
		return cfg

	cur = cfg
	for p in parts[:-1]:
		if p not in cur or not isinstance(cur[p], dict):
			cur[p] = {}
		cur = cur[p]

	cur[parts[-1]] = value
	return write_config(cfg)


def get_config(path: str) -> Any:
    """
    Get a single config key by dotted path, e.g.:
        get_config("app.max_plot_ticks")
    """
    cfg = read_config()

    parts = [p for p in path.split(".") if p.strip()]
    if not parts:
        return None

    cur = cfg
    for p in parts:
        if p not in cur:
            return None
        cur = cur[p]

    return cur
