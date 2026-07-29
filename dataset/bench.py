
#!/usr/bin/env python3
"""
test.py — Benchmark Runner
===========================
Reads prompts from dataset/dataset.csv, runs each through the LangGraph
CAD pipeline, and writes results to:

  dataset/benchmark.csv   — one row per prompt (compact)
  dataset/benchmark.log   — full per-attempt error trace

MLX note: Qwen2.5-Coder-7B-Instruct-4bit runs locally via mlx-lm on
Apple Silicon. The model is loaded once and kept in memory for the run.

Usage:
  python test.py                    # run all prompts
  python test.py --limit 10         # first N prompts
  python test.py --category Scale   # one category only
  python test.py --resume           # skip already-logged IDs
"""

import os
import sys
import csv
import json
import time
import argparse
import textwrap
from datetime import datetime

# ── Make project root importable ──────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from langgraph_pipeline import generate_cad_part_graph   # the full pipeline

# ── Paths ─────────────────────────────────────────────────────────────────────
DATASET_CSV   = os.path.join(HERE, "dataset", "dataset.csv")
BENCHMARK_CSV = os.path.join(HERE, "dataset", "benchmark.csv")
BENCHMARK_LOG = os.path.join(HERE, "dataset", "benchmark.log")

CSV_FIELDS = ["ID", "category", "prompt", "attempts",
              "execution_time", "success", "error_type", "final_error"]

# ── ANSI colours ──────────────────────────────────────────────────────────────
GRN  = "\033[92m"
RED  = "\033[91m"
YLW  = "\033[93m"
BLU  = "\033[94m"
CYN  = "\033[96m"
BOLD = "\033[1m"
DIM  = "\033[2m"
RST  = "\033[0m"

PASS_TAG = f"{GRN}{BOLD}✔ PASS{RST}"
FAIL_TAG = f"{RED}{BOLD}✗ FAIL{RST}"
LINE_W   = 72


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bar(label: str, char: str = "─") -> str:
    return f"{DIM}{char * LINE_W}{RST}  {label}"

def _wrap(text: str, indent: int = 6) -> str:
    prefix = " " * indent
    return textwrap.fill(text, width=LINE_W, initial_indent=prefix,
                         subsequent_indent=prefix)

def _load_dataset(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            prompt = r.get("prompt", "").strip()
            if prompt:
                rows.append({
                    "id":       r.get("id", "").strip(),
                    "category": r.get("category", "").strip(),
                    "difficulty": r.get("difficulty", "").strip(),
                    "prompt":   prompt,
                })
    return rows

def _already_done(path: str) -> set[str]:
    done = set()
    if not os.path.exists(path):
        return done
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            done.add(str(row.get("ID", "")).strip())
    return done

def _init_csv(path: str):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()

def _append_csv(path: str, row: dict):
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=CSV_FIELDS).writerow(row)

def _append_log(path: str, entry: str):
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

def _error_types(history: list) -> str:
    if not history:
        return ""
    types = list(dict.fromkeys(e.get("type", "Unknown") for e in history))
    return ", ".join(types)

def _format_history(history: list) -> str:
    if not history:
        return "    (none)"
    lines = []
    for e in history:
        attempt = e.get("attempt", "?")
        etype   = e.get("type", "Unknown")
        if etype == "PhysicsValidation":
            msg = e.get("details", {}).get("message", "Validation error")
        else:
            msg = e.get("message", "Unknown error")
        lines.append(f"    [Attempt {attempt}] ({etype})\n      {msg[:200]}")
    return "\n".join(lines)


# ── Live terminal display ─────────────────────────────────────────────────────

def _print_header(total: int, category_filter: str):
    os.system("clear")
    print(f"\n{BOLD}{CYN}{'CAD PIPELINE BENCHMARK':^{LINE_W}}{RST}")
    print(f"{DIM}{'─' * LINE_W}{RST}")
    print(f"  Dataset   : {DATASET_CSV}")
    print(f"  Prompts   : {total}")
    print(f"  Category  : {category_filter or 'ALL'}")
    print(f"  Model     : Qwen2.5-Coder-7B-Instruct-4bit (MLX / Apple Silicon)")
    print(f"  Output    : {BENCHMARK_CSV}")
    print(f"  Log       : {BENCHMARK_LOG}")
    print(f"  Started   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{DIM}{'─' * LINE_W}{RST}\n")

def _print_running(idx: int, total: int, row: dict):
    pct    = idx / total * 100
    filled = int(pct / 2)
    bar    = f"{GRN}{'█' * filled}{DIM}{'░' * (50 - filled)}{RST}"
    print(f"\r  [{bar}] {pct:5.1f}%  [{idx}/{total}]", end="", flush=True)
    print()
    print(f"  {BOLD}Running{RST}  [{BLU}{row['id']:>3}{RST}] "
          f"{YLW}{row['category']:<15}{RST} "
          f"{DIM}diff={row['difficulty']}{RST}")
    print(f"  {DIM}{_wrap(row['prompt'], 10)[:LINE_W + 10]}{RST}")

def _print_result(idx: int, total: int, row: dict, result: dict, elapsed: float):
    tag      = PASS_TAG if result["success"] else FAIL_TAG
    attempts = result["retries"]
    err_type = _error_types(result["history"])

    print(f"  {tag}  attempts={attempts}  time={elapsed:.1f}s")
    if not result["success"]:
        fe = (result.get("final_error") or "")[:120]
        print(f"  {RED}{DIM}{fe}{RST}")

