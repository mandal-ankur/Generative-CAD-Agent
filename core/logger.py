"""
core/logger.py
==============
Logs experiment results from the LangGraph pipeline to:
  <project>/dataset/benchmark.csv
  <project>/dataset/benchmark.log

All paths are __file__-relative — works on any device.
"""

import csv
import json
import os
from datetime import datetime

_PROJECT  = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DATASET  = os.path.join(_PROJECT, "dataset")
_CSV_PATH = os.path.join(_DATASET, "benchmark.csv")
_LOG_PATH = os.path.join(_DATASET, "benchmark.log")

_CSV_FIELDS = [
    "timestamp", "ID", "category", "prompt",
    "attempts", "syntax_errors", "physics_errors",
    "execution_time", "success", "error_type", "final_error",
]


def _ensure_csv():
    os.makedirs(_DATASET, exist_ok=True)
    if not os.path.exists(_CSV_PATH):
        with open(_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=_CSV_FIELDS).writeheader()


def _error_types(history: list) -> str:
    if not history:
        return ""
    return ", ".join(dict.fromkeys(e.get("type", "Unknown") for e in history))


def log_experiment(
    prompt_id:          str,
    prompt:             str,
    attempts:           int,
    execution_time:     float,
    success:            bool,
    category:           str  = "",
    syntax_errors:      int  = 0,
    physics_errors:     int  = 0,
    error_history:      list = None,
    final_error:        str  = None,
):
    """Append one experiment result to benchmark.csv and benchmark.log."""
    error_history = error_history or []
    _ensure_csv()

    row = {
        "timestamp":      datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "ID":             str(prompt_id),
        "category":       category,
        "prompt":         prompt,
        "attempts":       attempts,
        "syntax_errors":  syntax_errors,
        "physics_errors": physics_errors,
        "execution_time": round(float(execution_time), 2),
        "success":        "TRUE" if success else "FALSE",
        "error_type":     _error_types(error_history),
        "final_error":    "" if success else (final_error or "").strip(),
    }

    with open(_CSV_PATH, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=_CSV_FIELDS).writerow(row)

    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n[{row['timestamp']}] ID={prompt_id} | {category} | "
                f"{'PASS' if success else 'FAIL'} | "
                f"attempts={attempts} | time={row['execution_time']}s\n")
        f.write(f"  Prompt: {prompt}\n")
        for e in error_history:
            f.write(f"  [Attempt {e.get('attempt','?')}] ({e.get('type','?')}): "
                    f"{e.get('message', e.get('details', ''))}\n")
        if not success and final_error:
            f.write(f"  FinalErr: {final_error[:300]}\n")


def log_from_state(state: dict, prompt_id: str, execution_time: float,
                   category: str = ""):
    """Convenience wrapper — pass the final LangGraph CADState dict directly."""
    log_experiment(
        prompt_id      = prompt_id,
        prompt         = state.get("user_prompt", ""),
        attempts       = state.get("attempt", 0),
        execution_time = execution_time,
        success        = state.get("success", False),
        category       = category,
        syntax_errors  = state.get("syntax_errors", 0),
        physics_errors = state.get("physics_errors", 0),
        error_history  = state.get("error_history", []),
        final_error    = state.get("final_error"),
    )
