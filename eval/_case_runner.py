#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import fcntl
import importlib
import json
import re
import os
import resource
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

try:
    import psutil  # type: ignore
except Exception:  # noqa: BLE001
    psutil = None


PERF_TYPE_HARDWARE = 0
PERF_COUNT_HW_CPU_CYCLES = 0
PERF_COUNT_HW_INSTRUCTIONS = 1
PERF_EVENT_IOC_ENABLE = 0x2400
PERF_EVENT_IOC_DISABLE = 0x2401
PERF_EVENT_IOC_RESET = 0x2403


class _PerfEventAttr(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("size", ctypes.c_uint32),
        ("config", ctypes.c_uint64),
        ("sample_period", ctypes.c_uint64),
        ("sample_type", ctypes.c_uint64),
        ("read_format", ctypes.c_uint64),
        ("flags", ctypes.c_uint64),
        ("wakeup_events", ctypes.c_uint32),
        ("bp_type", ctypes.c_uint32),
        ("config1", ctypes.c_uint64),
        ("config2", ctypes.c_uint64),
        ("branch_sample_type", ctypes.c_uint64),
        ("sample_regs_user", ctypes.c_uint64),
        ("sample_stack_user", ctypes.c_uint32),
        ("clockid", ctypes.c_int32),
        ("sample_regs_intr", ctypes.c_uint64),
        ("aux_watermark", ctypes.c_uint32),
        ("sample_max_stack", ctypes.c_uint16),
        ("__reserved_2", ctypes.c_uint16),
        ("aux_sample_size", ctypes.c_uint32),
        ("__reserved_3", ctypes.c_uint32),
        ("sig_data", ctypes.c_uint64),
    ]


def _nr_perf_event_open() -> int:
    machine = os.uname().machine
    if machine in {"x86_64", "amd64"}:
        return 298
    if machine in {"aarch64", "arm64"}:
        return 241
    # Common fallback; may be wrong on some architectures.
    return 298


def _open_perf_event(attr: _PerfEventAttr, pid: int, cpu: int, group_fd: int, flags: int) -> int:
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    libc.syscall.restype = ctypes.c_long
    ret = libc.syscall(
        _nr_perf_event_open(),
        ctypes.byref(attr),
        ctypes.c_int(pid),
        ctypes.c_int(cpu),
        ctypes.c_int(group_fd),
        ctypes.c_ulong(flags),
    )
    if ret < 0:
        err = ctypes.get_errno()
        raise OSError(err, f"perf_event_open failed: errno={err}")
    return int(ret)


class _SolvePerfCounter:
    def __init__(self) -> None:
        self.fd_instr: int | None = None
        self.fd_cycles: int | None = None

    def _make_attr(self, event_config: int, disabled: bool) -> _PerfEventAttr:
        attr = _PerfEventAttr()
        attr.type = PERF_TYPE_HARDWARE
        attr.size = ctypes.sizeof(_PerfEventAttr)
        attr.config = ctypes.c_uint64(event_config).value
        attr.sample_period = 0
        attr.sample_type = 0
        attr.read_format = 0
        # disabled(bit0), exclude_kernel(bit5), exclude_hv(bit6) => user-space only
        flags = 0
        if disabled:
            flags |= 1 << 0
        flags |= 1 << 5
        flags |= 1 << 6
        attr.flags = ctypes.c_uint64(flags).value
        return attr

    def start(self) -> None:
        attr_instr = self._make_attr(PERF_COUNT_HW_INSTRUCTIONS, disabled=True)
        self.fd_instr = _open_perf_event(attr_instr, pid=0, cpu=-1, group_fd=-1, flags=0)

        attr_cycles = self._make_attr(PERF_COUNT_HW_CPU_CYCLES, disabled=False)
        self.fd_cycles = _open_perf_event(attr_cycles, pid=0, cpu=-1, group_fd=self.fd_instr, flags=0)

        fcntl.ioctl(self.fd_instr, PERF_EVENT_IOC_RESET, 0)
        fcntl.ioctl(self.fd_cycles, PERF_EVENT_IOC_RESET, 0)
        fcntl.ioctl(self.fd_instr, PERF_EVENT_IOC_ENABLE, 0)

    def stop_and_read(self) -> tuple[int | None, int | None]:
        instr = None
        cycles = None
        if self.fd_instr is not None:
            try:
                fcntl.ioctl(self.fd_instr, PERF_EVENT_IOC_DISABLE, 0)
            except Exception:
                pass
        if self.fd_instr is not None:
            try:
                raw = os.read(self.fd_instr, 8)
                if len(raw) == 8:
                    instr = int.from_bytes(raw, byteorder="little", signed=False)
            except Exception:
                instr = None
        if self.fd_cycles is not None:
            try:
                raw = os.read(self.fd_cycles, 8)
                if len(raw) == 8:
                    cycles = int.from_bytes(raw, byteorder="little", signed=False)
            except Exception:
                cycles = None
        return instr, cycles

    def close(self) -> None:
        for fd in (self.fd_cycles, self.fd_instr):
            if fd is None:
                continue
            try:
                os.close(fd)
            except Exception:
                pass
        self.fd_instr = None
        self.fd_cycles = None


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


