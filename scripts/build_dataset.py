from __future__ import annotations

import argparse
import importlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INIT_DIR = ROOT / "data" / "init"
DATA_DIR = ROOT / "data"
FIG_DIR = DATA_DIR / "figs"
RULES_SCHEMA_PATH = DATA_DIR / "rules_and_schema.jsonl"


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


def _load_rules_schema_map(path: Path) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for row in _load_jsonl(path):
        puzzle = row.get("puzzle")
        if not isinstance(puzzle, str) or not puzzle:
            continue
        mapping[puzzle] = {
            "rules": row.get("rules"),
            "ref_observation": row.get("ref_observation"),
        }
    return mapping


def _find_construct_fn(mod: Any, puzzle: str):
    fn_name = f"construct_{puzzle}_data"
    fn = getattr(mod, fn_name, None)
    if callable(fn):
        return fn
    for name in dir(mod):
        if name.startswith("construct_") and name.endswith("_data"):
            cand = getattr(mod, name)
            if callable(cand):
                return cand
    raise AttributeError(f"No construct function found for puzzle={puzzle}")


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


def _build_observation_from_original(item: dict[str, Any]) -> Any:
    puzzle = item["puzzle"]
    mod = importlib.import_module(f"construction.{puzzle}")
    get_observation = getattr(mod, "get_observation", None)
    if not callable(get_observation):
        return item.get("original_data")

    original_data = _decode_json_keys(item.get("original_data"))
    payload: dict[str, Any] = {
        "original_data": original_data,
    }

    row = item.get("row")
    col = item.get("column")
    if isinstance(row, int):
        payload["row"] = row
    if isinstance(col, int):
        payload["column"] = col
    if isinstance(row, int) and isinstance(col, int) and row == col:
        payload["column/row"] = row

    return get_observation(payload)


def _cap_image_max_edge(path: Path, max_edge: int = 768) -> None:
    try:
        from PIL import Image
    except Exception:
        return

    with Image.open(path) as img:
        w, h = img.size
        cur = max(w, h)
        if cur <= max_edge:
            return
        scale = max_edge / float(cur)
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        resized = img.resize(new_size, Image.Resampling.LANCZOS)
        resized.save(path)


def _render_one(item: dict[str, Any], figs_dir: Path) -> tuple[str, str]:
    puzzle = item["puzzle"]
    sample_id = item["id"]
    base = f"{puzzle}_{sample_id}"

    mod = importlib.import_module(f"construction.{puzzle}")
    construct_fn = _find_construct_fn(mod, puzzle)
    ret = construct_fn(_decode_json_keys(item))

    if "initial_image" in ret and "answer_image" in ret:
        src_initial = Path(ret["initial_image"])
        src_answer = Path(ret["answer_image"])
    else:
        # Compatibility path for constructors that only return figure names.
        fig_name = ret.get("fig_name")
        ans_name = ret.get("answer_fig_name")
        if not fig_name or not ans_name:
            raise KeyError(f"Missing image fields for puzzle={puzzle}, keys={sorted(ret.keys())}")
        puzzle_dir = ROOT / "puzzles" / puzzle
        src_initial = puzzle_dir / f"{fig_name}.png"
        src_answer = puzzle_dir / f"{ans_name}.png"

    dst_initial = figs_dir / f"{base}.png"
    dst_answer = figs_dir / f"{base}_answer.png"
    shutil.copy2(src_initial, dst_initial)
    shutil.copy2(src_answer, dst_answer)

    _cap_image_max_edge(dst_initial, max_edge=768)
    _cap_image_max_edge(dst_answer, max_edge=768)

    return str(Path("data") / "figs" / dst_initial.name), str(Path("data") / "figs" / dst_answer.name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render anchor figures and build final anchor dataset.")
    parser.add_argument("--init-dir", type=Path, default=INIT_DIR)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()

    root = ROOT
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    anchor_path = args.init_dir / "anchor.jsonl"
    transfer_path = args.init_dir / "transfer.jsonl"
    rules_schema_map = _load_rules_schema_map(RULES_SCHEMA_PATH)

    anchor_rows = _load_jsonl(anchor_path)
    figs_dir = args.data_dir / "figs"
    figs_dir.mkdir(parents=True, exist_ok=True)
    intermediate_puzzles_dir = ROOT / "puzzles"

    out_rows: list[dict[str, Any]] = []
    for row in anchor_rows:
        item = dict(row)
        item["idx"] = item.get("id")
        rs = rules_schema_map.get(item["puzzle"], {})
        item["rules"] = rs.get("rules")
        item["ref_observation"] = rs.get("ref_observation")
        item["observation"] = _build_observation_from_original(item)
        rel_initial, rel_answer = _render_one(item, figs_dir)
        item["image"] = rel_initial
        item["answer_image"] = rel_answer
        out_rows.append(item)

    _save_jsonl(args.data_dir / "anchor.jsonl", out_rows)
    transfer_rows = _load_jsonl(transfer_path)
    out_transfer: list[dict[str, Any]] = []
    for row in transfer_rows:
        item = dict(row)
        item["idx"] = item.get("id")
        rs = rules_schema_map.get(item["puzzle"], {})
        item["rules"] = rs.get("rules")
        item["ref_observation"] = rs.get("ref_observation")
        item["observation"] = _build_observation_from_original(item)
        out_transfer.append(item)
    _save_jsonl(args.data_dir / "transfer.jsonl", out_transfer)

    # construction helpers may emit intermediate figures under ROOT/puzzles/.
    # Keep repo output clean by removing these temporary artifacts.
    if intermediate_puzzles_dir.exists():
        shutil.rmtree(intermediate_puzzles_dir)

    print(f"anchor rows: {len(out_rows)} -> {args.data_dir / 'anchor.jsonl'}")
    print(f"transfer rows: {len(out_transfer)} -> {args.data_dir / 'transfer.jsonl'}")


if __name__ == "__main__":
    main()
