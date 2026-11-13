#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import psutil  # type: ignore
except Exception:  # noqa: BLE001
    psutil = None


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"Invalid JSONL row at {path}:{lineno}")
            rows.append(obj)
    return rows


def _iter_data_files(data_dir: Path, only_puzzle: Optional[str]) -> List[Tuple[str, Path]]:
    out: List[Tuple[str, Path]] = []
    for p in sorted(data_dir.glob("*_samples.jsonl")):
        puzzle = p.name[: -len("_samples.jsonl")]
        if only_puzzle is not None and puzzle != only_puzzle:
            continue
        out.append((puzzle, p))
    return out


def _load_skip_item_indexes_json(path: Path) -> Dict[str, set[int]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(obj, dict) and isinstance(obj.get("SKIP_ITEM_INDEXES"), dict):
        obj = obj.get("SKIP_ITEM_INDEXES")
    if not isinstance(obj, dict):
        return {}

    out: Dict[str, set[int]] = {}
    for puzzle, indexes in obj.items():
        if not isinstance(puzzle, str):
            continue
        vals: set[int] = set()
        if isinstance(indexes, list):
            it = indexes
        elif isinstance(indexes, set):
            it = list(indexes)
        else:
            continue
        for x in it:
            if isinstance(x, bool):
                continue
            if isinstance(x, (int, float)):
                iv = int(x)
                if iv > 0:
                    vals.add(iv)
            elif isinstance(x, str) and x.strip().isdigit():
                iv = int(x.strip())
                if iv > 0:
                    vals.add(iv)
        if vals:
            out[puzzle] = vals
    return out


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stderr_excerpt(stderr_bytes: bytes, n_chars: int) -> str:
    text = stderr_bytes.decode("utf-8", errors="replace")
    if len(text) <= n_chars:
        return text
    return text[-n_chars:]


def _run_cmd_text(cmd: List[str], cwd: Path, timeout_sec: float = 20.0) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout_sec)
        return int(p.returncode), p.stdout, p.stderr
    except Exception as exc:  # noqa: BLE001
        return 1, "", str(exc)