def _answers_match(puzzle: str, answer: Any, expected_answer: Any) -> bool:
    tester = _load_answer_tester_from_construction(puzzle)
    if tester is not None:
        try:
            return bool(tester(answer, expected_answer))
        except Exception:
            pass

    if puzzle == "hashi":
        na = _normalize_hashi_answer(answer)
        ne = _normalize_hashi_answer(expected_answer)
        if na is not None and ne is not None:
            return na == ne
    return _to_comparable(answer) == _to_comparable(expected_answer)


def _import_construction_module(module_name: str):
    try:
        return importlib.import_module(module_name), None
    except Exception as exc:
        msg = str(exc)
        if "No module named 'matplotlib'" not in msg:
            return None, exc

    import types

    fake_matplotlib = types.ModuleType("matplotlib")
    fake_pyplot = types.ModuleType("matplotlib.pyplot")
    fake_patches = types.ModuleType("matplotlib.patches")
    setattr(fake_matplotlib, "pyplot", fake_pyplot)
    setattr(fake_matplotlib, "patches", fake_patches)

    old_entries = {k: sys.modules.get(k) for k in ("matplotlib", "matplotlib.pyplot", "matplotlib.patches")}
    sys.modules["matplotlib"] = fake_matplotlib
    sys.modules["matplotlib.pyplot"] = fake_pyplot
    sys.modules["matplotlib.patches"] = fake_patches
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
    module_name = f"construction.{puzzle}"
    module, _ = _import_construction_module(module_name)
    if module is None:
        return None
    tester = getattr(module, "test_answer", None)
    return tester if callable(tester) else None


