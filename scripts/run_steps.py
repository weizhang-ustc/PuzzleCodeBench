#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Set, Tuple


def _normalize_prediction(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text or text == "No Solution":
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


def _json_safe(value: Any) -> Any:
    """Convert standalone CLI output to JSON-safe values."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, set):
        return [_json_safe(v) for v in sorted(value, key=repr)]
    return value


class BenchHooks:
    """Optional semantic counters for solver code.

    Any solve() code can call these to expose reasoning-style behavior:
    - BENCH.guess()
    - BENCH.backtrack()
    - BENCH.enter_decision()
    - BENCH.leave_decision()
    - BENCH.prune()
    """

    def __init__(self) -> None:
        self.guess_count = 0
        self.backtrack_count = 0
        self.prune_count = 0
        self.node_expand_count = 0
        self.decision_depth_current = 0
        self.decision_depth_max = 0

    def guess(self, n: int = 1) -> None:
        self.guess_count += int(n)

    def backtrack(self, n: int = 1) -> None:
        self.backtrack_count += int(n)

    def prune(self, n: int = 1) -> None:
        self.prune_count += int(n)

    def expand_node(self, n: int = 1) -> None:
        self.node_expand_count += int(n)

    def enter_decision(self) -> None:
        self.decision_depth_current += 1
        if self.decision_depth_current > self.decision_depth_max:
            self.decision_depth_max = self.decision_depth_current

    def leave_decision(self) -> None:
        if self.decision_depth_current > 0:
            self.decision_depth_current -= 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "guess_count": self.guess_count,
            "backtrack_count": self.backtrack_count,
            "prune_count": self.prune_count,
            "node_expand_count": self.node_expand_count,
            "decision_depth_max": self.decision_depth_max,
        }


@dataclass
class StepMetrics:
    line_steps: int = 0
    opcode_steps: int = 0
    call_steps: int = 0
    return_steps: int = 0
    unique_lines_executed: int = 0
    max_call_depth: int = 0
    wall_time_sec: float = 0.0

    # Semantic (human-style) counters; accurate when solver uses BENCH hooks.
    guess_count: int = 0
    backtrack_count: int = 0
    prune_count: int = 0
    node_expand_count: int = 0
    decision_depth_max: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_steps": self.line_steps,
            "opcode_steps": self.opcode_steps,
            "call_steps": self.call_steps,
            "return_steps": self.return_steps,
            "unique_lines_executed": self.unique_lines_executed,
            "max_call_depth": self.max_call_depth,
            "wall_time_sec": self.wall_time_sec,
            "guess_count": self.guess_count,
            "backtrack_count": self.backtrack_count,
            "prune_count": self.prune_count,
            "node_expand_count": self.node_expand_count,
            "decision_depth_max": self.decision_depth_max,
        }


class _StepTracer:
    def __init__(
        self,
        *,
        count_opcodes: bool,
        include_filenames: Optional[Sequence[str]] = None,
        include_module_prefixes: Optional[Sequence[str]] = None,
    ) -> None:
        self.count_opcodes = bool(count_opcodes)
        self.include_filenames: Set[str] = set(include_filenames or ("<string>",))
        self.include_module_prefixes = tuple(include_module_prefixes or ("__codex_eval__",))
        self.metrics = StepMetrics()
        self._line_seen: Set[Tuple[str, int]] = set()
        self._current_call_depth = 0

    def _tracked_frame(self, frame: Any) -> bool:
        code = getattr(frame, "f_code", None)
        if code is None:
            return False

        filename = getattr(code, "co_filename", "")
        if filename in self.include_filenames:
            return True

        module_name = frame.f_globals.get("__name__", "")
        return any(module_name.startswith(p) for p in self.include_module_prefixes)

    def tracer(self, frame: Any, event: str, arg: Any) -> Any:
        if not self._tracked_frame(frame):
            return self.tracer

        if self.count_opcodes:
            frame.f_trace_opcodes = True

        if event == "line":
            self.metrics.line_steps += 1
            key = (frame.f_code.co_filename, int(frame.f_lineno))
            self._line_seen.add(key)
            self.metrics.unique_lines_executed = len(self._line_seen)
        elif event == "opcode":
            self.metrics.opcode_steps += 1
        elif event == "call":
            self.metrics.call_steps += 1
            self._current_call_depth += 1
            if self._current_call_depth > self.metrics.max_call_depth:
                self.metrics.max_call_depth = self._current_call_depth
        elif event == "return":
            self.metrics.return_steps += 1
            if self._current_call_depth > 0:
                self._current_call_depth -= 1
        return self.tracer


def _build_bench_namespace() -> Dict[str, Any]:
    bench = BenchHooks()

    # Multiple names to maximize compatibility with arbitrary generated code.
    return {
        "BENCH": bench,
        "__bench__": bench,
        "codex_guess": bench.guess,
        "codex_backtrack": bench.backtrack,
        "codex_prune": bench.prune,
        "codex_expand_node": bench.expand_node,
        "codex_enter_decision": bench.enter_decision,
        "codex_leave_decision": bench.leave_decision,
    }


def run_code_with_steps(
    *,
    code: str,
    observation: Any,
    normalize_prediction: bool = True,
    count_opcodes: bool = False,
) -> Dict[str, Any]:
    hooks = _build_bench_namespace()
    bench = hooks["BENCH"]
    ns: Dict[str, Any] = {"__name__": "__codex_eval__", **hooks}

    try:
        exec(code, ns, ns)
    except Exception:
        return {
            "ok": False,
            "stage": "exec",
            "error": traceback.format_exc(),
        }

    solve_fn = ns.get("solve")
    if not callable(solve_fn):
        return {
            "ok": False,
            "stage": "resolve_solve",
            "error": "No callable solve(observation) found in code.",
        }

    tracer = _StepTracer(count_opcodes=count_opcodes)
    previous_trace = sys.gettrace()

    pred: Any = None
    started = time.perf_counter()
    try:
        sys.settrace(tracer.tracer)
        pred = solve_fn(observation)
    except Exception:
        elapsed = time.perf_counter() - started
        tracer.metrics.wall_time_sec = elapsed
        tracer.metrics.guess_count = bench.guess_count
        tracer.metrics.backtrack_count = bench.backtrack_count
        tracer.metrics.prune_count = bench.prune_count
        tracer.metrics.node_expand_count = bench.node_expand_count
        tracer.metrics.decision_depth_max = bench.decision_depth_max
        sys.settrace(previous_trace)
        return {
            "ok": False,
            "stage": "run_solve",
            "error": traceback.format_exc(),
            "metrics": tracer.metrics.to_dict(),
        }
    finally:
        sys.settrace(previous_trace)

    elapsed = time.perf_counter() - started
    tracer.metrics.wall_time_sec = elapsed
    tracer.metrics.guess_count = bench.guess_count
    tracer.metrics.backtrack_count = bench.backtrack_count
    tracer.metrics.prune_count = bench.prune_count
    tracer.metrics.node_expand_count = bench.node_expand_count
    tracer.metrics.decision_depth_max = bench.decision_depth_max

    if normalize_prediction:
        pred = _normalize_prediction(pred)

    return {
        "ok": True,
        "stage": "done",
        "prediction": pred,
        "metrics": tracer.metrics.to_dict(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one code snippet and report step metrics.")
    parser.add_argument("--code-file", required=True, help="Path to a .py file that defines solve(observation)")
    parser.add_argument("--observation-json", required=True, help="Observation JSON string")
    parser.add_argument("--count-opcodes", action="store_true", help="Also count opcode events")
    args = parser.parse_args()

    code_path = Path(args.code_file)
    code = code_path.read_text(encoding="utf-8")
    observation = json.loads(args.observation_json)

    result = run_code_with_steps(code=code, observation=observation, count_opcodes=args.count_opcodes)
    print(json.dumps(_json_safe(result), ensure_ascii=False))


if __name__ == "__main__":
    main()
