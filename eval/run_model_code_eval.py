#!/usr/bin/env python3
from __future__ import annotations

import ast
import argparse
import hashlib
import importlib
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
import types
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


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _to_comparable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _to_comparable(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, tuple):
        return [_to_comparable(v) for v in obj]
    if isinstance(obj, list):
        return [_to_comparable(v) for v in obj]
    if isinstance(obj, set):
        return sorted((_to_comparable(v) for v in obj), key=lambda x: repr(x))
    return obj


def _normalize_prediction_backslashes_for_compare(value: Any) -> Any:
    if isinstance(value, str):
        while "\\\\" in value:
            value = value.replace("\\\\", "\\")
        return value
    if isinstance(value, list):
        return [_normalize_prediction_backslashes_for_compare(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_prediction_backslashes_for_compare(v) for k, v in value.items()}
    return value


def _normalize_prediction(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return value
    if text == "No Solution":
        return value

    if text[0] in ("[", "{", '"', "'"):
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
                if isinstance(parsed, str):
                    inner = parsed.strip()
                    if inner and inner != text and inner[0] in ("[", "{", '"', "'"):
                        text = inner
                        continue
                return parsed
            except Exception:
                continue
    return value


def _norm_pt(pt: Any) -> tuple[int, int] | None:
    if isinstance(pt, (tuple, list)) and len(pt) == 2:
        a, b = pt[0], pt[1]
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return (int(a), int(b))
    return None


def _parse_hashi_edge_key(key: Any) -> tuple[tuple[int, int], tuple[int, int]] | None:
    if isinstance(key, (tuple, list)) and len(key) == 2:
        p1 = _norm_pt(key[0])
        p2 = _norm_pt(key[1])
        if p1 is not None and p2 is not None:
            return (p1, p2) if p1 <= p2 else (p2, p1)

    if isinstance(key, str):
        nums = re.findall(r"-?\d+", key)
        if len(nums) == 4:
            p1 = (int(nums[0]), int(nums[1]))
            p2 = (int(nums[2]), int(nums[3]))
            return (p1, p2) if p1 <= p2 else (p2, p1)
    return None


def _normalize_hashi_answer(ans: Any) -> dict[str, int] | None:
    if not isinstance(ans, dict):
        return None
    out: dict[str, int] = {}
    for k, v in ans.items():
        edge = _parse_hashi_edge_key(k)
        if edge is None:
            return None
        if not isinstance(v, (int, float)):
            return None
        vv = int(v)
        if vv < 0:
            return None
        ek = f"{edge[0][0]},{edge[0][1]}|{edge[1][0]},{edge[1][1]}"
        out[ek] = vv
    return out


def _answers_match(puzzle: str, prediction: Any, expected_answer: Any) -> bool:
    tester = _load_answer_tester_from_construction(puzzle)
    if tester is not None:
        try:
            return bool(tester(prediction, expected_answer))
        except Exception:
            pass

    if puzzle == "hashi":
        np = _normalize_hashi_answer(prediction)
        ne = _normalize_hashi_answer(expected_answer)
        if np is not None and ne is not None:
            return np == ne
    return _to_comparable(prediction) == _to_comparable(expected_answer)


_ANSWER_TESTER_CACHE: Dict[str, Any] = {}


def _import_construction_module(module_name: str):
    try:
        return importlib.import_module(module_name), None
    except Exception as exc:
        msg = str(exc)
        if "No module named 'matplotlib'" not in msg:
            return None, exc

    fake_matplotlib = types.ModuleType("matplotlib")
    fake_pyplot = types.ModuleType("matplotlib.pyplot")
    fake_patches = types.ModuleType("matplotlib.patches")
    fake_image = types.ModuleType("matplotlib.image")
    fake_backends = types.ModuleType("matplotlib.backends")
    fake_backend_agg = types.ModuleType("matplotlib.backends.backend_agg")
    fake_figure = types.ModuleType("matplotlib.figure")
    setattr(fake_matplotlib, "pyplot", fake_pyplot)
    setattr(fake_matplotlib, "patches", fake_patches)
    setattr(fake_matplotlib, "image", fake_image)
    setattr(fake_matplotlib, "backends", fake_backends)
    setattr(fake_matplotlib, "figure", fake_figure)
    setattr(fake_backends, "backend_agg", fake_backend_agg)
    setattr(fake_backend_agg, "FigureCanvasAgg", type("FigureCanvasAgg", (), {}))
    setattr(fake_figure, "Figure", type("Figure", (), {}))

    fake_names = (
        "matplotlib", "matplotlib.pyplot", "matplotlib.patches", "matplotlib.image",
        "matplotlib.backends", "matplotlib.backends.backend_agg", "matplotlib.figure",
    )
    old_entries = {k: sys.modules.get(k) for k in fake_names}
    sys.modules["matplotlib"] = fake_matplotlib
    sys.modules["matplotlib.pyplot"] = fake_pyplot
    sys.modules["matplotlib.patches"] = fake_patches
    sys.modules["matplotlib.image"] = fake_image
    sys.modules["matplotlib.backends"] = fake_backends
    sys.modules["matplotlib.backends.backend_agg"] = fake_backend_agg
    sys.modules["matplotlib.figure"] = fake_figure
    try:
        return importlib.import_module(module_name), None
    except Exception as exc2:
        return None, exc2
    finally:
        for k, v in old_entries.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def _load_answer_tester_from_construction(puzzle: str):
    if puzzle in _ANSWER_TESTER_CACHE:
        return _ANSWER_TESTER_CACHE[puzzle]
    module_name = f"construction.{puzzle}"
    module, _ = _import_construction_module(module_name)
    if module is None:
        _ANSWER_TESTER_CACHE[puzzle] = None
        return None
    tester = getattr(module, "test_answer", None)
    out = tester if callable(tester) else None
    _ANSWER_TESTER_CACHE[puzzle] = out
    return out


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    return {"git_commit": commit, "git_dirty": dirty}


def _pip_freeze_hash(repo_root: Path) -> Optional[str]:
    rc, out, _ = _run_cmd_text([sys.executable, "-m", "pip", "freeze"], cwd=repo_root, timeout_sec=60.0)
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
    for c in proc.children(recursive=True):
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


def _stderr_excerpt(stderr_bytes: bytes, n_chars: int) -> str:
    text = stderr_bytes.decode("utf-8", errors="replace")
    if len(text) <= n_chars:
        return text
    return text[-n_chars:]


def _run_one_repeat(
    *,
    repo_root: Path,
    runner_script: Path,
    puzzle: str,
    code_text: str,
    observation: Any,
    expected_answer: Any,
    repeat_idx: int,
    timeout_sec: float,
    sample_interval_sec: float,
    stderr_excerpt_chars: int,
    perf_enabled: bool,
    memory_limit_mb: float,
) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="model_code_eval_") as td:
        tmpdir = Path(td)
        code_file = tmpdir / "solution.py"
        obs_file = tmpdir / "observation.json"
        out_file = tmpdir / "out.json"
        stdout_file = tmpdir / "stdout.bin"
        stderr_file = tmpdir / "stderr.bin"

        code_file.write_text(code_text, encoding="utf-8")
        obs_file.write_text(json.dumps(observation, ensure_ascii=False), encoding="utf-8")

        cmd = [
            sys.executable,
            str(runner_script),
            "--code-file",
            str(code_file),
            "--observation-json",
            str(obs_file),
            "--out-json",
            str(out_file),
        ]
        if perf_enabled:
            cmd.append("--measure-instructions")
        if memory_limit_mb > 0:
            cmd.extend(["--memory-limit-mb", str(memory_limit_mb)])

        with stdout_file.open("wb") as fout, stderr_file.open("wb") as ferr:
            proc = subprocess.Popen(cmd, cwd=str(repo_root), stdout=fout, stderr=ferr)
            t0 = time.perf_counter()
            timed_out = False
            last_t = 0.0
            while True:
                now = time.perf_counter() - t0
                last_t = now
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

        stdout_raw = stdout_file.read_bytes() if stdout_file.exists() else b""
        stderr_raw = stderr_file.read_bytes() if stderr_file.exists() else b""

        child: Dict[str, Any] = {}
        if out_file.exists():
            try:
                child = json.loads(out_file.read_text(encoding="utf-8"))
            except Exception:
                child = {}

        child_exec_success = bool(child.get("exec_success"))
        has_prediction = "prediction" in child
        prediction = _normalize_prediction(child.get("prediction"))
        prediction = _normalize_prediction_backslashes_for_compare(prediction)
        output_match = False
        if child_exec_success and has_prediction:
            output_match = _answers_match(puzzle, prediction, expected_answer)

        crashed = (not timed_out) and (return_code != 0)
        if timed_out:
            error_type = "timeout"
            judge_status = "timeout"
            exec_success = False
        elif crashed:
            error_type = "runtime_error"
            judge_status = "runtime_error"
            exec_success = False
        else:
            child_error = child.get("error_type")
            if child_exec_success:
                error_type = None if output_match else "wrong_answer"
                judge_status = "accepted" if output_match else "wrong_answer"
                exec_success = True
            else:
                error_type = str(child_error or "runtime_error")
                judge_status = "runtime_error"
                exec_success = False

        solve_wall = child.get("solve_wall_time_ms")
        solve_cpu = child.get("solve_cpu_time_ms")
        solve_peak = child.get("solve_peak_rss_bytes")
        solve_mem_int = child.get("solve_memory_integral_byte_seconds")
        solve_instr = child.get("solve_instruction_count")
        solve_cycles = child.get("solve_cycles")

        peak_mb = None
        max_rss_kb = None
        if isinstance(solve_peak, (int, float)) and float(solve_peak) > 0:
            peak_mb = round(float(solve_peak) / (1024.0 * 1024.0), 6)
            max_rss_kb = int(round(float(solve_peak) / 1024.0))

        mem_integral_mb_ms = None
        if isinstance(solve_mem_int, (int, float)) and float(solve_mem_int) >= 0:
            mem_integral_mb_ms = round(float(solve_mem_int) * 1000.0 / (1024.0 * 1024.0), 6)

        wall_time_ms = float(solve_wall) if isinstance(solve_wall, (int, float)) else round(last_t * 1000.0, 6)
        cpu_time_ms = float(solve_cpu) if isinstance(solve_cpu, (int, float)) else child.get("cpu_time_ms")

        return {
            "repeat_idx": repeat_idx,
            "timed_out": timed_out,
            "crashed": crashed,
            "return_code": return_code,
            "error_type": error_type,
            "exec_success": exec_success,
            "correct": bool(output_match),
            "judge_status": judge_status,
            "output_match": bool(output_match),
            "judge_score": 1.0 if output_match else 0.0,
            "wall_time_ms": wall_time_ms,
            "cpu_time_ms": cpu_time_ms,
            "peak_memory_mb": peak_mb,
            "memory_integral_mb_ms": mem_integral_mb_ms,
            "instruction_count": int(solve_instr) if isinstance(solve_instr, (int, float)) else None,
            "cycles": int(solve_cycles) if isinstance(solve_cycles, (int, float)) else None,
            "max_rss_kb": max_rss_kb,
            "stdout_bytes": len(stdout_raw),
            "stderr_hash": _sha256_hex(stderr_raw),
            "stderr_excerpt": _stderr_excerpt(stderr_raw, stderr_excerpt_chars),
            "instruction_measurement_error": child.get("instruction_measurement_error"),
            "exception": child.get("exception"),
            "has_solve": bool(child.get("has_solve")),
            "solve_only_measured": isinstance(solve_wall, (int, float)),
            "raw_child_error_type": child.get("error_type"),
        }


def _precheck_code_once(
    *,
    repo_root: Path,
    runner_script: Path,
    code_text: str,
    memory_limit_mb: float,
) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="model_code_precheck_") as td:
        tmpdir = Path(td)
        code_file = tmpdir / "solution.py"
        obs_file = tmpdir / "observation.json"
        out_file = tmpdir / "out.json"
        code_file.write_text(code_text, encoding="utf-8")
        obs_file.write_text("{}", encoding="utf-8")

        cmd = [
            sys.executable,
            str(runner_script),
            "--code-file",
            str(code_file),
            "--observation-json",
            str(obs_file),
            "--out-json",
            str(out_file),
            "--precheck-only",
        ]
        if memory_limit_mb > 0:
            cmd.extend(["--memory-limit-mb", str(memory_limit_mb)])

        p = subprocess.run(cmd, cwd=str(repo_root), capture_output=True)
        out: Dict[str, Any] = {}
        if out_file.exists():
            try:
                out = json.loads(out_file.read_text(encoding="utf-8"))
            except Exception:
                out = {}
        out["return_code"] = int(p.returncode)
        out["stderr_hash"] = _sha256_hex(p.stderr or b"")
        return out