def main() -> None:
    ap = argparse.ArgumentParser(description="Run one solver case in a fresh process.")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--puzzle", required=True)
    ap.add_argument("--case-json", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--measure-instructions", action="store_true")
    ap.add_argument("--memory-limit-mb", type=float, default=-1.0)
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    case_json = Path(args.case_json).resolve()
    out_json = Path(args.out_json).resolve()

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    payload = json.loads(case_json.read_text(encoding="utf-8"))
    observation = payload.get("observation")
    expected_answer = payload.get("expected_answer")

    # Apply memory limit for the whole worker process when requested.
    if args.memory_limit_mb is not None and float(args.memory_limit_mb) > 0:
        mem_bytes = int(float(args.memory_limit_mb) * 1024 * 1024)
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except Exception:
            pass
        try:
            resource.setrlimit(resource.RLIMIT_DATA, (mem_bytes, mem_bytes))
        except Exception:
            pass
        try:
            soft_stack, hard_stack = resource.getrlimit(resource.RLIMIT_STACK)
            stack_cap = min(mem_bytes, hard_stack if hard_stack > 0 else mem_bytes)
            resource.setrlimit(resource.RLIMIT_STACK, (stack_cap, stack_cap))
        except Exception:
            pass

    out = {
        "exec_success": False,
        "correct": False,
        "output_match": False,
        "judge_status": "runtime_error",
        "judge_score": 0.0,
        "error_type": "runtime_error",
        "exception": None,
        "cpu_time_ms": None,
        "ru_maxrss_kb": None,
        "solve_wall_time_ms": None,
        "solve_cpu_time_ms": None,
        "solve_peak_rss_bytes": None,
        "solve_memory_integral_byte_seconds": None,
        "solve_instruction_count": None,
        "solve_cycles": None,
        "instruction_measurement_error": None,
    }

    try:
        t0_cpu_all = time.process_time()
        solver_mod = importlib.import_module(f"solver.{args.puzzle}")
        if not hasattr(solver_mod, "solve"):
            raise AttributeError(f"solver.{args.puzzle} missing solve(observation)")

        proc = psutil.Process(os.getpid()) if psutil is not None else None
        base_rss = None
        if proc is not None:
            try:
                base_rss = int(proc.memory_info().rss)
            except Exception:
                base_rss = None

        samples: list[tuple[float, int]] = []
        stop_flag = {"stop": False}

        def _sampler() -> None:
            if proc is None:
                return
            t_ref = time.perf_counter()
            while not stop_flag["stop"]:
                try:
                    rss = int(proc.memory_info().rss)
                except Exception:
                    rss = 0
                samples.append((time.perf_counter() - t_ref, rss))
                time.sleep(0.0005)

        th = threading.Thread(target=_sampler, daemon=True)
        if proc is not None:
            th.start()

        perf_counter = None
        if args.measure_instructions:
            try:
                perf_counter = _SolvePerfCounter()
                perf_counter.start()
            except Exception as exc:
                out["instruction_measurement_error"] = f"{type(exc).__name__}: {exc}"
                perf_counter = None

        t0_wall = time.perf_counter()
        t0_cpu = time.process_time()
        answer = solver_mod.solve(observation)
        solve_wall_time_ms = round((time.perf_counter() - t0_wall) * 1000.0, 6)
        solve_cpu_time_ms = round((time.process_time() - t0_cpu) * 1000.0, 6)

        solve_instruction_count = None
        solve_cycles = None
        if perf_counter is not None:
            try:
                solve_instruction_count, solve_cycles = perf_counter.stop_and_read()
            except Exception as exc:
                out["instruction_measurement_error"] = f"{type(exc).__name__}: {exc}"
            finally:
                perf_counter.close()

        stop_flag["stop"] = True
        if proc is not None:
            th.join(timeout=0.2)

        solve_peak_rss_bytes = None
        solve_memory_integral_byte_seconds = None
        if samples:
            peak = max(rss for _, rss in samples)
            if base_rss is not None:
                peak = max(peak, base_rss)
            solve_peak_rss_bytes = int(peak)

            mem_integral = 0.0
            for i in range(1, len(samples)):
                dt = samples[i][0] - samples[i - 1][0]
                mem_integral += dt * samples[i - 1][1]
            solve_memory_integral_byte_seconds = mem_integral

        output_match = _answers_match(args.puzzle, answer, expected_answer)
        out.update(
            {
                "exec_success": True,
                "correct": bool(output_match),
                "output_match": bool(output_match),
                "judge_status": "accepted" if output_match else "wrong_answer",
                "judge_score": 1.0 if output_match else 0.0,
                "error_type": None if output_match else "wrong_answer",
                "cpu_time_ms": round((time.process_time() - t0_cpu_all) * 1000.0, 6),
                "ru_maxrss_kb": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
                "solve_wall_time_ms": solve_wall_time_ms,
                "solve_cpu_time_ms": solve_cpu_time_ms,
                "solve_peak_rss_bytes": solve_peak_rss_bytes,
                "solve_memory_integral_byte_seconds": solve_memory_integral_byte_seconds,
                "solve_instruction_count": solve_instruction_count,
                "solve_cycles": solve_cycles,
            }
        )
    except Exception as exc:
        cpu_ms = None
        try:
            cpu_ms = round((time.process_time() - t0_cpu_all) * 1000.0, 6)  # type: ignore[name-defined]
        except Exception:
            cpu_ms = None
        err_text = f"{type(exc).__name__}: {exc}".lower()
        is_mem_limit = isinstance(exc, MemoryError) or ("memory" in err_text and "error" in err_text)
        out.update(
            {
                "exec_success": False,
                "correct": False,
                "output_match": False,
                "judge_status": "runtime_error",
                "judge_score": 0.0,
                "error_type": "memory_limit" if is_mem_limit else "runtime_error",
                "exception": traceback.format_exc(limit=50),
                "cpu_time_ms": cpu_ms,
                "ru_maxrss_kb": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            }
        )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
