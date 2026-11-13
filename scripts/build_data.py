from __future__ import annotations

import argparse
import copy
import importlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INIT_DIR = ROOT / "data" / "init"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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
        for row in rows:
            f.write(json.dumps(_to_json_safe(row), ensure_ascii=False) + "\n")


def _to_json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[Any, Any] = {}
        for k, v in obj.items():
            if isinstance(k, tuple):
                key = "(" + ",".join(str(x) for x in k) + ")"
            else:
                key = k
            out[key] = _to_json_safe(v)
        return out
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [_to_json_safe(v) for v in obj]
    return obj


def _parse_maybe_number(token: str) -> Any:
    token = token.strip()
    if token == "":
        return token
    try:
        num = float(token)
    except ValueError:
        return token
    if num.is_integer():
        return int(num)
    return num


def _decode_coordinate_key(key: Any) -> Any:
    if not isinstance(key, str):
        return key
    t = key.strip()
    if t.startswith("(") and t.endswith(")"):
        t = t[1:-1]
    if "," not in t:
        return key
    parts = t.split(",")
    if len(parts) != 2:
        return key
    vals = [_parse_maybe_number(x) for x in parts]
    if not all(isinstance(v, (int, float)) for v in vals):
        return key
    return (vals[0], vals[1])


def _decode_json_keys(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out[_decode_coordinate_key(k)] = _decode_json_keys(v)
        return out
    if isinstance(obj, list):
        return [_decode_json_keys(v) for v in obj]
    return obj


def _prepare_item(item: dict[str, Any]) -> dict[str, Any]:
    prepared = _decode_json_keys(copy.deepcopy(item))
    if "column/row" not in prepared:
        row = prepared.get("row")
        col = prepared.get("column")
        if isinstance(row, int) and isinstance(col, int) and row == col:
            prepared["column/row"] = row
    return prepared


def _solve_one(item: dict[str, Any]) -> dict[str, Any]:
    puzzle = item.get("puzzle")
    if not isinstance(puzzle, str) or not puzzle:
        raise ValueError("Every row must include a non-empty 'puzzle' field")

    construction = importlib.import_module(f"construction.{puzzle}")
    solver = importlib.import_module(f"solver.{puzzle}")

    if not hasattr(construction, "get_observation"):
        raise AttributeError(f"construction.{puzzle} missing get_observation")
    if not hasattr(solver, "solve"):
        raise AttributeError(f"solver.{puzzle} missing solve")

    prepared = _prepare_item(item)
    observation = construction.get_observation(prepared)
    answer = solver.solve(observation)

    out = dict(item)
    out["observation"] = observation
    out["answer"] = answer

    if "puzzle" in out:
        ordered = {"puzzle": out["puzzle"]}
        for k, v in out.items():
            if k != "puzzle":
                ordered[k] = v
        out = ordered

    return out


def _solve_file(input_path: Path, output_path: Path) -> int:
    rows = _load_jsonl(input_path)
    solved = [_solve_one(row) for row in rows]
    _save_jsonl(output_path, solved)
    return len(solved)


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve *_init.jsonl into anchor/transfer jsonl.")
    parser.add_argument("--init-dir", type=Path, default=DEFAULT_INIT_DIR)
    parser.add_argument("--anchor-init", default="anchor_init.jsonl")
    parser.add_argument("--transfer-init", default="transfer_init.jsonl")
    parser.add_argument("--anchor-out", default="anchor.jsonl")
    parser.add_argument("--transfer-out", default="transfer.jsonl")
    args = parser.parse_args()

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    anchor_in = args.init_dir / args.anchor_init
    transfer_in = args.init_dir / args.transfer_init
    anchor_out = args.init_dir / args.anchor_out
    transfer_out = args.init_dir / args.transfer_out

    n_anchor = _solve_file(anchor_in, anchor_out)
    n_transfer = _solve_file(transfer_in, transfer_out)

    print(f"anchor solved: {n_anchor} -> {anchor_out}")
    print(f"transfer solved: {n_transfer} -> {transfer_out}")


if __name__ == "__main__":
    main()