def _make_fast_fail_repeat_from(
    template: Dict[str, Any],
    repeat_idx: int,
) -> Dict[str, Any]:
    """Create a synthetic repeat row for deterministic non-runnable code paths."""
    return {
        "repeat_idx": repeat_idx,
        "timed_out": False,
        "crashed": False,
        "return_code": template.get("return_code"),
        "error_type": template.get("error_type"),
        "exec_success": False,
        "correct": False,
        "judge_status": "runtime_error",
        "output_match": False,
        "judge_score": 0.0,
        "wall_time_ms": None,
        "cpu_time_ms": None,
        "peak_memory_mb": None,
        "memory_integral_mb_ms": None,
        "instruction_count": None,
        "cycles": None,
        "max_rss_kb": None,
        "stdout_bytes": 0,
        "stderr_hash": template.get("stderr_hash"),
        "stderr_excerpt": template.get("stderr_excerpt", ""),
        "instruction_measurement_error": template.get("instruction_measurement_error"),
        "exception": template.get("exception"),
        "has_solve": bool(template.get("has_solve")),
        "solve_only_measured": False,
        "raw_child_error_type": template.get("raw_child_error_type"),
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
    # prioritize memory-limit if any repeat hit it
    if any(str(r.get("error_type") or "") == "memory_limit" for r in repeats):
        return all_exec_success, timed_out, crashed, "runtime_error", "memory_limit", judge_score
    if all_exec_success and all_correct:
        return all_exec_success, timed_out, crashed, "accepted", None, judge_score
    if all_exec_success:
        return all_exec_success, timed_out, crashed, "wrong_answer", "wrong_answer", judge_score
    return all_exec_success, timed_out, crashed, "runtime_error", "runtime_error", judge_score


def _load_puzzle_samples(data_dir: Path, puzzle: str) -> List[Dict[str, Any]]:
    fp = data_dir / f"{puzzle}_samples.jsonl"
    if not fp.exists():
        raise FileNotFoundError(f"Missing data file for puzzle={puzzle}: {fp}")
    return _load_jsonl(fp)


def _discover_model_files(
    extracted_dir: Path,
    only_model: Optional[str],
    include_models: Optional[set[str]],
    exclude_models: set[str],
) -> List[Tuple[str, Path, Path]]:
    out: List[Tuple[str, Path, Path]] = []
    for rr in sorted(extracted_dir.glob("results-*.rerun.jsonl")):
        model = rr.name[len("results-") : -len(".rerun.jsonl")]
        if only_model is not None and model != only_model:
            continue
        if include_models is not None and model not in include_models:
            continue
        if model in exclude_models:
            continue
        ex = rr.with_name(f"results-{model}.extracted.jsonl")
        if ex.exists():
            out.append((model, ex, rr))
    return out


def _safe_slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)


