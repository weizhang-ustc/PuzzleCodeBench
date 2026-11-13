#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import fcntl
import json
import os
import resource
import threading
import time
import traceback
from pathlib import Path
from typing import Any

try:
    import psutil  # type: ignore
except Exception:  # noqa: BLE001
    psutil = None


def _json_safe(value: Any) -> Any:
    """Convert predictions, including tuple-keyed Hashi answers, to JSON-safe values."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, set):
        return [_json_safe(v) for v in sorted(value, key=repr)]
    return value


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


def main() -> None:
    ap = argparse.ArgumentParser(description="Run one model code case in fresh process.")
    ap.add_argument("--code-file", required=True)
    ap.add_argument("--observation-json", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--measure-instructions", action="store_true")
    ap.add_argument("--memory-limit-mb", type=float, default=-1.0)
    ap.add_argument("--precheck-only", action="store_true", help="Only compile code and check callable solve; do not execute solve().")
    args = ap.parse_args()

    code = Path(args.code_file).read_text(encoding="utf-8")
    observation = json.loads(Path(args.observation_json).read_text(encoding="utf-8"))

    if args.memory_limit_mb is not None and float(args.memory_limit_mb) > 0:
        mem_bytes = int(float(args.memory_limit_mb) * 1024 * 1024)
        for kind in (resource.RLIMIT_AS, resource.RLIMIT_DATA):
            try:
                resource.setrlimit(kind, (mem_bytes, mem_bytes))
            except Exception:
                pass

    out: dict[str, Any] = {
        "exec_success": False,
        "has_solve": False,
        "error_type": "runtime_error",
        "exception": None,
        "prediction": None,
        "solve_wall_time_ms": None,
        "solve_cpu_time_ms": None,
        "solve_peak_rss_bytes": None,
        "solve_memory_integral_byte_seconds": None,
        "solve_instruction_count": None,
        "solve_cycles": None,
        "instruction_measurement_error": None,
        "ru_maxrss_kb": None,
        "cpu_time_ms": None,
    }

    t0_cpu_all = time.process_time()
    try:
        g: dict[str, Any] = {}
        try:
            compiled = compile(code, "<model_code>", "exec")
        except Exception:
            out["error_type"] = "compile_error"
            raise

        exec(compiled, g)
        solve_fn = g.get("solve")
        if not callable(solve_fn):
            out["error_type"] = "missing_solve"
            raise AttributeError("solve(observation) is missing")
        out["has_solve"] = True

        if args.precheck_only:
            out["exec_success"] = True
            out["error_type"] = None
            out["prediction"] = None
            out_path = Path(args.out_json)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out["cpu_time_ms"] = round((time.process_time() - t0_cpu_all) * 1000.0, 6)
            out["ru_maxrss_kb"] = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            out_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
            return

        proc = psutil.Process(os.getpid()) if psutil is not None else None
        base_rss = None
        if proc is not None:
            try:
                base_rss = int(proc.memory_info().rss)
            except Exception:
                base_rss = None
        samples: list[tuple[float, int]] = []
        stop = {"v": False}

        def sampler() -> None:
            if proc is None:
                return
            t_ref = time.perf_counter()
            while not stop["v"]:
                try:
                    rss = int(proc.memory_info().rss)
                except Exception:
                    rss = 0
                samples.append((time.perf_counter() - t_ref, rss))
                time.sleep(0.0001)

        th = threading.Thread(target=sampler, daemon=True)
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
        pred = solve_fn(observation)
        out["solve_wall_time_ms"] = round((time.perf_counter() - t0_wall) * 1000.0, 6)
        out["solve_cpu_time_ms"] = round((time.process_time() - t0_cpu) * 1000.0, 6)

        if perf_counter is not None:
            try:
                ins, cyc = perf_counter.stop_and_read()
                out["solve_instruction_count"] = ins
                out["solve_cycles"] = cyc
            except Exception as exc:
                out["instruction_measurement_error"] = f"{type(exc).__name__}: {exc}"
            finally:
                perf_counter.close()

        stop["v"] = True
        if proc is not None:
            th.join(timeout=0.2)

        if samples:
            peak = max(r for _, r in samples)
            if isinstance(base_rss, int):
                peak = max(peak, base_rss)
            out["solve_peak_rss_bytes"] = int(peak)
            mem_integral = 0.0
            for i in range(1, len(samples)):
                dt = samples[i][0] - samples[i - 1][0]
                mem_integral += dt * samples[i - 1][1]
            out["solve_memory_integral_byte_seconds"] = mem_integral

        out["prediction"] = _json_safe(pred)
        out["exec_success"] = True
        out["error_type"] = None

    except Exception as exc:  # noqa: BLE001
        err_text = f"{type(exc).__name__}: {exc}".lower()
        if isinstance(exc, MemoryError) or ("memory" in err_text and "error" in err_text):
            out["error_type"] = "memory_limit"
        out["exception"] = traceback.format_exc(limit=50)

    out["cpu_time_ms"] = round((time.process_time() - t0_cpu_all) * 1000.0, 6)
    out["ru_maxrss_kb"] = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
