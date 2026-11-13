#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            x = json.loads(line)
            if isinstance(x, dict):
                out.append(x)
    return out


def _save_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _transform_row(row: dict[str, Any], puzzle: str, is_model: bool) -> dict[str, Any]:
    r = dict(row)
    anon_id = str(r.get("pool_case_id"))
    r["pool_case_id"] = anon_id
    r["id"] = anon_id
    r["idx"] = anon_id
    r["case_key"] = anon_id
    if "ref_case_key" in r:
        r["ref_case_key"] = anon_id
    return r


def _write_temp_transfer_samples(transfer_jsonl: Path, out_dir: Path) -> None:
    rows = _load_jsonl(transfer_jsonl)
    by_puzzle: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        pz = str(row.get("puzzle", "")).strip()
        if not pz:
            continue
        by_puzzle.setdefault(pz, []).append(row)
    for pz, items in by_puzzle.items():
        fp = out_dir / f"{pz}_samples.jsonl"
        _save_jsonl(fp, items)


def _run(cmd: list[str]) -> None:
    print("[cmd]", " ".join(cmd), flush=True)
    env = dict(**__import__("os").environ)
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("NUMEXPR_NUM_THREADS", "1")
    env.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    env.setdefault("BLIS_NUM_THREADS", "1")
    subprocess.run(cmd, check=True, cwd=str(ROOT), env=env)


def _flatten_from_eval(eval_out_dir: Path, target: str) -> Path:
    rows: list[dict[str, Any]] = []
    is_ref = target == "ref"
    metric_file = "ref_solver_case_metrics.jsonl" if is_ref else "model_code_case_metrics.jsonl"
    for fp in sorted(eval_out_dir.rglob(metric_file)):
        puzzle = fp.parent.name
        for row in _load_jsonl(fp):
            rows.append(_transform_row(row, puzzle, is_model=not is_ref))
    out_dir = ROOT / "results" / "transfer-level"
    out_path = out_dir / f"{target}.jsonl"
    _save_jsonl(out_path, rows)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Run transfer-level eval (real execution) for ref or one model.")
    ap.add_argument("target", help="'ref' or model name")
    ap.add_argument("--transfer-jsonl", type=Path, default=ROOT / "data" / "transfer.jsonl")
    ap.add_argument("--extracted-dir", type=Path, default=ROOT / "results" / "anchor-level")
    ap.add_argument("--timeout-sec", type=float, default=150.0)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--memory-limit-mb", type=float, default=1024.0)
    ap.add_argument("--case-limit", type=int, default=-1)
    ap.add_argument("--code-limit", type=int, default=-1)
    ap.add_argument("--code-idxs", default=None, help="Comma-separated code_idx whitelist for model mode")
    ap.add_argument("--code-idx-json", default=None, help="JSON mapping model->code_idx list for model mode")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="pcb_transfer_eval_") as troot, tempfile.TemporaryDirectory(prefix="pcb_transfer_data_") as td:
        tmp_root = Path(troot)
        data_dir = Path(td)
        _write_temp_transfer_samples(args.transfer_jsonl, data_dir)
        eval_out = tmp_root / args.target
        eval_out.mkdir(parents=True, exist_ok=True)

        if args.target == "ref":
            cmd = [
                sys.executable,
                str(ROOT / "eval" / "run_ref_solver_eval.py"),
                "--repo-root", str(ROOT),
                "--data-dir", str(data_dir),
                "--solver-dir", "solver",
                "--output-dir", str(eval_out),
                "--case-limit", str(args.case_limit),
                "--warmup", str(args.warmup),
                "--repeats", str(args.repeats),
                "--memory-limit-mb", str(args.memory_limit_mb),
                "--timeout-sec", str(args.timeout_sec),
                "--instruction-tool", "perf",
                "--profile-aggregation-rule", "trimmed_mean_drop_minmax",
                "--case-split", "transfer_pool",
                "--validation-mode", "pool_eval",
            ]
        else:
            cmd = [
                sys.executable,
                str(ROOT / "eval" / "run_model_code_eval.py"),
                "--repo-root", str(ROOT),
                "--data-dir", str(data_dir),
                "--extracted-dir", str(args.extracted_dir),
                "--output-dir", str(eval_out),
                "--model", args.target,
                "--code-limit", str(args.code_limit),
                "--case-limit", str(args.case_limit),
                "--timeout-sec", str(args.timeout_sec),
                "--warmup", str(args.warmup),
                "--repeats", str(args.repeats),
                "--memory-limit-mb", str(args.memory_limit_mb),
                "--instruction-tool", "perf",
                "--profile-aggregation-rule", "trimmed_mean_drop_minmax",
                "--case-split", "transfer_pool",
                "--validation-mode", "pool_eval",
            ]
            if args.code_idxs:
                cmd.extend(["--code-idxs", args.code_idxs])
            if args.code_idx_json:
                cmd.extend(["--code-idx-json", args.code_idx_json])

        _run(cmd)
        out = _flatten_from_eval(eval_out, args.target)
        print(f"[done] target={args.target} output={out}")


if __name__ == "__main__":
    main()