def _git_version(repo_root: Path) -> Dict[str, Any]:
    rc, out, _ = _run_cmd_text(["git", "rev-parse", "HEAD"], cwd=repo_root)
    commit = out.strip() if rc == 0 else None
    rc2, out2, _ = _run_cmd_text(["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo_root)
    dirty = bool(out2.strip()) if rc2 == 0 else None
    return {
        "git_commit": commit,
        "git_dirty": dirty,
    }


def _pip_freeze_hash(repo_root: Path) -> Optional[str]:
    rc, out, _ = _run_cmd_text([sys.executable, "-m", "pip", "freeze"], cwd=repo_root, timeout_sec=40.0)
    if rc != 0:
        return None
    lines = [x.strip() for x in out.splitlines() if x.strip()]
    lines.sort()
    return _sha256_hex("\n".join(lines).encode("utf-8"))


def _runtime_env_version(repo_root: Path) -> Dict[str, Any]:
    return {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "pip_freeze_sha256": _pip_freeze_hash(repo_root),
    }


def _to_number(x: Any) -> Optional[float]:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    return None


def _infer_pool_case_group(item: Dict[str, Any]) -> str:
    row = item.get("row")
    col = item.get("column")
    level = item.get("level", "unknown")
    if isinstance(row, (int, float)) and isinstance(col, (int, float)):
        rr = int(row) if float(row).is_integer() else row
        cc = int(col) if float(col).is_integer() else col
        return f"{rr}x{cc}_{level}"
    return str(item.get("group", level))


def _infer_input_size_proxy(item: Dict[str, Any]) -> Optional[float]:
    row = _to_number(item.get("row"))
    col = _to_number(item.get("column"))
    if row is not None and col is not None:
        return float(row * col)

    obs = item.get("observation")
    if isinstance(obs, dict):
        grid = obs.get("data") or obs.get("region")
        if isinstance(grid, list) and grid and isinstance(grid[0], list):
            return float(len(grid) * len(grid[0]))
    return None


def _trimmed_mean_drop_minmax(values: List[float]) -> Optional[float]:
    if not values:
        return None
    vals = sorted(values)
    if len(vals) >= 3:
        vals = vals[1:-1]
    return float(sum(vals) / len(vals))


def _aggregate(values: List[Optional[float]], rule: str) -> Optional[float]:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return None
    if rule == "trimmed_mean_drop_minmax":
        return _trimmed_mean_drop_minmax(vals)
    if rule == "median":
        return float(statistics.median(vals))
    return float(sum(vals) / len(vals))


def _kill_proc_tree(pid: int) -> None:
    if psutil is None:
        return
    try:
        proc = psutil.Process(pid)
    except Exception:
        return
    children = proc.children(recursive=True)
    for c in children:
        try:
            c.kill()
        except Exception:
            pass
    try:
        proc.kill()
    except Exception:
        pass


def _detect_perf_available(repo_root: Path) -> Tuple[bool, str]:
    try:
        p = subprocess.run(
            ["perf", "stat", "-x,", "-e", "instructions,cycles", "--", "sleep", "0.01"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if p.returncode == 0:
            return True, "ok"
        msg = (p.stderr or p.stdout or "").strip()
        return False, msg[:500]
    except FileNotFoundError:
        return False, "perf_not_found"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _run_one_repeat(
    *,
    repo_root: Path,
    runner_script: Path,
    puzzle: str,
    item: Dict[str, Any],
    repeat_idx: int,
    timeout_sec: float,
    sample_interval_sec: float,
    stderr_excerpt_chars: int,
    perf_enabled: bool,
    memory_limit_mb: float,
) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ref_eval_case_") as td:
        tmpdir = Path(td)
        case_json = tmpdir / "case.json"
        out_json = tmpdir / "result.json"
        stdout_file = tmpdir / "stdout.bin"
        stderr_file = tmpdir / "stderr.bin"

        payload = {
            "observation": item.get("observation"),
            "expected_answer": item.get("answer"),
        }
        case_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        cmd_base = [
            sys.executable,
            str(runner_script),
            "--repo-root",
            str(repo_root),
            "--puzzle",
            puzzle,
            "--case-json",
            str(case_json),
            "--out-json",
            str(out_json),
        ]
        cmd = cmd_base[:]
        if perf_enabled:
            cmd.append("--measure-instructions")
        if memory_limit_mb > 0:
            cmd.extend(["--memory-limit-mb", str(memory_limit_mb)])

        with stdout_file.open("wb") as fout, stderr_file.open("wb") as ferr:
            proc = subprocess.Popen(cmd, cwd=str(repo_root), stdout=fout, stderr=ferr)

            t0 = time.perf_counter()
            samples: List[Tuple[float, int]] = []
            timed_out = False
            last_t = 0.0

            while True:
                now = time.perf_counter() - t0
                last_t = now

                rss_bytes = 0
                if psutil is not None:
                    try:
                        ps = psutil.Process(proc.pid)
                        rss_bytes += int(ps.memory_info().rss)
                        for c in ps.children(recursive=True):
                            try:
                                rss_bytes += int(c.memory_info().rss)
                            except Exception:
                                pass
                    except Exception:
                        pass
                samples.append((now, rss_bytes))

                if proc.poll() is not None:
                    break
                if timeout_sec > 0 and now > timeout_sec:
                    timed_out = True
                    _kill_proc_tree(proc.pid)
                    try:
                        proc.wait(timeout=1)
                    except Exception:
                        pass
                    break
                time.sleep(sample_interval_sec)

            try:
                proc.wait(timeout=1)
            except Exception:
                pass

        return_code = int(proc.returncode) if proc.returncode is not None else 124
        if timed_out:
            return_code = 124

        stdout_bytes_raw = stdout_file.read_bytes() if stdout_file.exists() else b""
        stderr_bytes_raw = stderr_file.read_bytes() if stderr_file.exists() else b""

        child = {}
        if out_json.exists():
            try:
                child = json.loads(out_json.read_text(encoding="utf-8"))
            except Exception:
                child = {}

        peak_rss = max((rss for _, rss in samples), default=0)
        mem_integral_byte_s = 0.0
        for i in range(1, len(samples)):
            dt = samples[i][0] - samples[i - 1][0]
            mem_integral_byte_s += dt * samples[i - 1][1]

        solve_instr = child.get("solve_instruction_count")
        solve_cycles = child.get("solve_cycles")
        instruction_count = int(solve_instr) if isinstance(solve_instr, (int, float)) else None
        cycles = int(solve_cycles) if isinstance(solve_cycles, (int, float)) else None

        crashed = (not timed_out) and (return_code != 0)
        child_exec_success = bool(child.get("exec_success"))
        exec_success = (not timed_out) and (not crashed) and child_exec_success
        correct = bool(child.get("correct")) if exec_success else False
        output_match = bool(child.get("output_match")) if exec_success else False

        if timed_out:
            judge_status = "timeout"
            error_type = "timeout"
        elif str(child.get("error_type") or "") == "memory_limit":
            judge_status = "runtime_error"
            error_type = "memory_limit"
        elif crashed:
            judge_status = "runtime_error"
            error_type = "runtime_error"
        elif exec_success and correct:
            judge_status = "accepted"
            error_type = None
        elif exec_success:
            judge_status = "wrong_answer"
            error_type = "wrong_answer"
        else:
            judge_status = str(child.get("judge_status") or "runtime_error")
            error_type = str(child.get("error_type") or "runtime_error")

        child_ru_maxrss_kb = child.get("ru_maxrss_kb")
        if peak_rss <= 0 and isinstance(child_ru_maxrss_kb, (int, float)):
            peak_rss = int(float(child_ru_maxrss_kb) * 1024.0)

        # Preferred fairness path: use solve-only metrics reported by child runner.
        solve_wall_time_ms = child.get("solve_wall_time_ms")
        solve_cpu_time_ms = child.get("solve_cpu_time_ms")
        solve_peak_rss_bytes = child.get("solve_peak_rss_bytes")
        solve_mem_integral_byte_s = child.get("solve_memory_integral_byte_seconds")

        wall_time_ms = (
            float(solve_wall_time_ms)
            if isinstance(solve_wall_time_ms, (int, float))
            else round(last_t * 1000.0, 6)
        )
        cpu_time_ms = (
            float(solve_cpu_time_ms)
            if isinstance(solve_cpu_time_ms, (int, float))
            else child.get("cpu_time_ms")
        )

        peak_rss_for_metrics = peak_rss
        if isinstance(solve_peak_rss_bytes, (int, float)) and float(solve_peak_rss_bytes) > 0:
            peak_rss_for_metrics = int(float(solve_peak_rss_bytes))
        peak_memory_mb = (
            round(float(peak_rss_for_metrics) / (1024.0 * 1024.0), 6)
            if peak_rss_for_metrics > 0
            else None
        )
        max_rss_kb = int(round(float(peak_rss_for_metrics) / 1024.0)) if peak_rss_for_metrics > 0 else None

        mem_integral_for_metrics = mem_integral_byte_s
        if isinstance(solve_mem_integral_byte_s, (int, float)) and float(solve_mem_integral_byte_s) > 0:
            mem_integral_for_metrics = float(solve_mem_integral_byte_s)
        mem_integral_mb_ms = (
            round(mem_integral_for_metrics * 1000.0 / (1024.0 * 1024.0), 6)
            if mem_integral_for_metrics > 0
            else None
        )

        return {
            "repeat_idx": repeat_idx,
            "wall_time_ms": wall_time_ms,
            "peak_memory_mb": peak_memory_mb,
            "instruction_count": instruction_count,
            "cycles": cycles,
            "timed_out": timed_out,
            "crashed": crashed,
            "exec_success": exec_success,
            "correct": correct,
            "output_match": output_match,
            "judge_status": judge_status,
            "judge_score": float(child.get("judge_score", 1.0 if correct else 0.0)) if exec_success else 0.0,
            "return_code": return_code,
            "error_type": error_type,
            "stderr_excerpt": _stderr_excerpt(stderr_bytes_raw, stderr_excerpt_chars),
            "stderr_hash": _sha256_hex(stderr_bytes_raw),
            "stdout_bytes": len(stdout_bytes_raw),
            "cpu_time_ms": cpu_time_ms,
            "memory_integral_mb_ms": mem_integral_mb_ms,
            "max_rss_kb": max_rss_kb,
            "exception": child.get("exception"),
            "solve_only_measured": isinstance(solve_wall_time_ms, (int, float)),
            "instruction_measurement_error": child.get("instruction_measurement_error"),
        }


def _derive_case_status(repeats: List[Dict[str, Any]]) -> Tuple[bool, bool, bool, str, Optional[str], float]:
    timed_out = any(bool(r.get("timed_out")) for r in repeats)
    crashed = any(bool(r.get("crashed")) for r in repeats)
    all_exec_success = bool(repeats) and all(bool(r.get("exec_success")) for r in repeats)
    all_correct = bool(repeats) and all(bool(r.get("correct")) for r in repeats)
    judge_score = float(sum(float(r.get("judge_score", 0.0)) for r in repeats) / len(repeats)) if repeats else 0.0

    if timed_out:
        return all_exec_success, timed_out, crashed, "timeout", "timeout", judge_score
    if crashed:
        return all_exec_success, timed_out, crashed, "runtime_error", "runtime_error", judge_score
    if all_exec_success and all_correct:
        return all_exec_success, timed_out, crashed, "accepted", None, judge_score
    if all_exec_success:
        return all_exec_success, timed_out, crashed, "wrong_answer", "wrong_answer", judge_score
    return all_exec_success, timed_out, crashed, "runtime_error", "runtime_error", judge_score


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate reference solver across all puzzle samples with repeat profiling.")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--solver-dir", default="solver")
    ap.add_argument("--output-dir", default="eval/results")
    ap.add_argument("--skip-item-indexes-json", default=None, help="JSON mapping puzzle -> 1-based sample indexes to skip.")
    ap.add_argument("--puzzle", default=None, help="Only one puzzle, e.g. yinyang")
    ap.add_argument("--case-limit", type=int, default=-1, help="Max cases per puzzle; -1 means all")
    ap.add_argument("--timeout-sec", type=float, default=60.0, help="Per-repeat timeout in seconds; <=0 disables timeout.")
    ap.add_argument("--repeats", type=int, default=12)
    ap.add_argument("--warmup", type=int, default=1, help="Warmup runs per case before measured repeats (not recorded).")
    ap.add_argument("--sample-interval-sec", type=float, default=0.002)
    ap.add_argument("--stderr-excerpt-chars", type=int, default=1000)
    ap.add_argument("--case-split", default="anchor", choices=["anchor", "transfer_pool", "stressful"])
    ap.add_argument("--validation-mode", default="anchor_eval", choices=["anchor_eval", "pool_eval", "stressful_eval"])
    ap.add_argument("--profile-aggregation-rule", default="trimmed_mean_drop_minmax", choices=["trimmed_mean_drop_minmax", "mean", "median"])
    ap.add_argument("--instruction-tool", default="auto", choices=["auto", "perf", "none"])
    ap.add_argument("--memory-limit-mb", type=float, default=-1.0, help="Per-process memory limit in MB; <=0 disables limit.")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    data_dir = (repo_root / args.data_dir).resolve()
    solver_dir = (repo_root / args.solver_dir).resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    skip_item_indexes_path = Path(args.skip_item_indexes_json).resolve() if args.skip_item_indexes_json else None
    output_dir.mkdir(parents=True, exist_ok=True)

    runner_script = (repo_root / "eval" / "_case_runner.py").resolve()
    if not runner_script.exists():
        raise SystemExit(f"Runner script missing: {runner_script}")

    summary_path = output_dir / "ref_solver_eval_summary.json"

    files = _iter_data_files(data_dir, args.puzzle)
    if not files:
        raise SystemExit(f"No sample files found in {data_dir}")

    skip_item_indexes: Dict[str, set[int]] = {}
    if skip_item_indexes_path is not None:
        if not skip_item_indexes_path.exists():
            raise SystemExit(f"Missing skip-item-indexes file: {skip_item_indexes_path}")
        skip_item_indexes = _load_skip_item_indexes_json(skip_item_indexes_path)

    perf_enabled = False
    perf_probe_reason = "disabled"
    if args.instruction_tool in {"auto", "perf"}:
        perf_enabled, perf_probe_reason = _detect_perf_available(repo_root)
    if args.instruction_tool == "none":
        perf_enabled = False
        perf_probe_reason = "forced_none"
    if args.instruction_tool == "perf" and not perf_enabled:
        raise SystemExit(f"--instruction-tool=perf but perf unavailable: {perf_probe_reason}")

    all_case_records: List[Dict[str, Any]] = []
    all_repeat_records: List[Dict[str, Any]] = []
    total_skipped_cases = 0

    print(f"[ref-eval] files={len(files)} repeats={args.repeats} timeout={args.timeout_sec}s perf={perf_enabled} ({perf_probe_reason})", flush=True)

    for puzzle, file_path in files:
        rows = _load_jsonl(file_path)
        if args.case_limit >= 0:
            rows = rows[: args.case_limit]

        solver_file = solver_dir / f"{puzzle}.py"
        has_code = solver_file.exists()
        puzzle_case_records: List[Dict[str, Any]] = []
        puzzle_repeat_records: List[Dict[str, Any]] = []

        print(f"[ref-eval] puzzle={puzzle} cases={len(rows)} has_code={has_code}", flush=True)

        skip_indexes = skip_item_indexes.get(puzzle, set())
        skipped_count = 0

        for idx, item in enumerate(rows, start=1):
            if idx in skip_indexes:
                skipped_count += 1
                continue

            pool_case_id = item.get("id")
            if pool_case_id is None:
                pool_case_id = f"{puzzle}:{idx}"

            pool_case_group = _infer_pool_case_group(item)
            input_size_proxy = _infer_input_size_proxy(item)
            case_split = str(item.get("case_split", args.case_split))

            case_key = f"{puzzle}::{pool_case_id}"
            case_repeats: List[Dict[str, Any]] = []

            if has_code:
                for _ in range(max(0, args.warmup)):
                    _ = _run_one_repeat(
                        repo_root=repo_root,
                        runner_script=runner_script,
                        puzzle=puzzle,
                        item=item,
                        repeat_idx=0,
                        timeout_sec=args.timeout_sec,
                        sample_interval_sec=args.sample_interval_sec,
                        stderr_excerpt_chars=args.stderr_excerpt_chars,
                        perf_enabled=perf_enabled,
                        memory_limit_mb=args.memory_limit_mb,
                    )
                for rep in range(1, args.repeats + 1):
                    repeat_row = _run_one_repeat(
                        repo_root=repo_root,
                        runner_script=runner_script,
                        puzzle=puzzle,
                        item=item,
                        repeat_idx=rep,
                        timeout_sec=args.timeout_sec,
                        sample_interval_sec=args.sample_interval_sec,
                        stderr_excerpt_chars=args.stderr_excerpt_chars,
                        perf_enabled=perf_enabled,
                        memory_limit_mb=args.memory_limit_mb,
                    )
                    repeat_record = {
                        "puzzle_name": puzzle,
                        "pool_case_id": pool_case_id,
                        "pool_case_group": pool_case_group,
                        "case_key": case_key,
                        "repeat_idx": rep,
                        "wall_time_ms": repeat_row["wall_time_ms"],
                        "peak_memory_mb": repeat_row["peak_memory_mb"],
                        "instruction_count": repeat_row["instruction_count"],
                        "timed_out": repeat_row["timed_out"],
                        "crashed": repeat_row["crashed"],
                        "cycles": repeat_row["cycles"],
                        "exec_success": repeat_row["exec_success"],
                        "correct": repeat_row["correct"],
                        "judge_status": repeat_row["judge_status"],
                        "return_code": repeat_row["return_code"],
                        "error_type": repeat_row["error_type"],
                        "stderr_hash": repeat_row["stderr_hash"],
                        "stdout_bytes": repeat_row["stdout_bytes"],
                        "cpu_time_ms": repeat_row["cpu_time_ms"],
                        "memory_integral_mb_ms": repeat_row["memory_integral_mb_ms"],
                        "max_rss_kb": repeat_row["max_rss_kb"],
                        "solve_only_measured": repeat_row["solve_only_measured"],
                        "instruction_measurement_error": repeat_row.get("instruction_measurement_error"),
                    }
                    case_repeats.append(repeat_row)
                    puzzle_repeat_records.append(repeat_record)
            else:
                for rep in range(1, args.repeats + 1):
                    repeat_row = {
                        "repeat_idx": rep,
                        "wall_time_ms": None,
                        "peak_memory_mb": None,
                        "instruction_count": None,
                        "timed_out": False,
                        "crashed": False,
                        "exec_success": False,
                        "correct": False,
                        "output_match": False,
                        "judge_status": "runtime_error",
                        "judge_score": 0.0,
                        "return_code": None,
                        "error_type": "missing_solver_code",
                        "stderr_excerpt": "",
                        "stderr_hash": None,
                        "stdout_bytes": 0,
                        "cpu_time_ms": None,
                        "memory_integral_mb_ms": None,
                        "max_rss_kb": None,
                        "cycles": None,
                    }
                    case_repeats.append(repeat_row)
                    puzzle_repeat_records.append(
                        {
                            "puzzle_name": puzzle,
                            "pool_case_id": pool_case_id,
                            "pool_case_group": pool_case_group,
                            "case_key": case_key,
                            "repeat_idx": rep,
                            "wall_time_ms": None,
                            "peak_memory_mb": None,
                            "instruction_count": None,
                            "timed_out": False,
                            "crashed": False,
                            "cycles": None,
                            "exec_success": False,
                            "correct": False,
                            "judge_status": "runtime_error",
                            "return_code": None,
                            "error_type": "missing_solver_code",
                            "stderr_hash": None,
                            "stdout_bytes": 0,
                            "cpu_time_ms": None,
                            "memory_integral_mb_ms": None,
                            "max_rss_kb": None,
                            "solve_only_measured": False,
                            "instruction_measurement_error": "missing_solver_code",
                        }
                    )

            status_exec_success, status_timed_out, status_crashed, judge_status, error_type, judge_score = _derive_case_status(case_repeats)

            perf_source = [r for r in case_repeats if bool(r.get("exec_success")) and bool(r.get("correct"))]
            if not perf_source:
                perf_source = [r for r in case_repeats if bool(r.get("exec_success"))]

            wall_time_ms = _aggregate([r.get("wall_time_ms") for r in perf_source], args.profile_aggregation_rule)
            peak_memory_mb = _aggregate([r.get("peak_memory_mb") for r in perf_source], args.profile_aggregation_rule)
            instruction_count = _aggregate([r.get("instruction_count") for r in perf_source], args.profile_aggregation_rule)
            cycles = _aggregate([r.get("cycles") for r in perf_source], args.profile_aggregation_rule)
            cpu_time_ms = _aggregate([r.get("cpu_time_ms") for r in perf_source], args.profile_aggregation_rule)
            memory_integral_mb_ms = _aggregate([r.get("memory_integral_mb_ms") for r in perf_source], args.profile_aggregation_rule)
            max_rss_kb = _aggregate([r.get("max_rss_kb") for r in perf_source], args.profile_aggregation_rule)

            first_err = next((r for r in case_repeats if r.get("error_type")), None)
            first_stderr = next((r for r in case_repeats if r.get("stderr_excerpt")), None)
            first_instr_err = next((r for r in case_repeats if r.get("instruction_measurement_error")), None)
            primary = case_repeats[0] if case_repeats else {}

            case_record = {
                "puzzle_name": puzzle,
                "pool_case_id": pool_case_id,
                "pool_case_group": pool_case_group,
                "input_size_proxy": input_size_proxy,
                "case_split": case_split,
                "solver_type": "reference",
                "has_code": has_code,
                "exec_success": status_exec_success,
                "timed_out": status_timed_out,
                "crashed": status_crashed,
                "return_code": primary.get("return_code"),
                "error_type": error_type if error_type is not None else (first_err.get("error_type") if first_err else None),
                "stderr_excerpt": (first_stderr.get("stderr_excerpt") if first_stderr else ""),
                "stderr_hash": (first_stderr.get("stderr_hash") if first_stderr else None),
                "stdout_bytes": int(primary.get("stdout_bytes") or 0),
                "correct": bool(case_repeats) and all(bool(r.get("correct")) for r in case_repeats),
                "judge_status": judge_status,
                "output_match": bool(case_repeats) and all(bool(r.get("output_match")) for r in case_repeats),
                "judge_score": round(float(judge_score), 6),
                "validation_mode": args.validation_mode,
                "wall_time_ms": wall_time_ms,
                "cpu_time_ms": cpu_time_ms,
                "peak_memory_mb": peak_memory_mb,
                "memory_integral_mb_ms": memory_integral_mb_ms,
                "instruction_count": instruction_count,
                "cycles": cycles,
                "max_rss_kb": max_rss_kb,
                "profile_repeat_count": args.repeats,
                "profile_aggregation_rule": args.profile_aggregation_rule,
                "case_key": case_key,
                "perf_measurement_enabled": perf_enabled,
                "perf_probe_reason": perf_probe_reason,
                "performance_scope": "solve_only_for_time_and_memory",
                "instruction_cycle_scope": "solve_only_via_perf_event_open",
                "warmup_count": args.warmup,
                "memory_limit_mb": args.memory_limit_mb if args.memory_limit_mb > 0 else None,
                "instruction_measurement_error": (
                    first_instr_err.get("instruction_measurement_error")
                    if first_instr_err
                    else None
                ),
            }
            puzzle_case_records.append(case_record)

            print(
                f"  - {puzzle} case={idx}/{len(rows)} id={pool_case_id} status={judge_status} "
                f"wall_ms={wall_time_ms}",
                flush=True,
            )

        puzzle_dir = output_dir / puzzle
        puzzle_dir.mkdir(parents=True, exist_ok=True)
        puzzle_case_out = puzzle_dir / "ref_solver_case_metrics.jsonl"
        puzzle_repeat_out = puzzle_dir / "ref_solver_repeat_metrics.jsonl"
        puzzle_summary_out = puzzle_dir / "ref_solver_eval_summary.json"

        with puzzle_case_out.open("w", encoding="utf-8") as f:
            for row in puzzle_case_records:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        with puzzle_repeat_out.open("w", encoding="utf-8") as f:
            for row in puzzle_repeat_records:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        puzzle_summary = {
            "generated_at_unix": int(time.time()),
            "puzzle_name": puzzle,
            "repo_root": str(repo_root),
            "data_file": str(file_path),
            "output_dir": str(puzzle_dir),
            "case_metrics_file": str(puzzle_case_out),
            "repeat_metrics_file": str(puzzle_repeat_out),
            "skip_item_indexes_file": str(skip_item_indexes_path) if skip_item_indexes_path else None,
            "total_cases": len(puzzle_case_records),
            "skipped_cases": skipped_count,
            "total_repeats": len(puzzle_repeat_records),
            "repeats_per_case": args.repeats,
            "warmup_per_case": args.warmup,
            "timeout_sec": args.timeout_sec,
            "memory_limit_mb": args.memory_limit_mb if args.memory_limit_mb > 0 else None,
            "sample_interval_sec": args.sample_interval_sec,
            "profile_aggregation_rule": args.profile_aggregation_rule,
            "perf_measurement_enabled": perf_enabled,
            "perf_probe_reason": perf_probe_reason,
            "status_counts": {
                "accepted": sum(1 for r in puzzle_case_records if r.get("judge_status") == "accepted"),
                "wrong_answer": sum(1 for r in puzzle_case_records if r.get("judge_status") == "wrong_answer"),
                "timeout": sum(1 for r in puzzle_case_records if r.get("judge_status") == "timeout"),
                "runtime_error": sum(1 for r in puzzle_case_records if r.get("judge_status") == "runtime_error"),
            },
        }
        puzzle_summary_out.write_text(json.dumps(puzzle_summary, indent=2, ensure_ascii=False), encoding="utf-8")

        all_case_records.extend(puzzle_case_records)
        all_repeat_records.extend(puzzle_repeat_records)
        total_skipped_cases += skipped_count

        print(f"[ref-eval] wrote case metrics: {puzzle_case_out}")
        print(f"[ref-eval] wrote repeat metrics: {puzzle_repeat_out}")
        print(f"[ref-eval] wrote summary: {puzzle_summary_out}")

    # Root-level global summary across puzzles.
    summary = {
        "generated_at_unix": int(time.time()),
        "repo_root": str(repo_root),
        "data_dir": str(data_dir),
        "solver_dir": str(solver_dir),
        "output_dir": str(output_dir),
        "total_cases": len(all_case_records),
        "total_repeats": len(all_repeat_records),
        "skipped_cases": total_skipped_cases,
        "skip_item_indexes_file": str(skip_item_indexes_path) if skip_item_indexes_path else None,
        "puzzles": sorted({str(r["puzzle_name"]) for r in all_case_records}),
        "repeats_per_case": args.repeats,
        "warmup_per_case": args.warmup,
        "timeout_sec": args.timeout_sec,
        "memory_limit_mb": args.memory_limit_mb if args.memory_limit_mb > 0 else None,
        "sample_interval_sec": args.sample_interval_sec,
        "profile_aggregation_rule": args.profile_aggregation_rule,
        "perf_measurement_enabled": perf_enabled,
        "perf_probe_reason": perf_probe_reason,
        "status_counts": {
            "accepted": sum(1 for r in all_case_records if r.get("judge_status") == "accepted"),
            "wrong_answer": sum(1 for r in all_case_records if r.get("judge_status") == "wrong_answer"),
            "timeout": sum(1 for r in all_case_records if r.get("judge_status") == "timeout"),
            "runtime_error": sum(1 for r in all_case_records if r.get("judge_status") == "runtime_error"),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ref-eval] wrote global summary: {summary_path}")


if __name__ == "__main__":
    main()