def _load_timeout_config(path: Path) -> Dict[str, float]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, float] = {}

    def _set_key(k: str, v: Any) -> None:
        if not isinstance(k, str) or "::" not in k:
            return
        if isinstance(v, dict):
            vv = v.get("timeout_sec")
        else:
            vv = v
        if isinstance(vv, (int, float)) and float(vv) > 0:
            out[k] = float(vv)

    if isinstance(obj, dict):
        cases = obj.get("cases")
        if isinstance(cases, dict):
            for k, v in cases.items():
                _set_key(str(k), v)

        per_puzzle = obj.get("per_puzzle")
        if isinstance(per_puzzle, dict):
            for puzzle, id_map in per_puzzle.items():
                if not isinstance(id_map, dict):
                    continue
                for case_id, rec in id_map.items():
                    _set_key(f"{str(puzzle)}::{str(case_id)}", rec)

        for k, v in obj.items():
            _set_key(str(k), v)

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


def _load_model_code_idx_map(path: Path) -> Dict[str, set[int]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        return {}
    out: Dict[str, set[int]] = {}
    for model_name, idxs in obj.items():
        if not isinstance(model_name, str):
            continue
        if not isinstance(idxs, list):
            continue
        s: set[int] = set()
        for x in idxs:
            if isinstance(x, bool):
                continue
            if isinstance(x, int):
                s.add(x)
            elif isinstance(x, float) and float(x).is_integer():
                s.add(int(x))
            elif isinstance(x, str):
                xx = x.strip()
                if xx and xx.lstrip("-").isdigit():
                    s.add(int(xx))
        if s:
            out[model_name] = s
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate extracted model code on all samples of corresponding puzzle.")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--extracted-dir", required=True, help="Directory containing results-*.extracted.jsonl and .rerun.jsonl")
    ap.add_argument("--output-dir", default="eval/model_code_eval_results")
    ap.add_argument("--model", default=None, help="Only one model file stem, e.g. gpt-5.4")
    ap.add_argument("--models", default=None, help="Comma-separated model names to include.")
    ap.add_argument("--exclude-models", default=None, help="Comma-separated model names to exclude.")
    ap.add_argument("--puzzle", default=None, help="Only evaluate one puzzle type, e.g. sudoku")
    ap.add_argument("--code-limit", type=int, default=-1, help="Max code entries per model; -1 all")
    ap.add_argument("--code-idxs", default=None, help="Comma-separated code_idx whitelist to evaluate.")
    ap.add_argument("--code-idx-json", default=None, help="JSON mapping model_name -> [code_idx,...] whitelist.")
    ap.add_argument("--case-limit", type=int, default=-1, help="Max sample cases per puzzle; -1 all")
    ap.add_argument("--timeout-sec", type=float, default=60.0, help="Per-repeat timeout seconds; <=0 disables")
    ap.add_argument("--timeout-config", default=None, help="JSON file mapping '<puzzle>::<pool_case_id>' to timeout_sec.")
    ap.add_argument("--skip-item-indexes-json", default=None, help="JSON mapping puzzle -> 1-based sample indexes to skip.")
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--repeats", type=int, default=12)
    ap.add_argument("--memory-limit-mb", type=float, default=1024.0, help="Per-process memory limit MB; <=0 disables")
    ap.add_argument("--sample-interval-sec", type=float, default=0.002)
    ap.add_argument("--stderr-excerpt-chars", type=int, default=1000)
    ap.add_argument("--profile-aggregation-rule", default="trimmed_mean_drop_minmax", choices=["trimmed_mean_drop_minmax", "mean", "median"])
    ap.add_argument("--instruction-tool", default="auto", choices=["auto", "perf", "none"])
    ap.add_argument("--case-split", default="anchor", choices=["anchor", "transfer_pool", "stressful"])
    ap.add_argument("--validation-mode", default="anchor_eval", choices=["anchor_eval", "pool_eval", "stressful_eval"])
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    data_dir = (repo_root / args.data_dir).resolve()
    extracted_dir = Path(args.extracted_dir).resolve()
    output_root = Path(args.output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    timeout_config_path = Path(args.timeout_config).resolve() if args.timeout_config else None
    skip_item_indexes_path = Path(args.skip_item_indexes_json).resolve() if args.skip_item_indexes_json else None
    code_idx_json_path = Path(args.code_idx_json).resolve() if args.code_idx_json else None

    runner_script = (repo_root / "eval" / "_model_code_case_runner.py").resolve()
    if not runner_script.exists():
        raise SystemExit(f"Missing runner: {runner_script}")

    timeout_map: Dict[str, float] = {}
    if timeout_config_path is not None:
        if not timeout_config_path.exists():
            raise SystemExit(f"Missing timeout config: {timeout_config_path}")
        timeout_map = _load_timeout_config(timeout_config_path)
        if not timeout_map:
            raise SystemExit(f"Timeout config has no usable entries: {timeout_config_path}")

    skip_item_indexes: Dict[str, set[int]] = {}
    if skip_item_indexes_path is not None:
        if not skip_item_indexes_path.exists():
            raise SystemExit(f"Missing skip-item-indexes file: {skip_item_indexes_path}")
        skip_item_indexes = _load_skip_item_indexes_json(skip_item_indexes_path)

    cli_code_idx_whitelist: Optional[set[int]] = None
    if args.code_idxs:
        cli_code_idx_whitelist = set()
        for x in args.code_idxs.split(","):
            xx = x.strip()
            if xx and xx.lstrip("-").isdigit():
                cli_code_idx_whitelist.add(int(xx))
        if not cli_code_idx_whitelist:
            raise SystemExit("--code-idxs provided but no valid integers were parsed.")

    model_code_idx_map: Dict[str, set[int]] = {}
    if code_idx_json_path is not None:
        if not code_idx_json_path.exists():
            raise SystemExit(f"Missing code-idx-json file: {code_idx_json_path}")
        model_code_idx_map = _load_model_code_idx_map(code_idx_json_path)

    perf_enabled = False
    perf_probe_reason = "disabled"
    if args.instruction_tool in {"auto", "perf"}:
        perf_enabled, perf_probe_reason = _detect_perf_available(repo_root)
    if args.instruction_tool == "none":
        perf_enabled = False
        perf_probe_reason = "forced_none"
    if args.instruction_tool == "perf" and not perf_enabled:
        raise SystemExit(f"--instruction-tool=perf but unavailable: {perf_probe_reason}")

    include_models = None
    if args.models:
        include_models = {x.strip() for x in args.models.split(",") if x.strip()}
    # If code-idx JSON is provided and caller did not explicitly pin model(s),
    # default to only models present in that JSON mapping.
    elif code_idx_json_path is not None and args.model is None and model_code_idx_map:
        include_models = set(model_code_idx_map.keys())
    exclude_models: set[str] = set()
    if args.exclude_models:
        exclude_models = {x.strip() for x in args.exclude_models.split(",") if x.strip()}

    model_files = _discover_model_files(extracted_dir, args.model, include_models, exclude_models)
    if not model_files:
        raise SystemExit(f"No matching model files in {extracted_dir}")

    print(f"[model-eval] models={len(model_files)} repeats={args.repeats} warmup={args.warmup} perf={perf_enabled} ({perf_probe_reason})", flush=True)

    puzzle_cache: Dict[str, List[Dict[str, Any]]] = {}

    for model_name, extracted_file, rerun_file in model_files:
        print(f"[model-eval] model={model_name}", flush=True)
        model_slug = _safe_slug(model_name)
        model_out = output_root / model_slug
        model_out.mkdir(parents=True, exist_ok=True)

        summary_out = model_out / "model_code_eval_summary.json"

        ex_rows = _load_jsonl(extracted_file)
        rr_rows = _load_jsonl(rerun_file)
        ex_by_idx: Dict[Any, Dict[str, Any]] = {r.get("idx"): r for r in ex_rows if "idx" in r}

        # code entries from rerun rows (groundtruth alignment is already there)
        code_entries: List[Dict[str, Any]] = []
        for rr in rr_rows:
            idx = rr.get("idx")
            puzzle = rr.get("puzzle_type")
            if idx is None or not isinstance(puzzle, str) or not puzzle:
                continue
            if args.puzzle is not None and puzzle != args.puzzle:
                continue
            ex = ex_by_idx.get(idx, {})
            code = str(ex.get("code") or "")
            code_entries.append(
                {
                    "code_idx": idx,
                    "line_no": rr.get("line_no"),
                    "puzzle_name": puzzle,
                    "code": code,
                    "source_extracted_ok": bool(rr.get("extracted_ok", True)),
                    "source_matched": bool(rr.get("matched", True)),
                    "source_dataset_idx": rr.get("dataset_idx"),
                    "source_match_key": rr.get("match_key"),
                    "source_mode": rr.get("mode"),
                }
            )

        if args.code_limit >= 0:
            code_entries = code_entries[: args.code_limit]

        # Optional code_idx whitelist filters (intersection when both are provided).
        model_whitelist = model_code_idx_map.get(model_name)
        effective_whitelist: Optional[set[int]] = None
        if cli_code_idx_whitelist is not None and model_whitelist is not None:
            effective_whitelist = set(cli_code_idx_whitelist) & set(model_whitelist)
        elif cli_code_idx_whitelist is not None:
            effective_whitelist = set(cli_code_idx_whitelist)
        elif model_whitelist is not None:
            effective_whitelist = set(model_whitelist)

        if effective_whitelist is not None:
            code_entries = [
                ce
                for ce in code_entries
                if isinstance(ce.get("code_idx"), int) and int(ce["code_idx"]) in effective_whitelist
            ]

        case_records_by_puzzle: Dict[str, List[Dict[str, Any]]] = {}
        repeat_records_by_puzzle: Dict[str, List[Dict[str, Any]]] = {}
        used_case_timeouts_sec: List[float] = []
        puzzle_artifacts: Dict[str, Dict[str, Path]] = {}

        for puzzle_name in sorted({str(ce["puzzle_name"]) for ce in code_entries if ce.get("puzzle_name")}):
            puzzle_dir = model_out / puzzle_name
            puzzle_dir.mkdir(parents=True, exist_ok=True)
            case_out = puzzle_dir / "model_code_case_metrics.jsonl"
            repeat_out = puzzle_dir / "model_code_repeat_metrics.jsonl"
            case_out.write_text("", encoding="utf-8")
            repeat_out.write_text("", encoding="utf-8")
            puzzle_artifacts[puzzle_name] = {
                "puzzle_dir": puzzle_dir,
                "case_out": case_out,
                "repeat_out": repeat_out,
                "summary_out": puzzle_dir / "model_code_eval_summary.json",
            }

        def _push_repeat_record(puzzle_name: str, rec: Dict[str, Any]) -> None:
            repeat_records_by_puzzle.setdefault(puzzle_name, []).append(rec)
            art = puzzle_artifacts.get(puzzle_name)
            if art is not None:
                _append_jsonl(art["repeat_out"], rec)

        def _push_case_record(puzzle_name: str, rec: Dict[str, Any]) -> None:
            case_records_by_puzzle.setdefault(puzzle_name, []).append(rec)
            art = puzzle_artifacts.get(puzzle_name)
            if art is not None:
                _append_jsonl(art["case_out"], rec)

        for c_i, ce in enumerate(code_entries, start=1):
            puzzle = ce["puzzle_name"]
            if puzzle not in puzzle_cache:
                puzzle_cache[puzzle] = _load_puzzle_samples(data_dir, puzzle)
            samples = puzzle_cache[puzzle]
            if args.case_limit >= 0:
                samples = samples[: args.case_limit]

            code_text = str(ce.get("code") or "")
            has_code = bool(code_text.strip())
            code_sha256 = _sha256_hex(code_text.encode("utf-8")) if has_code else None
            code_precheck: Optional[Dict[str, Any]] = None
            code_non_runnable_error: Optional[str] = None
            if has_code:
                code_precheck = _precheck_code_once(
                    repo_root=repo_root,
                    runner_script=runner_script,
                    code_text=code_text,
                    memory_limit_mb=args.memory_limit_mb,
                )
                e = str(code_precheck.get("error_type") or "")
                if e in {"compile_error"}:
                    code_non_runnable_error = e

            for s_i, item in enumerate(samples, start=1):
                if s_i in skip_item_indexes.get(puzzle, set()):
                    continue
                pool_case_id = str(item.get("id", f"{puzzle}:{s_i}"))
                pool_case_group = _infer_pool_case_group(item)
                input_size_proxy = _infer_input_size_proxy(item)
                case_split = str(item.get("case_split", args.case_split))
                case_key = f"{model_name}::{ce['code_idx']}::{puzzle}::{pool_case_id}"
                ref_case_key = f"{puzzle}::{pool_case_id}"
                timeout_sec_for_case = float(timeout_map.get(ref_case_key, args.timeout_sec))
                used_case_timeouts_sec.append(timeout_sec_for_case)

                case_repeats: List[Dict[str, Any]] = []
                if has_code:
                    if code_non_runnable_error is not None:
                        template = {
                            "return_code": code_precheck.get("return_code") if code_precheck else None,
                            "error_type": code_non_runnable_error,
                            "stderr_hash": code_precheck.get("stderr_hash") if code_precheck else None,
                            "stderr_excerpt": "",
                            "instruction_measurement_error": f"fast_fail_precheck_{code_non_runnable_error}",
                            "exception": code_precheck.get("exception") if code_precheck else None,
                            "has_solve": bool(code_precheck.get("has_solve")) if code_precheck else False,
                            "raw_child_error_type": code_non_runnable_error,
                        }
                        first = _make_fast_fail_repeat_from(template, 1)
                        case_repeats.append(first)
                        _push_repeat_record(
                            puzzle,
                            {
                                "model_name": model_name,
                                "code_idx": ce["code_idx"],
                                "code_line_no": ce.get("line_no"),
                                "code_sha256": code_sha256,
                                "puzzle_name": puzzle,
                                "pool_case_id": pool_case_id,
                                "pool_case_group": pool_case_group,
                                "case_key": case_key,
                                "timeout_sec": timeout_sec_for_case,
                                **{k: first.get(k) for k in [
                                    "repeat_idx", "wall_time_ms", "cpu_time_ms", "peak_memory_mb", "memory_integral_mb_ms",
                                    "instruction_count", "cycles", "max_rss_kb", "timed_out", "crashed", "return_code",
                                    "error_type", "exec_success", "correct", "judge_status", "output_match", "judge_score",
                                    "stdout_bytes", "stderr_hash", "instruction_measurement_error", "solve_only_measured", "has_solve",
                                ]},
                            },
                        )
                        for rep in range(2, args.repeats + 1):
                            rr = _make_fast_fail_repeat_from(first, rep)
                            case_repeats.append(rr)
                            _push_repeat_record(
                                puzzle,
                                {
                                    "model_name": model_name,
                                    "code_idx": ce["code_idx"],
                                    "code_line_no": ce.get("line_no"),
                                    "code_sha256": code_sha256,
                                    "puzzle_name": puzzle,
                                    "pool_case_id": pool_case_id,
                                    "pool_case_group": pool_case_group,
                                    "case_key": case_key,
                                    "timeout_sec": timeout_sec_for_case,
                                    **{k: rr.get(k) for k in [
                                        "repeat_idx", "wall_time_ms", "cpu_time_ms", "peak_memory_mb", "memory_integral_mb_ms",
                                        "instruction_count", "cycles", "max_rss_kb", "timed_out", "crashed", "return_code",
                                        "error_type", "exec_success", "correct", "judge_status", "output_match", "judge_score",
                                        "stdout_bytes", "stderr_hash", "instruction_measurement_error", "solve_only_measured", "has_solve",
                                    ]},
                                },
                            )
                        # no need to execute per-case for this code anymore
                        status_exec_success, status_timed_out, status_crashed, judge_status, error_type, judge_score = _derive_case_status(case_repeats)
                        perf_source: List[Dict[str, Any]] = []
                        first_stderr = next((r for r in case_repeats if r.get("stderr_hash")), None)
                        first_instr_err = next((r for r in case_repeats if r.get("instruction_measurement_error")), None)
                        primary = case_repeats[0] if case_repeats else {}

                        _push_case_record(
                            puzzle,
                            {
                                "model_name": model_name,
                                "code_idx": ce["code_idx"],
                                "code_line_no": ce.get("line_no"),
                                "code_sha256": code_sha256,
                                "code_chars": len(code_text),
                                "source_extracted_ok": ce.get("source_extracted_ok"),
                                "source_matched": ce.get("source_matched"),
                                "source_dataset_idx": ce.get("source_dataset_idx"),
                                "source_match_key": ce.get("source_match_key"),
                                "source_mode": ce.get("source_mode"),
                                "puzzle_name": puzzle,
                                "pool_case_id": pool_case_id,
                                "pool_case_group": pool_case_group,
                                "input_size_proxy": input_size_proxy,
                                "case_split": case_split,
                                "solver_type": "model_generated",
                                "has_code": has_code,
                                "exec_success": status_exec_success,
                                "timed_out": status_timed_out,
                                "crashed": status_crashed,
                                "return_code": primary.get("return_code"),
                                "error_type": error_type,
                                "stderr_excerpt": primary.get("stderr_excerpt", ""),
                                "stderr_hash": first_stderr.get("stderr_hash") if first_stderr else None,
                                "stdout_bytes": int(primary.get("stdout_bytes") or 0),
                                "correct": False,
                                "judge_status": judge_status,
                                "output_match": False,
                                "judge_score": round(float(judge_score), 6),
                                "validation_mode": args.validation_mode,
                                "timeout_sec": timeout_sec_for_case,
                                "wall_time_ms": _aggregate([r.get("wall_time_ms") for r in perf_source], args.profile_aggregation_rule),
                                "cpu_time_ms": _aggregate([r.get("cpu_time_ms") for r in perf_source], args.profile_aggregation_rule),
                                "peak_memory_mb": _aggregate([r.get("peak_memory_mb") for r in perf_source], args.profile_aggregation_rule),
                                "memory_integral_mb_ms": _aggregate([r.get("memory_integral_mb_ms") for r in perf_source], args.profile_aggregation_rule),
                                "instruction_count": _aggregate([r.get("instruction_count") for r in perf_source], args.profile_aggregation_rule),
                                "cycles": _aggregate([r.get("cycles") for r in perf_source], args.profile_aggregation_rule),
                                "max_rss_kb": _aggregate([r.get("max_rss_kb") for r in perf_source], args.profile_aggregation_rule),
                                "profile_repeat_count": args.repeats,
                                "profile_aggregation_rule": args.profile_aggregation_rule,
                                "warmup_count": args.warmup,
                                "memory_limit_mb": args.memory_limit_mb if args.memory_limit_mb > 0 else None,
                                "case_key": case_key,
                                "ref_case_key": ref_case_key,
                                "perf_measurement_enabled": perf_enabled,
                                "perf_probe_reason": perf_probe_reason,
                                "performance_scope": "solve_only_for_time_and_memory",
                                "instruction_cycle_scope": "solve_only_via_perf_event_open",
                                "instruction_measurement_error": first_instr_err.get("instruction_measurement_error") if first_instr_err else None,
                            },
                        )
                        continue

                    warmup_failed_nonrunnable = False
                    warmup_error_type = None
                    for _ in range(max(0, args.warmup)):
                        warm = _run_one_repeat(
                            repo_root=repo_root,
                            runner_script=runner_script,
                            puzzle=puzzle,
                            code_text=code_text,
                            observation=item.get("observation"),
                            expected_answer=item.get("answer"),
                            repeat_idx=0,
                            timeout_sec=timeout_sec_for_case,
                            sample_interval_sec=args.sample_interval_sec,
                            stderr_excerpt_chars=args.stderr_excerpt_chars,
                            perf_enabled=perf_enabled,
                            memory_limit_mb=args.memory_limit_mb,
                        )
                        if str(warm.get("error_type") or "") in {"compile_error"}:
                            warmup_failed_nonrunnable = True
                            warmup_error_type = str(warm.get("error_type"))
                            break

                    first_real_repeat: Optional[Dict[str, Any]] = None
                    fast_fail_rest = warmup_failed_nonrunnable
                    if warmup_failed_nonrunnable:
                        first_real_repeat = {
                            "repeat_idx": 1,
                            "timed_out": False,
                            "crashed": False,
                            "return_code": None,
                            "error_type": warmup_error_type or "runtime_error",
                            "exec_success": False,
                            "correct": False,
                            "judge_status": "runtime_error",
                            "output_match": False,
                            "judge_score": 0.0,
                            "wall_time_ms": None,
                            "cpu_time_ms": None,
                            "peak_memory_mb": None,
                            "memory_integral_mb_ms": None,
                            "instruction_count": None,
                            "cycles": None,
                            "max_rss_kb": None,
                            "stdout_bytes": 0,
                            "stderr_hash": None,
                            "stderr_excerpt": "",
                            "instruction_measurement_error": "fast_fail_after_warmup_nonrunnable",
                            "exception": None,
                            "has_solve": True,
                            "solve_only_measured": False,
                            "raw_child_error_type": warmup_error_type,
                        }

                    for rep in range(1, args.repeats + 1):
                        if rep == 1 and first_real_repeat is not None:
                            rr = first_real_repeat
                        elif fast_fail_rest and first_real_repeat is not None:
                            rr = _make_fast_fail_repeat_from(first_real_repeat, rep)
                        else:
                            rr = _run_one_repeat(
                                repo_root=repo_root,
                                runner_script=runner_script,
                                puzzle=puzzle,
                                code_text=code_text,
                                observation=item.get("observation"),
                                expected_answer=item.get("answer"),
                                repeat_idx=rep,
                                timeout_sec=timeout_sec_for_case,
                                sample_interval_sec=args.sample_interval_sec,
                                stderr_excerpt_chars=args.stderr_excerpt_chars,
                                perf_enabled=perf_enabled,
                                memory_limit_mb=args.memory_limit_mb,
                            )
                            if rep == 1 and str(rr.get("error_type") or "") in {"compile_error"}:
                                first_real_repeat = rr
                                fast_fail_rest = True
                        case_repeats.append(rr)
                        _push_repeat_record(
                            puzzle,
                            {
                                "model_name": model_name,
                                "code_idx": ce["code_idx"],
                                "code_line_no": ce.get("line_no"),
                                "code_sha256": code_sha256,
                                "puzzle_name": puzzle,
                                "pool_case_id": pool_case_id,
                                "pool_case_group": pool_case_group,
                                "case_key": case_key,
                                "timeout_sec": timeout_sec_for_case,
                                **{k: rr.get(k) for k in [
                                    "repeat_idx", "wall_time_ms", "cpu_time_ms", "peak_memory_mb", "memory_integral_mb_ms",
                                    "instruction_count", "cycles", "max_rss_kb", "timed_out", "crashed", "return_code",
                                    "error_type", "exec_success", "correct", "judge_status", "output_match", "judge_score",
                                    "stdout_bytes", "stderr_hash", "instruction_measurement_error", "solve_only_measured", "has_solve",
                                ]},
                            },
                        )
                else:
                    for rep in range(1, args.repeats + 1):
                        rr = {
                            "repeat_idx": rep,
                            "wall_time_ms": None,
                            "cpu_time_ms": None,
                            "peak_memory_mb": None,
                            "memory_integral_mb_ms": None,
                            "instruction_count": None,
                            "cycles": None,
                            "max_rss_kb": None,
                            "timed_out": False,
                            "crashed": False,
                            "return_code": None,
                            "error_type": "missing_code",
                            "exec_success": False,
                            "correct": False,
                            "judge_status": "runtime_error",
                            "output_match": False,
                            "judge_score": 0.0,
                            "stdout_bytes": 0,
                            "stderr_hash": None,
                            "instruction_measurement_error": "missing_code",
                            "solve_only_measured": False,
                            "has_solve": False,
                        }
                        case_repeats.append(rr)
                        _push_repeat_record(
                            puzzle,
                            {
                                "model_name": model_name,
                                "code_idx": ce["code_idx"],
                                "code_line_no": ce.get("line_no"),
                                "code_sha256": code_sha256,
                                "puzzle_name": puzzle,
                                "pool_case_id": pool_case_id,
                                "pool_case_group": pool_case_group,
                                "case_key": case_key,
                                "timeout_sec": timeout_sec_for_case,
                                **rr,
                            },
                        )

                status_exec_success, status_timed_out, status_crashed, judge_status, error_type, judge_score = _derive_case_status(case_repeats)
                perf_source = [r for r in case_repeats if bool(r.get("exec_success")) and bool(r.get("correct"))]
                if not perf_source:
                    perf_source = [r for r in case_repeats if bool(r.get("exec_success"))]

                first_stderr = next((r for r in case_repeats if r.get("stderr_hash")), None)
                first_instr_err = next((r for r in case_repeats if r.get("instruction_measurement_error")), None)
                primary = case_repeats[0] if case_repeats else {}

                _push_case_record(
                    puzzle,
                    {
                        "model_name": model_name,
                        "code_idx": ce["code_idx"],
                        "code_line_no": ce.get("line_no"),
                        "code_sha256": code_sha256,
                        "code_chars": len(code_text),
                        "source_extracted_ok": ce.get("source_extracted_ok"),
                        "source_matched": ce.get("source_matched"),
                        "source_dataset_idx": ce.get("source_dataset_idx"),
                        "source_match_key": ce.get("source_match_key"),
                        "source_mode": ce.get("source_mode"),
                        "puzzle_name": puzzle,
                        "pool_case_id": pool_case_id,
                        "pool_case_group": pool_case_group,
                        "input_size_proxy": input_size_proxy,
                        "case_split": case_split,
                        "solver_type": "model_generated",
                        "has_code": has_code,
                        "exec_success": status_exec_success,
                        "timed_out": status_timed_out,
                        "crashed": status_crashed,
                        "return_code": primary.get("return_code"),
                        "error_type": error_type,
                        "stderr_excerpt": primary.get("stderr_excerpt", ""),
                        "stderr_hash": first_stderr.get("stderr_hash") if first_stderr else None,
                        "stdout_bytes": int(primary.get("stdout_bytes") or 0),
                        "correct": bool(case_repeats) and all(bool(r.get("correct")) for r in case_repeats),
                        "judge_status": judge_status,
                        "output_match": bool(case_repeats) and all(bool(r.get("output_match")) for r in case_repeats),
                        "judge_score": round(float(judge_score), 6),
                        "validation_mode": args.validation_mode,
                        "timeout_sec": timeout_sec_for_case,
                        "wall_time_ms": _aggregate([r.get("wall_time_ms") for r in perf_source], args.profile_aggregation_rule),
                        "cpu_time_ms": _aggregate([r.get("cpu_time_ms") for r in perf_source], args.profile_aggregation_rule),
                        "peak_memory_mb": _aggregate([r.get("peak_memory_mb") for r in perf_source], args.profile_aggregation_rule),
                        "memory_integral_mb_ms": _aggregate([r.get("memory_integral_mb_ms") for r in perf_source], args.profile_aggregation_rule),
                        "instruction_count": _aggregate([r.get("instruction_count") for r in perf_source], args.profile_aggregation_rule),
                        "cycles": _aggregate([r.get("cycles") for r in perf_source], args.profile_aggregation_rule),
                        "max_rss_kb": _aggregate([r.get("max_rss_kb") for r in perf_source], args.profile_aggregation_rule),
                        "profile_repeat_count": args.repeats,
                        "profile_aggregation_rule": args.profile_aggregation_rule,
                        "warmup_count": args.warmup,
                        "memory_limit_mb": args.memory_limit_mb if args.memory_limit_mb > 0 else None,
                        "case_key": case_key,
                        "ref_case_key": ref_case_key,
                        "perf_measurement_enabled": perf_enabled,
                        "perf_probe_reason": perf_probe_reason,
                        "performance_scope": "solve_only_for_time_and_memory",
                        "instruction_cycle_scope": "solve_only_via_perf_event_open",
                        "instruction_measurement_error": first_instr_err.get("instruction_measurement_error") if first_instr_err else None,
                    },
                )

            print(f"  - model={model_name} code={c_i}/{len(code_entries)} idx={ce['code_idx']} puzzle={puzzle}", flush=True)

        total_case_records = 0
        total_repeat_records = 0
        puzzles_written = sorted(set(case_records_by_puzzle.keys()) | set(repeat_records_by_puzzle.keys()))
        for puzzle_name in puzzles_written:
            art = puzzle_artifacts.get(puzzle_name)
            if art is None:
                puzzle_dir = model_out / puzzle_name
                puzzle_dir.mkdir(parents=True, exist_ok=True)
                case_out = puzzle_dir / "model_code_case_metrics.jsonl"
                repeat_out = puzzle_dir / "model_code_repeat_metrics.jsonl"
                puzzle_summary_out = puzzle_dir / "model_code_eval_summary.json"
            else:
                puzzle_dir = art["puzzle_dir"]
                case_out = art["case_out"]
                repeat_out = art["repeat_out"]
                puzzle_summary_out = art["summary_out"]

            puzzle_case_records = case_records_by_puzzle.get(puzzle_name, [])
            puzzle_repeat_records = repeat_records_by_puzzle.get(puzzle_name, [])
            total_case_records += len(puzzle_case_records)
            total_repeat_records += len(puzzle_repeat_records)

            with case_out.open("w", encoding="utf-8") as f:
                for r in puzzle_case_records:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            with repeat_out.open("w", encoding="utf-8") as f:
                for r in puzzle_repeat_records:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

            puzzle_summary = {
                "generated_at_unix": int(time.time()),
                "model_name": model_name,
                "puzzle_name": puzzle_name,
                "repo_root": str(repo_root),
                "data_dir": str(data_dir),
                "output_dir": str(puzzle_dir),
                "total_case_records": len(puzzle_case_records),
                "total_repeat_records": len(puzzle_repeat_records),
                "repeats_per_case": args.repeats,
                "warmup_per_case": args.warmup,
                "timeout_mode": "per_case_from_config" if timeout_map else "fixed",
                "timeout_sec_default": args.timeout_sec,
                "timeout_config_file": str(timeout_config_path) if timeout_config_path else None,
                "skip_item_indexes_file": str(skip_item_indexes_path) if skip_item_indexes_path else None,
                "memory_limit_mb": args.memory_limit_mb if args.memory_limit_mb > 0 else None,
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
            print(f"[model-eval] wrote {case_out}")
            print(f"[model-eval] wrote {repeat_out}")
            print(f"[model-eval] wrote {puzzle_summary_out}")

        summary = {
            "generated_at_unix": int(time.time()),
            "model_name": model_name,
            "repo_root": str(repo_root),
            "data_dir": str(data_dir),
            "output_dir": str(model_out),
            "total_codes": len(code_entries),
            "total_case_records": total_case_records,
            "total_repeat_records": total_repeat_records,
            "puzzles": puzzles_written,
            "repeats_per_case": args.repeats,
            "warmup_per_case": args.warmup,
            "timeout_mode": "per_case_from_config" if timeout_map else "fixed",
            "timeout_sec_default": args.timeout_sec,
            "timeout_config_file": str(timeout_config_path) if timeout_config_path else None,
            "skip_item_indexes_file": str(skip_item_indexes_path) if skip_item_indexes_path else None,
            "code_idx_json_file": str(code_idx_json_path) if code_idx_json_path else None,
            "code_idxs_cli": sorted(cli_code_idx_whitelist) if cli_code_idx_whitelist is not None else None,
            "timeout_sec_stats": {
                "min": min(used_case_timeouts_sec) if used_case_timeouts_sec else None,
                "max": max(used_case_timeouts_sec) if used_case_timeouts_sec else None,
                "mean": (sum(used_case_timeouts_sec) / len(used_case_timeouts_sec)) if used_case_timeouts_sec else None,
            },
            "memory_limit_mb": args.memory_limit_mb if args.memory_limit_mb > 0 else None,
            "perf_measurement_enabled": perf_enabled,
            "perf_probe_reason": perf_probe_reason,
            "status_counts": {
                "accepted": sum(1 for rows in case_records_by_puzzle.values() for r in rows if r.get("judge_status") == "accepted"),
                "wrong_answer": sum(1 for rows in case_records_by_puzzle.values() for r in rows if r.get("judge_status") == "wrong_answer"),
                "timeout": sum(1 for rows in case_records_by_puzzle.values() for r in rows if r.get("judge_status") == "timeout"),
                "runtime_error": sum(1 for rows in case_records_by_puzzle.values() for r in rows if r.get("judge_status") == "runtime_error"),
            },
        }
        summary_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[model-eval] wrote {summary_out}", flush=True)


if __name__ == "__main__":
    main()
