#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from prettytable import PrettyTable
except Exception:
    PrettyTable = None  # type: ignore


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _save_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _save_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _as_bool(v: Any) -> bool:
    return bool(v is True or v == 1)


def _as_pos_float(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        fv = float(v)
        if fv > 0:
            return fv
    return None


def _as_int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and float(v).is_integer():
        return int(v)
    return None


def _avg(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _gmean(vals: list[float]) -> float | None:
    if not vals or any(v <= 0 for v in vals):
        return None
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def _pct(n: int, d: int) -> float:
    return float(n) / float(d) if d > 0 else 0.0


def _solver_key(row: dict[str, Any]) -> str:
    if row.get("code_idx") is not None:
        return f"code_idx::{row.get('code_idx')}"
    if row.get("source_dataset_idx") is not None:
        return f"source_dataset_idx::{row.get('source_dataset_idx')}"
    return str(row.get("code_sha256") or row.get("case_key") or "unknown_solver")


def _load_anchor_case_map(rerun_file: Path) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for row in _load_jsonl(rerun_file):
        idx = _as_int(row.get("idx"))
        if idx is None:
            idx = _as_int(row.get("dataset_idx"))
        if idx is None:
            continue
        run_oracle = row.get("run_oracle") if isinstance(row.get("run_oracle"), dict) else {}
        cmp_oracle = row.get("comparison_oracle") if isinstance(row.get("comparison_oracle"), dict) else {}
        cmp_e2e = row.get("comparison_e2e") if isinstance(row.get("comparison_e2e"), dict) else {}
        obs_cmp = row.get("observation_comparison") if isinstance(row.get("observation_comparison"), dict) else {}
        out[idx] = {
            "anchor_idx": idx,
            "anchor_puzzle_name": row.get("puzzle_type"),
            "anchor_observation_correct": _as_bool(obs_cmp.get("is_correct")),
            "anchor_correct_oracle": _as_bool(cmp_oracle.get("is_correct")),
            "anchor_correct_e2e": _as_bool(cmp_e2e.get("is_correct")),
            "anchor_exec_oracle": _as_bool(run_oracle.get("ok")),
        }
    return out


def _load_extract_summary(all_results_jsonl: Path, model_name: str) -> dict[str, Any]:
    for row in _load_jsonl(all_results_jsonl):
        if str(row.get("model")) != model_name:
            continue
        ex = row.get("extract") if isinstance(row.get("extract"), dict) else {}
        rr = row.get("rerun") if isinstance(row.get("rerun"), dict) else {}
        ot = row.get("output_tokens") if isinstance(row.get("output_tokens"), dict) else {}
        avg_tokens = None
        if isinstance(ot.get("sum"), (int, float)) and isinstance(ot.get("count"), (int, float)) and float(ot.get("count")) > 0:
            avg_tokens = float(ot["sum"]) / float(ot["count"])
        return {
            "extract_total": ex.get("total"),
            "extract_ok": ex.get("ok"),
            "anchor_observation_correct_count": rr.get("observation_correct"),
            "anchor_answer_correct_oracle_count": rr.get("answer_correct_oracle"),
            "anchor_answer_correct_e2e_count": rr.get("answer_correct_e2e"),
            "anchor_exec_success_oracle_count": rr.get("code_execution_success_oracle"),
            "anchor_exec_success_e2e_count": rr.get("code_execution_success_e2e"),
            "output_tokens_sum": ot.get("sum"),
            "output_tokens_count": ot.get("count"),
            "output_tokens_avg": avg_tokens,
        }
    return {}


def _case_is_valid(cand: dict[str, Any] | None, ref: dict[str, Any]) -> bool:
    return (
        cand is not None
        and _as_bool(cand.get("exec_success"))
        and _as_bool(cand.get("correct"))
        and not _as_bool(cand.get("timed_out"))
        and not _as_bool(cand.get("crashed"))
        and _as_bool(ref.get("exec_success"))
        and _as_bool(ref.get("correct"))
    )


def _ratio_score(cand: dict[str, Any] | None, ref: dict[str, Any], cand_key: str, ref_key: str) -> float:
    if not _case_is_valid(cand, ref):
        return 0.0
    rv = _as_pos_float(ref.get(ref_key))
    cv = _as_pos_float(cand.get(cand_key) if cand is not None else None)
    if rv is None or cv is None:
        return 0.0
    return min(1.0, rv / cv)


def _faster_score(cand: dict[str, Any] | None, ref: dict[str, Any], cand_key: str, ref_key: str) -> float:
    if not _case_is_valid(cand, ref):
        return 0.0
    rv = _as_pos_float(ref.get(ref_key))
    cv = _as_pos_float(cand.get(cand_key) if cand is not None else None)
    if rv is None or cv is None:
        return 0.0
    return 1.0 if cv < rv else 0.0


def _compute_model_metrics(
    model_name: str,
    model_rows: list[dict[str, Any]],
    ref_rows: list[dict[str, Any]],
    anchor_case_map: dict[int, dict[str, Any]],
    extract_summary: dict[str, Any],
) -> dict[str, Any]:
    ref_by_puzzle_case: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in ref_rows:
        pz = str(r.get("puzzle_name") or "")
        cid = str(r.get("pool_case_id") or "")
        if pz and cid:
            ref_by_puzzle_case[pz][cid] = r

    by_puzzle_solver: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for r in model_rows:
        pz = str(r.get("puzzle_name") or "")
        if not pz:
            continue
        by_puzzle_solver[pz][_solver_key(r)].append(r)

    solver_rows: list[dict[str, Any]] = []
    puzzle_agg: dict[str, dict[str, Any]] = {}

    for puzzle, solver_map in sorted(by_puzzle_solver.items()):
        ref_cases = ref_by_puzzle_case.get(puzzle, {})
        if not ref_cases:
            continue
        puzzle_solver_metrics: list[dict[str, Any]] = []

        for sk, rows in sorted(solver_map.items()):
            cand_by_case = {str(r.get("pool_case_id")): r for r in rows}
            pairs: list[tuple[dict[str, Any] | None, dict[str, Any]]] = []
            for cid, ref in ref_cases.items():
                pairs.append((cand_by_case.get(cid), ref))

            n = len(pairs)
            correct_count = sum(1 for c, _ in pairs if c is not None and _as_bool(c.get("correct")))
            exec_count = sum(1 for c, _ in pairs if c is not None and _as_bool(c.get("exec_success")))
            timeout_count = sum(1 for c, _ in pairs if c is not None and _as_bool(c.get("timed_out")))
            crash_count = sum(1 for c, _ in pairs if c is not None and _as_bool(c.get("crashed")))

            et_time_vals = [_ratio_score(c, r, "wall_time_ms", "wall_time_ms") for c, r in pairs]
            et_instr_vals = [_ratio_score(c, r, "instruction_count", "instruction_count") for c, r in pairs]
            er_time_vals = [_faster_score(c, r, "wall_time_ms", "wall_time_ms") for c, r in pairs]
            er_instr_vals = [_faster_score(c, r, "instruction_count", "instruction_count") for c, r in pairs]
            mp_vals = [_ratio_score(c, r, "peak_memory_mb", "peak_memory_mb") for c, r in pairs]

            speedup_instr_vals: list[float] = []
            speedup_time_vals: list[float] = []
            for cand, ref in pairs:
                if not _case_is_valid(cand, ref):
                    continue
                ri = _as_pos_float(ref.get("instruction_count"))
                ci = _as_pos_float(cand.get("instruction_count") if cand is not None else None)
                if ri is not None and ci is not None:
                    speedup_instr_vals.append(ri / ci)
                rt = _as_pos_float(ref.get("wall_time_ms"))
                ct = _as_pos_float(cand.get("wall_time_ms") if cand is not None else None)
                if rt is not None and ct is not None:
                    speedup_time_vals.append(rt / ct)

            solver_code_idx = rows[0].get("code_idx")
            solver_source_idx = rows[0].get("source_dataset_idx")
            solver_anchor_idx = _as_int(solver_source_idx)
            if solver_anchor_idx is None:
                solver_anchor_idx = _as_int(solver_code_idx)
            anchor = anchor_case_map.get(solver_anchor_idx) if solver_anchor_idx is not None else None
            anchor_correct_oracle = _as_bool(anchor.get("anchor_correct_oracle")) if anchor is not None else False
            full_transfer = (n > 0 and correct_count == n)
            good_solver = full_transfer and anchor_correct_oracle

            sm = {
                "model_name": model_name,
                "puzzle_name": puzzle,
                "solver_key": sk,
                "solver_code_idx": solver_code_idx,
                "solver_source_dataset_idx": solver_source_idx,
                "solver_anchor_idx": solver_anchor_idx,
                "num_pool_cases": n,
                "transfer_correct_count": correct_count,
                "transfer_exec_count": exec_count,
                "transfer_timeout_count": timeout_count,
                "transfer_crash_count": crash_count,
                "transfer_correct_rate": _pct(correct_count, n),
                "transfer_exec_rate": _pct(exec_count, n),
                "transfer_et_time": _avg(et_time_vals),
                "transfer_et_instr": _avg(et_instr_vals),
                "transfer_er_time": _avg(er_time_vals),
                "transfer_er_instr": _avg(er_instr_vals),
                "transfer_mp": _avg(mp_vals),
                "transfer_et": _avg(et_time_vals),
                "transfer_efficient_rate_instr": _avg(er_instr_vals),
                "transfer_instruction_speedup_gmean": _gmean(speedup_instr_vals),
                "transfer_time_speedup_gmean": _gmean(speedup_time_vals),
                "anchor_found": anchor is not None,
                "anchor_observation_correct": (_as_bool(anchor.get("anchor_observation_correct")) if anchor is not None else False),
                "anchor_correct_oracle": anchor_correct_oracle,
                "anchor_correct_e2e": (_as_bool(anchor.get("anchor_correct_e2e")) if anchor is not None else False),
                "anchor_exec_oracle": (_as_bool(anchor.get("anchor_exec_oracle")) if anchor is not None else False),
                "solver_is_full_transfer": full_transfer,
                "solver_is_good_anchor_plus_transfer": good_solver,
            }
            puzzle_solver_metrics.append(sm)
            solver_rows.append(sm)

        if not puzzle_solver_metrics:
            continue

        puzzle_agg[puzzle] = {
            "num_solvers": len(puzzle_solver_metrics),
            "transfer_correct_rate": _avg([float(x["transfer_correct_rate"]) for x in puzzle_solver_metrics]),
            "transfer_exec_rate": _avg([float(x["transfer_exec_rate"]) for x in puzzle_solver_metrics]),
            "transfer_et_time": _avg([float(x["transfer_et_time"]) for x in puzzle_solver_metrics]),
            "transfer_et_instr": _avg([float(x["transfer_et_instr"]) for x in puzzle_solver_metrics]),
            "transfer_er_time": _avg([float(x["transfer_er_time"]) for x in puzzle_solver_metrics]),
            "transfer_er_instr": _avg([float(x["transfer_er_instr"]) for x in puzzle_solver_metrics]),
            "transfer_mp": _avg([float(x["transfer_mp"]) for x in puzzle_solver_metrics]),
            "good_solver_count": sum(1 for x in puzzle_solver_metrics if _as_bool(x.get("solver_is_good_anchor_plus_transfer"))),
            "full_transfer_solver_count": sum(1 for x in puzzle_solver_metrics if _as_bool(x.get("solver_is_full_transfer"))),
        }

    pvals = list(puzzle_agg.values())
    benchmark_metrics: dict[str, Any] = {
        "num_puzzles": len(pvals),
        "transfer_correct_rate": _avg([float(v["transfer_correct_rate"]) for v in pvals]) if pvals else 0.0,
        "transfer_exec_rate": _avg([float(v["transfer_exec_rate"]) for v in pvals]) if pvals else 0.0,
        "transfer_et_time": _avg([float(v["transfer_et_time"]) for v in pvals]) if pvals else 0.0,
        "transfer_et_instr": _avg([float(v["transfer_et_instr"]) for v in pvals]) if pvals else 0.0,
        "transfer_er_time": _avg([float(v["transfer_er_time"]) for v in pvals]) if pvals else 0.0,
        "transfer_er_instr": _avg([float(v["transfer_er_instr"]) for v in pvals]) if pvals else 0.0,
        "transfer_mp": _avg([float(v["transfer_mp"]) for v in pvals]) if pvals else 0.0,
        "transfer_et": _avg([float(v["transfer_et_time"]) for v in pvals]) if pvals else 0.0,
        "transfer_efficient_rate_instr": _avg([float(v["transfer_er_instr"]) for v in pvals]) if pvals else 0.0,
    }

    total_solvers = len(solver_rows)
    good_solver_rows = [r for r in solver_rows if _as_bool(r.get("solver_is_good_anchor_plus_transfer"))]
    full_transfer_rows = [r for r in solver_rows if _as_bool(r.get("solver_is_full_transfer"))]
    good_puzzles = sorted({str(r.get("puzzle_name")) for r in good_solver_rows})

    anchor_found_rows = [r for r in solver_rows if _as_bool(r.get("anchor_found"))]
    model_anchor_metrics = {
        "anchor_found_solver_count": len(anchor_found_rows),
        "anchor_observation_acc": _avg([1.0 if _as_bool(r.get("anchor_observation_correct")) else 0.0 for r in anchor_found_rows]) if anchor_found_rows else 0.0,
        "anchor_correct_rate_oracle": _avg([1.0 if _as_bool(r.get("anchor_correct_oracle")) else 0.0 for r in anchor_found_rows]) if anchor_found_rows else 0.0,
        "anchor_correct_rate_e2e": _avg([1.0 if _as_bool(r.get("anchor_correct_e2e")) else 0.0 for r in anchor_found_rows]) if anchor_found_rows else 0.0,
        "anchor_exec_rate_oracle": _avg([1.0 if _as_bool(r.get("anchor_exec_oracle")) else 0.0 for r in anchor_found_rows]) if anchor_found_rows else 0.0,
    }

    return {
        "model_name": model_name,
        "num_total_solvers": total_solvers,
        "num_total_puzzles": len(puzzle_agg),
        "benchmark_metrics": benchmark_metrics,
        "model_anchor_metrics": model_anchor_metrics,
        "good_solver_count_anchor_plus_transfer": len(good_solver_rows),
        "good_solver_rate_over_190": _pct(len(good_solver_rows), 190),
        "full_transfer_solver_count": len(full_transfer_rows),
        "full_transfer_solver_rate": _pct(len(full_transfer_rows), total_solvers),
        "model_mastered_puzzle_count": len(good_puzzles),
        "model_mastered_puzzles": good_puzzles,
        "model_mastered_puzzle_rate_over_30": _pct(len(good_puzzles), 30),
        "extract_and_rerun_summary": extract_summary,
        "notes": {
            "good_solver_definition": "anchor_correct_oracle==1 and transfer_correct_count==num_pool_cases",
            "transfer_pool_cases_per_solver_target": 20,
        },
    }


def _fpct(v: Any) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{100.0 * float(v):.1f}%"
    return "-"


def _mastered_fmt(count: Any, total: int) -> str:
    if isinstance(count, (int, float)) and not isinstance(count, bool) and total > 0:
        c = int(count)
        return f"{c}/{total} ({100.0 * c / total:.1f}%)"
    return "-"


def _render_table(rows: list[dict[str, Any]], mastered_total: int) -> str:
    rows = sorted(rows, key=lambda r: str(r.get("model_name", "")))
    headers = [
        "Model",
        "Obs. Acc.",
        "E2E Acc.",
        "Oracle-Obs. Acc.",
        "Instr. Eff.",
        "Faster Rate",
        "Verified@190",
        "Mastered@30",
    ]
    data_rows: list[list[str]] = []
    for r in rows:
        anchor = r.get("model_anchor_metrics", {}) if isinstance(r.get("model_anchor_metrics"), dict) else {}
        bench = r.get("benchmark_metrics", {}) if isinstance(r.get("benchmark_metrics"), dict) else {}
        data_rows.append(
            [
                str(r.get("model_name", "-")),
                _fpct(anchor.get("anchor_observation_acc")),
                _fpct(anchor.get("anchor_correct_rate_e2e")),
                _fpct(anchor.get("anchor_correct_rate_oracle")),
                _fpct(bench.get("transfer_et_instr")),
                _fpct(bench.get("transfer_er_instr")),
                _fpct(r.get("good_solver_rate_over_190")),
                _mastered_fmt(r.get("model_mastered_puzzle_count"), mastered_total),
            ]
        )

    if PrettyTable is not None:
        t = PrettyTable()
        t.field_names = headers
        t.align = "l"
        for rr in data_rows:
            t.add_row(rr)
        return str(t)

    lines = ["\t".join(headers)]
    lines.extend("\t".join(rr) for rr in data_rows)
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Compute final metrics by merging anchor-level and transfer-level results.")
    ap.add_argument("--root", default=".", help="PuzzleCodeBench repo root")
    ap.add_argument("--anchor-dir", default="results/anchor-level")
    ap.add_argument("--transfer-dir", default="results/transfer-level")
    ap.add_argument("--out-dir", default="results/final")
    ap.add_argument("--mastered-total", type=int, default=30)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    anchor_dir = (root / args.anchor_dir).resolve()
    transfer_dir = (root / args.transfer_dir).resolve()
    out_dir = (root / args.out_dir).resolve()

    ref_file = transfer_dir / "ref.jsonl"
    if not ref_file.exists():
        raise SystemExit(f"Missing ref file: {ref_file}")
    ref_rows = _load_jsonl(ref_file)

    all_results_file = anchor_dir / "all_results.jsonl"
    model_files = sorted(
        p for p in transfer_dir.glob("*.jsonl") if p.name != "ref.jsonl"
    )
    final_rows: list[dict[str, Any]] = []

    for mf in model_files:
        model_name = mf.stem
        model_rows = _load_jsonl(mf)
        rerun_file = anchor_dir / f"results-{model_name}.rerun.jsonl"
        anchor_case_map = _load_anchor_case_map(rerun_file)
        extract_summary = _load_extract_summary(all_results_file, model_name)
        final_rows.append(
            _compute_model_metrics(
                model_name=model_name,
                model_rows=model_rows,
                ref_rows=ref_rows,
                anchor_case_map=anchor_case_map,
                extract_summary=extract_summary,
            )
        )
        print(f"[done] {model_name}")

    _save_jsonl(out_dir / "model_final_metrics.jsonl", final_rows)
    _save_json(out_dir / "model_final_metrics.json", {"num_models": len(final_rows), "models": final_rows})

    table_txt = _render_table(final_rows, args.mastered_total)
    (out_dir / "final_metrics_table.txt").write_text(table_txt + "\n", encoding="utf-8")
    print(table_txt)
    print(f"[done] wrote: {out_dir}")


if __name__ == "__main__":
    main()