def _print_summary(passed: int, failed: int, skipped: int, total: int,
                   total_time: float, cat_stats: dict):
    print(f"\n{DIM}{'═' * LINE_W}{RST}")
    print(f"{BOLD}{CYN}  BENCHMARK COMPLETE{RST}")
    print(f"{DIM}{'─' * LINE_W}{RST}")
    print(f"  Total   : {total}")
    print(f"  {GRN}Passed{RST}  : {passed}  ({passed/max(total,1)*100:.1f}%)")
    print(f"  {RED}Failed{RST}  : {failed}  ({failed/max(total,1)*100:.1f}%)")
    if skipped:
        print(f"  {DIM}Skipped{RST} : {skipped}  (already done, --resume)")
    print(f"  Time    : {total_time:.1f}s  (avg {total_time/max(passed+failed,1):.1f}s/prompt)")
    print(f"\n  {BOLD}Category breakdown:{RST}")
    for cat, stats in sorted(cat_stats.items()):
        p, f_ = stats["pass"], stats["fail"]
        tot   = p + f_
        pct   = p / tot * 100 if tot else 0
        bar   = f"{GRN}{'█' * int(pct/5)}{RED}{'█' * int((100-pct)/5)}{RST}"
        print(f"    {cat:<20} {bar}  {p}/{tot} ({pct:.0f}%)")
    print(f"{DIM}{'═' * LINE_W}{RST}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CAD Pipeline Benchmark Runner")
    parser.add_argument("--limit",    type=int, default=None, help="Only run first N prompts")
    parser.add_argument("--category", type=str, default=None, help="Filter to one category")
    parser.add_argument("--resume",   action="store_true",    help="Skip already-logged IDs")
    args = parser.parse_args()

    rows = _load_dataset(DATASET_CSV)

    if args.category:
        rows = [r for r in rows if r["category"].lower() == args.category.lower()]
    if args.limit:
        rows = rows[:args.limit]

    done_ids = _already_done(BENCHMARK_CSV) if args.resume else set()
    skipped  = len([r for r in rows if r["id"] in done_ids])
    rows     = [r for r in rows if r["id"] not in done_ids]

    _init_csv(BENCHMARK_CSV)
    _print_header(len(rows) + skipped, args.category)

    if not rows:
        print(f"  {YLW}Nothing to run — all prompts already benchmarked.{RST}")
        print(f"  Use without --resume to re-run everything.\n")
        return

    passed    = 0
    failed    = 0
    total_t   = 0.0
    cat_stats: dict[str, dict] = {}

    _append_log(BENCHMARK_LOG,
        f"\n{'='*72}\n"
        f"BENCHMARK RUN — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Category filter: {args.category or 'ALL'}  |  Prompts: {len(rows)}\n"
        f"{'='*72}"
    )

    for idx, row in enumerate(rows, 1):
        prompt_id = row["id"]
        category  = row["category"]
        prompt    = row["prompt"]

        cat_stats.setdefault(category, {"pass": 0, "fail": 0})

        _print_running(idx, len(rows), row)

        t_start = time.time()
        try:
            result = generate_cad_part_graph(
                user_prompt = prompt,
                prompt_id   = prompt_id,
            )
            elapsed = round(time.time() - t_start, 2)
        except Exception as e:
            elapsed = round(time.time() - t_start, 2)
            result  = {
                "success":        False,
                "retries":        0,
                "history":        [],
                "final_error":    f"CRASH: {e}",
                "syntax_errors":  0,
                "physics_errors": 0,
            }

        total_t += elapsed
        success   = result.get("success", False)
        attempts  = result.get("retries", 0)
        err_type  = _error_types(result.get("history", []))
        final_err = result.get("final_error") or ""

        if success:
            passed += 1
            cat_stats[category]["pass"] += 1
        else:
            failed += 1
            cat_stats[category]["fail"] += 1

        # ── CSV row ────────────────────────────────────────────────────────
        _append_csv(BENCHMARK_CSV, {
            "ID":             prompt_id,
            "category":       category,
            "prompt":         prompt,
            "attempts":       attempts,
            "execution_time": elapsed,
            "success":        "TRUE" if success else "FALSE",
            "error_type":     err_type,
            "final_error":    final_err,
        })

        # ── Log entry ──────────────────────────────────────────────────────
        status_str = "SUCCESS" if success else "FAILED"
        log_entry  = (
            f"\n{'─'*72}\n"
            f"[{idx}/{len(rows)}] ID={prompt_id}  Category={category}\n"
            f"Prompt   : {prompt}\n"
            f"Status   : {status_str}  |  Attempts: {attempts}  |  Time: {elapsed}s\n"
            f"ErrTypes : {err_type or 'None'}\n"
            f"History  :\n{_format_history(result.get('history', []))}\n"
        )
        if not success:
            log_entry += f"FinalErr : {final_err[:300]}\n"
        _append_log(BENCHMARK_LOG, log_entry)

        # ── Terminal result ────────────────────────────────────────────────
        _print_result(idx, len(rows), row, result, elapsed)
        print()   # blank line between prompts

    # ── Final summary ──────────────────────────────────────────────────────────
    _append_log(BENCHMARK_LOG,
        f"\n{'='*72}\n"
        f"SUMMARY  passed={passed}  failed={failed}  total_time={total_t:.1f}s\n"
        f"{'='*72}\n"
    )

    _print_summary(passed, failed, skipped, passed + failed, total_t, cat_stats)
    print(f"  {BOLD}benchmark.csv{RST} → {BENCHMARK_CSV}")
    print(f"  {BOLD}benchmark.log{RST} → {BENCHMARK_LOG}\n")


if __name__ == "__main__":
    main()