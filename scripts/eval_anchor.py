#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import ast
import json
import re
import traceback
import importlib
import sys
from multiprocessing import Process, Queue
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from run_steps import run_code_with_steps

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from prettytable import PrettyTable
except Exception:
    class PrettyTable:  # type: ignore[override]
        def __init__(self) -> None:
            self.field_names: List[str] = []
            self.align = "l"
            self._rows: List[List[Any]] = []

        def add_row(self, row: List[Any]) -> None:
            self._rows.append(list(row))

        def _split_lines(self, v: Any) -> List[str]:
            return str(v).splitlines() or [""]

        def _render_line(self, cols: List[str], widths: List[int]) -> str:
            padded = []
            for i, cell in enumerate(cols):
                if self.align == "r":
                    padded.append(cell.rjust(widths[i]))
                elif self.align == "c":
                    padded.append(cell.center(widths[i]))
                else:
                    padded.append(cell.ljust(widths[i]))
            return "| " + " | ".join(padded) + " |"

        def __str__(self) -> str:
            headers = [str(x) for x in self.field_names]
            all_rows = [headers] + [[str(x) for x in row] for row in self._rows]
            widths = [0] * len(headers)
            for row in all_rows:
                for i, cell in enumerate(row):
                    for line in self._split_lines(cell):
                        widths[i] = max(widths[i], len(line))

            sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
            out: List[str] = [sep]
            out.append(self._render_line(headers, widths))
            out.append(sep)

            for row in self._rows:
                cells = [str(x) for x in row]
                lines_per_cell = [self._split_lines(c) for c in cells]
                height = max(len(lines) for lines in lines_per_cell) if lines_per_cell else 1
                for h in range(height):
                    line_cells = []
                    for i, lines in enumerate(lines_per_cell):
                        line_cells.append(lines[h] if h < len(lines) else "")
                    out.append(self._render_line(line_cells, widths))
                out.append(sep)
            return "\n".join(out)


THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
THINK_CLOSE_RE = re.compile(r"</think>", re.IGNORECASE)
FENCE_RE = re.compile(r"```(?:json|python|text)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
KEY_RE_TEMPLATE = r"([\"']){key}\1\s*:"

TEXT_PRIORITY_KEYS = [
    "response",
    "content",
    "output_text",
    "text",
    "result",
    "message",
    "generated_text",
]


@dataclass
class ExtractResult:
    ok: bool
    payload: Optional[Dict[str, Any]]
    method: str
    error: str = ""


@dataclass
class PuzzleComparators:
    puzzle_type: Optional[str]
    skip_compare: bool
    skip_reason: str = ""
    observation_tester: Optional[Callable[[Any, Any], Any]] = None
    answer_tester: Optional[Callable[[Any, Any], Any]] = None
    load_error: str = ""


def _iter_input_files(input_path: Path) -> Iterable[Path]:
    def is_raw_result_file(path: Path) -> bool:
        name = path.name
        if not name.endswith(".jsonl"):
            return False
        if name.endswith(".extracted.jsonl") or name.endswith(".rerun.jsonl"):
            return False
        if name == "all_results.jsonl":
            return False
        return True

    if input_path.is_file():
        if is_raw_result_file(input_path):
            yield input_path
        return

    for p in sorted(input_path.rglob("*.jsonl")):
        if is_raw_result_file(p):
            yield p


def _normalize_text(s: str) -> str:
    return s.replace("\ufeff", "").strip()


def _strip_noise_blocks(s: str, strip_think: bool = True) -> str:
    out = s
    if strip_think:
        out = THINK_RE.sub("", out)
        # Some model outputs contain only a trailing </think> marker without an
        # opening <think> tag. In that case, treat everything before the last
        # closing marker as thinking content and keep the suffix only.
        if "<think" not in out.lower():
            matches = list(THINK_CLOSE_RE.finditer(out))
            if matches:
                out = out[matches[-1].end() :]
    return out.strip()


def _extract_text_candidates(obj: Any) -> List[str]:
    out: List[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, str):
            t = x.strip()
            if t:
                out.append(t)
            return

        if isinstance(x, dict):
            for key in TEXT_PRIORITY_KEYS:
                v = x.get(key)
                if isinstance(v, str) and v.strip():
                    out.append(v.strip())

            choices = x.get("choices")
            if isinstance(choices, list):
                for ch in choices:
                    if isinstance(ch, dict):
                        msg = ch.get("message")
                        if isinstance(msg, dict):
                            content = msg.get("content")
                            if isinstance(content, str) and content.strip():
                                out.append(content.strip())

            output = x.get("output")
            if isinstance(output, list):
                for item in output:
                    if isinstance(item, dict):
                        content = item.get("content")
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict):
                                    text = c.get("text")
                                    if isinstance(text, str) and text.strip():
                                        out.append(text.strip())

            for v in x.values():
                walk(v)
            return

        if isinstance(x, list):
            for v in x:
                walk(v)

    walk(obj)

    seen = set()
    uniq: List[str] = []
    for s in out:
        if s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    return uniq


def _peel_json_string_layers(text: str, max_depth: int = 4) -> str:
    cur = text.strip()
    for _ in range(max_depth):
        try:
            val = json.loads(cur)
        except Exception:
            break
        if isinstance(val, str):
            nxt = val.strip()
            if not nxt or nxt == cur:
                break
            cur = nxt
            continue
        break
    return cur


def _try_parse_mapping(text: str) -> Optional[Dict[str, Any]]:
    s = text.strip()
    if not s:
        return None

    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    try:
        obj = ast.literal_eval(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    return None


def _scan_quoted_string(text: str, start: int) -> Optional[Tuple[str, int]]:
    if start >= len(text) or text[start] not in ('"', "'"):
        return None

    q = text[start]
    i = start + 1
    escaped = False
    while i < len(text):
        ch = text[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if ch == "\\":
            escaped = True
            i += 1
            continue
        if ch == q:
            raw = text[start : i + 1]
            try:
                val = json.loads(raw)
                if isinstance(val, str):
                    return val, i + 1
            except Exception:
                pass
            try:
                val = ast.literal_eval(raw)
                if isinstance(val, str):
                    return val, i + 1
            except Exception:
                pass
            return raw[1:-1], i + 1
        i += 1
    return None


def _scan_balanced_chunk(text: str, start: int) -> Optional[Tuple[str, int]]:
    if start >= len(text) or text[start] not in "[{":
        return None

    stack = [text[start]]
    i = start + 1
    quote: Optional[str] = None
    escaped = False

    while i < len(text):
        ch = text[i]

        if quote is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            i += 1
            continue

        if ch in ('"', "'"):
            quote = ch
            i += 1
            continue

        if ch in "[{":
            stack.append(ch)
        elif ch in "]}":
            if not stack:
                return None
            top = stack[-1]
            if (top == "{" and ch == "}") or (top == "[" and ch == "]"):
                stack.pop()
                if not stack:
                    return text[start : i + 1], i + 1
            else:
                return None
        i += 1

    return None


def _extract_key_value_fragment(text: str, key: str) -> Any:
    pattern = re.compile(KEY_RE_TEMPLATE.format(key=re.escape(key)))
    for m in pattern.finditer(text):
        i = m.end()
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            continue

        if text[i] in ('"', "'"):
            got = _scan_quoted_string(text, i)
            if got is not None:
                return got[0]
            continue

        if text[i] in "[{":
            got = _scan_balanced_chunk(text, i)
            if got is not None:
                chunk, _ = got
                parsed = _try_parse_mapping(chunk)
                if parsed is not None:
                    return parsed
                try:
                    return ast.literal_eval(chunk)
                except Exception:
                    return chunk
            continue

        j = i
        while j < len(text) and text[j] not in ",}\n":
            j += 1
        token = text[i:j].strip()
        if token:
            return token

    return None


def _extract_json_from_text(raw_text: str) -> ExtractResult:
    text = _normalize_text(raw_text)
    text = _peel_json_string_layers(text)

    obj = _try_parse_mapping(text)
    if obj is not None:
        return ExtractResult(True, obj, "whole_mapping")

    for block in FENCE_RE.findall(text):
        blk = _peel_json_string_layers(block.strip())
        obj = _try_parse_mapping(blk)
        if obj is not None:
            return ExtractResult(True, obj, "fenced_mapping")

    decoder = json.JSONDecoder()
    best: Optional[Tuple[int, Dict[str, Any], str]] = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            cand, end = decoder.raw_decode(text, idx=i)
        except Exception:
            continue
        if not isinstance(cand, dict):
            continue

        span = end - i
        score = span
        if "observation" in cand:
            score += 50_000
        if "code" in cand:
            score += 50_000
        if best is None or score > best[0]:
            best = (score, cand, f"raw_decode_scan@{i}")

    if best is not None:
        return ExtractResult(True, best[1], best[2])

    best_py: Optional[Tuple[int, Dict[str, Any], str]] = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        got = _scan_balanced_chunk(text, i)
        if got is None:
            continue
        chunk, end = got
        obj = _try_parse_mapping(chunk)
        if obj is None:
            continue

        span = end - i
        score = span
        if "observation" in obj:
            score += 50_000
        if "code" in obj:
            score += 50_000
        if best_py is None or score > best_py[0]:
            best_py = (score, obj, f"balanced_scan@{i}")

    if best_py is not None:
        return ExtractResult(True, best_py[1], best_py[2])

    l = text.find("{")
    r = text.rfind("}")
    if l >= 0 and r > l:
        chunk = _peel_json_string_layers(text[l : r + 1])
        obj = _try_parse_mapping(chunk)
        if obj is not None:
            return ExtractResult(True, obj, "first_last_brace")

    observation = _extract_key_value_fragment(text, "observation")
    code = _extract_key_value_fragment(text, "code")
    if observation is not None or code is not None:
        payload: Dict[str, Any] = {}
        if observation is not None:
            payload["observation"] = observation
        if code is not None:
            payload["code"] = code
        return ExtractResult(True, payload, "key_fragment_fallback")

    return ExtractResult(False, None, "failed", error="Unable to locate parseable JSON object in text")


def _parse_coord_number(token: str) -> Optional[Any]:
    t = token.strip()
    if not t:
        return None

    if re.fullmatch(r"[-+]?\d+", t):
        try:
            return int(t)
        except Exception:
            return None

    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?", t):
        try:
            return float(t)
        except Exception:
            return None

    return None


def _parse_tuple_like_key(key: str) -> Optional[Tuple[Any, ...]]:
    s = key.strip()
    if not s:
        return None

    parts = [p.strip() for p in s.split(",")]
    if len(parts) < 2:
        return None

    parsed_parts: List[Any] = []
    for p in parts:
        num = _parse_coord_number(p)
        if num is None:
            return None
        parsed_parts.append(num)

    return tuple(parsed_parts)


def _restore_tuple_like_keys(value: Any) -> Any:
    if isinstance(value, list):
        return [_restore_tuple_like_keys(v) for v in value]

    if isinstance(value, dict):
        out: Dict[Any, Any] = {}
        for k, v in value.items():
            new_key: Any = k
            if isinstance(k, str):
                parsed_key = _parse_tuple_like_key(k)
                if parsed_key is not None:
                    new_key = parsed_key
            # Avoid accidental overwrite if key normalization collides.
            if new_key in out and new_key != k:
                new_key = k
            out[new_key] = _restore_tuple_like_keys(v)
        return out

    return value


def _try_parse_observation(value: Any) -> Any:
    parsed: Any = value

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value

        try:
            parsed = json.loads(text)
        except Exception:
            try:
                parsed = ast.literal_eval(text)
            except Exception:
                parsed = value

    # Keep coordinate-like dict keys as strings (JSON form) so solver code
    # that parses keys via string operations (e.g. key.strip()) remains compatible.
    return parsed


def _decode_escaped_string(value: str) -> str:
    text = value.strip()
    if not text:
        return value

    likely_escaped = ("\\n" in text) or ("\\t" in text) or ("\\r" in text)
    if not likely_escaped:
        return value

    for parser in (json.loads, ast.literal_eval):
        try:
            decoded = parser(f'"{text}"')
            if isinstance(decoded, str) and decoded:
                return decoded
        except Exception:
            continue

    return value


def _normalize_code_field(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return value

    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
            if isinstance(parsed, str):
                text = parsed
                break
        except Exception:
            continue

    text = _decode_escaped_string(text)
    return text


def _recover_payload_fields(clean_text: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Recover observation/code when top-level JSON is malformed but fragments are present."""
    out: Dict[str, Any] = dict(payload or {})

    has_obs = out.get("observation") not in (None, "")
    has_code = out.get("code") not in (None, "")

    # Common malformed pattern from some model outputs:
    # {"observation": "{"data": ...}", "code": "..."}
    # The parser may only capture the inner {"data": ...} object.
    if not has_obs and isinstance(payload, dict) and "data" in payload:
        out["observation"] = payload
        has_obs = True

    if not has_obs:
        obs = _extract_key_value_fragment(clean_text, "observation")
        if obs not in (None, ""):
            out["observation"] = obs
            has_obs = True

    if not has_code:
        code = _extract_key_value_fragment(clean_text, "code")
        if code not in (None, ""):
            out["code"] = code

    return out


def _extract_observation_from_code(code_text: str) -> Any:
    try:
        tree = ast.parse(code_text)
    except Exception:
        return None

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "OBSERVATION":
                    try:
                        return ast.literal_eval(node.value)
                    except Exception:
                        return None
        if isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == "OBSERVATION" and node.value is not None:
                try:
                    return ast.literal_eval(node.value)
                except Exception:
                    return None

    return None


def _extract_observation_from_text_assignment(text: str) -> Any:
    pattern = re.compile(r"\bOBSERVATION\s*=")
    for m in pattern.finditer(text):
        i = m.end()
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            continue
        if text[i] != "{":
            continue
        got = _scan_balanced_chunk(text, i)
        if got is None:
            continue
        chunk, _ = got
        try:
            value = ast.literal_eval(chunk)
        except Exception:
            continue
        if isinstance(value, dict):
            return value
    return None


def _is_valid_python_code(code_text: str) -> bool:
    try:
        ast.parse(code_text)
        return True
    except Exception:
        return False


def _extract_v4_payload_from_text(raw_text: str) -> ExtractResult:
    text = _normalize_text(raw_text)
    text = _peel_json_string_layers(text)
    text = text.strip()
    if not text:
        return ExtractResult(False, None, "empty", error="Empty candidate text")

    global_observation = _extract_observation_from_text_assignment(text)

    code_candidates: List[Tuple[int, str, str]] = []

    for m in re.finditer(r"```\s*([a-zA-Z0-9_+-]*)\s*\n?(.*?)```", text, re.DOTALL):
        lang = (m.group(1) or "").strip().lower()
        body = (m.group(2) or "").strip()
        if not body:
            continue
        rank = len(body)
        if lang in ("python", "py"):
            rank += 10000
        code_candidates.append((rank, body, f"fenced_{lang or 'plain'}"))

    raw = text.strip()
    if raw:
        rank = len(raw)
        if raw.startswith("OBSERVATION"):
            rank += 15000
        elif "def solve(" in raw:
            rank += 5000
        code_candidates.append((rank, raw, "raw_text"))

    if not code_candidates:
        return ExtractResult(False, None, "failed", error="No Python code candidate found")

    code_candidates.sort(key=lambda x: x[0], reverse=True)
    best_solve_payload: Optional[Tuple[str, Dict[str, Any]]] = None

    for _, code_text, method in code_candidates:
        code_text = _normalize_code_field(code_text)
        if not isinstance(code_text, str) or not code_text.strip():
            continue

        observation = _extract_observation_from_code(code_text)
        if observation is None and global_observation is not None:
            observation = global_observation

        payload: Dict[str, Any] = {"code": code_text}
        if observation is not None:
            payload["observation"] = observation

        has_solve = "def solve(" in code_text
        syntax_ok = _is_valid_python_code(code_text)

        if has_solve and best_solve_payload is None:
            best_solve_payload = (method, payload)

        if has_solve and syntax_ok:
            return ExtractResult(True, payload, method)

    if best_solve_payload is not None:
        mth, pld = best_solve_payload
        return ExtractResult(True, pld, f"{mth}_syntax_fallback")

    # Fallback: return best code even if solve() is missing; downstream run stage will report the exact failure.
    _, best_code, best_method = code_candidates[0]
    best_code = _normalize_code_field(best_code)
    payload2: Dict[str, Any] = {"code": best_code}
    obs2 = _extract_observation_from_code(best_code) if isinstance(best_code, str) else None
    if obs2 is None and global_observation is not None:
        obs2 = global_observation
    if obs2 is not None:
        payload2["observation"] = obs2
    return ExtractResult(True, payload2, f"{best_method}_fallback")


def _idx_sort_key(v: Any) -> Tuple[int, Any]:
    if isinstance(v, int):
        return (0, v)
    if isinstance(v, str):
        t = v.strip()
        if re.fullmatch(r"-?\d+", t):
            return (0, int(t))
        return (1, t)
    return (2, str(v))


def _looks_like_solver_code(code: Any) -> bool:
    if not isinstance(code, str):
        return False
    text = code.strip()
    if not text:
        return False
    return "def solve(" in text or "def solve (" in text


def _has_meaningful_extract(obs: Any, code: Any) -> bool:
    has_obs = obs is not None
    has_code = _looks_like_solver_code(code)
    return has_obs or has_code


def _to_json_safe(value: Any) -> Any:
    """Recursively convert values into JSON-serializable forms."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        out: Dict[Any, Any] = {}
        for k, v in value.items():
            if isinstance(k, (str, int, float, bool)) or k is None:
                key = k
            else:
                key = str(k)
            out[key] = _to_json_safe(v)
        return out

    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(v) for v in value]

    return str(value)


def _load_existing_jsonl_by_line_no(path: Path) -> Dict[int, Dict[str, Any]]:
    if not path.exists():
        return {}

    out: Dict[int, Dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            key_raw = obj.get("line_no", line_no)
            try:
                key = int(key_raw)
            except Exception:
                key = line_no
            out[key] = obj
    return out


def _line_to_output(record: Dict[str, Any], source_file: Path, line_no: int, strip_think: bool) -> Dict[str, Any]:
    idx = record.get("idx", line_no)

    candidates = _extract_text_candidates(record)
    if not candidates:
        return {
            "idx": idx,
            "source_file": str(source_file),
            "line_no": line_no,
            "ok": False,
            "method": "no_text_candidate",
            "error": "No text field found in this JSON line",
            "observation": None,
            "code": None,
        }

    best_success: Optional[Tuple[int, str, ExtractResult]] = None
    best_failure: Optional[Tuple[int, str, ExtractResult]] = None

    for cand in candidates:
        clean = _strip_noise_blocks(cand, strip_think=strip_think)
        parsed = _extract_v4_payload_from_text(clean)

        rank = len(clean) // 1000
        if parsed.ok and parsed.payload:
            payload = parsed.payload
            has_code = isinstance(payload.get("code"), str) and bool(payload.get("code", "").strip())
            has_obs = payload.get("observation") not in (None, "")
            if has_code:
                rank += 20
            if has_obs:
                rank += 10
            if parsed.method.startswith("fenced_python"):
                rank += 5
            if best_success is None or rank > best_success[0]:
                best_success = (rank, clean, parsed)
        else:
            fail_rank = len(clean)
            if best_failure is None or fail_rank > best_failure[0]:
                best_failure = (fail_rank, clean, parsed)

    if best_success is None:
        if best_failure is None:
            return {
                "idx": idx,
                "source_file": str(source_file),
                "line_no": line_no,
                "ok": False,
                "method": "failed",
                "error": "No parse candidates found.",
                "observation": None,
                "code": None,
            }
        _, clean, failed = best_failure
        return {
            "idx": idx,
            "source_file": str(source_file),
            "line_no": line_no,
            "ok": False,
            "method": failed.method,
            "error": failed.error,
            "observation": None,
            "code": None,
            "clean_text": clean,
        }

    _, clean, success = best_success
    payload = success.payload or {}
    obs = _try_parse_observation(payload.get("observation"))
    code = _normalize_code_field(payload.get("code"))
    meaningful = _has_meaningful_extract(obs, code)

    if not meaningful:
        return {
            "idx": idx,
            "source_file": str(source_file),
            "line_no": line_no,
            "ok": False,
            "method": f"{success.method}_empty_payload",
            "error": "Extracted payload has neither observation nor runnable solve() code.",
            "observation": obs,
            "code": code,
            "clean_text": clean,
        }

    return {
        "idx": idx,
        "source_file": str(source_file),
        "line_no": line_no,
        "ok": True,
        "method": success.method,
        "observation": obs,
        "code": code,
        "clean_text": clean,
    }


def process_extract_file(
    input_file: Path,
    output_file: Path,
    strip_think: bool = True,
    overwrite: bool = False,
) -> Dict[str, Any]:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    existing_by_line = {} if overwrite else _load_existing_jsonl_by_line_no(output_file)

    total = 0
    ok = 0
    fail = 0
    reused = 0
    computed = 0
    failed_idxs: List[Any] = []
    rows: List[Dict[str, Any]] = []

    with input_file.open("r", encoding="utf-8") as fin:
        for line_no, line in enumerate(fin, start=1):
            if not line.strip():
                continue
            total += 1

            cached = existing_by_line.get(line_no)
            if cached is not None:
                reused += 1
                if cached.get("ok"):
                    ok += 1
                else:
                    fail += 1
                    failed_idxs.append(cached.get("idx", line_no))
                rows.append(cached)
                continue

            computed += 1
            try:
                record = json.loads(line)
            except Exception as exc:
                fail += 1
                failed_idxs.append(line_no)
                rows.append(
                    {
                        "idx": line_no,
                        "source_file": str(input_file),
                        "line_no": line_no,
                        "ok": False,
                        "method": "invalid_jsonl_row",
                        "error": str(exc),
                        "observation": None,
                        "code": None,
                    }
                )
                continue

            out = _line_to_output(record, input_file, line_no, strip_think=strip_think)
            if out.get("ok"):
                ok += 1
            else:
                fail += 1
                failed_idxs.append(out.get("idx", line_no))
            rows.append(out)

    rows.sort(key=_row_idx_sort_key)

    with output_file.open("w", encoding="utf-8") as fout:
        for out in rows:
            fout.write(json.dumps(_to_json_safe(out), ensure_ascii=False) + "\n")

    return {
        "total": total,
        "ok": ok,
        "fail": fail,
        "failed_idxs": failed_idxs,
        "reused": reused,
        "computed": computed,
    }


def _read_json_or_jsonl(path: Path) -> List[Dict[str, Any]]:
    if path.suffix == ".json":
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Expected a list in JSON file: {path}")
        return data

    if path.suffix == ".jsonl":
        rows: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
                if not isinstance(obj, dict):
                    raise ValueError(f"JSONL row is not an object at {path}:{line_no}")
                rows.append(obj)
        return rows

    raise ValueError(f"Unsupported file extension: {path}")


def _json_stable(v: Any) -> str:
    return json.dumps(_to_json_safe(v), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _build_dataset_index(
    rows: List[Dict[str, Any]],
    key: str,
    obs_key: str,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    by_idx: Dict[str, Dict[str, Any]] = {}
    by_obs: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        if key in row:
            by_idx[str(row[key])] = row
        if obs_key in row:
            obs_norm = _try_parse_observation(row.get(obs_key))
            by_obs[_json_stable(obs_norm)] = row

    return by_idx, by_obs


def _exec_solve_worker(payload: Dict[str, Any]) -> Dict[str, Any]:
    code = payload["code"]
    observation = payload["observation"]
    count_opcodes = bool(payload.get("count_opcodes", False))

    return run_code_with_steps(
        code=code,
        observation=observation,
        normalize_prediction=False,
        count_opcodes=count_opcodes,
    )


def _exec_solve_worker_plain(payload: Dict[str, Any]) -> Dict[str, Any]:
    code = payload["code"]
    observation = payload["observation"]

    ns: Dict[str, Any] = {"__name__": "__codex_eval_plain__"}
    try:
        compiled = compile(code, "<model_code>", "exec")
    except Exception:
        return {
            "ok": False,
            "stage": "compile",
            "error": traceback.format_exc(),
        }

    try:
        exec(compiled, ns, ns)
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

    try:
        prediction = solve_fn(observation)
    except Exception:
        return {
            "ok": False,
            "stage": "run",
            "error": traceback.format_exc(),
        }

    return {
        "ok": True,
        "stage": "done",
        "prediction": prediction,
        "metrics": {},
    }


def _run_worker_main(payload: Dict[str, Any], result_q: Queue) -> None:
    try:
        result_q.put(_exec_solve_worker(payload))
    except Exception:
        result_q.put(
            {
                "ok": False,
                "stage": "worker_crash",
                "error": traceback.format_exc(),
            }
        )


def _run_worker_main_plain(payload: Dict[str, Any], result_q: Queue) -> None:
    try:
        result_q.put(_exec_solve_worker_plain(payload))
    except Exception:
        result_q.put(
            {
                "ok": False,
                "stage": "worker_crash",
                "error": traceback.format_exc(),
            }
        )


def _run_with_timeout(code: str, observation: Any, timeout_sec: float, count_opcodes: bool = False) -> Dict[str, Any]:
    payload = {"code": code, "observation": observation, "count_opcodes": count_opcodes}

    result_q: Queue = Queue(maxsize=1)
    proc = Process(target=_run_worker_main, args=(payload, result_q), daemon=True)
    proc.start()
    proc.join(timeout_sec)

    if proc.is_alive():
        proc.terminate()
        proc.join(1)
        if proc.is_alive():
            proc.kill()
            proc.join(1)
        return {
            "ok": False,
            "stage": "timeout",
            "error": f"Execution exceeded timeout ({timeout_sec}s)",
        }

    try:
        if not result_q.empty():
            return result_q.get_nowait()
    except Exception:
        pass

    return {
        "ok": False,
        "stage": "worker_exit",
        "error": f"Worker exited without result (exitcode={proc.exitcode})",
    }


def _run_with_timeout_plain(code: str, observation: Any, timeout_sec: float) -> Dict[str, Any]:
    payload = {"code": code, "observation": observation}

    result_q: Queue = Queue(maxsize=1)
    proc = Process(target=_run_worker_main_plain, args=(payload, result_q), daemon=True)
    proc.start()
    proc.join(timeout_sec)

    if proc.is_alive():
        proc.terminate()
        proc.join(1)
        if proc.is_alive():
            proc.kill()
            proc.join(1)
        return {
            "ok": False,
            "stage": "timeout",
            "error": f"Execution exceeded timeout ({timeout_sec}s)",
        }

    try:
        if not result_q.empty():
            return result_q.get_nowait()
    except Exception:
        pass

    return {
        "ok": False,
        "stage": "worker_exit",
        "error": f"Worker exited without result (exitcode={proc.exitcode})",
    }


def _iter_jsonl(path: Path) -> Iterable[Tuple[int, Dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            s = line.strip()
            if not s:
                continue
            yield line_no, json.loads(s)


def _count_nonempty_lines(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def _row_idx_sort_key(row: Dict[str, Any]) -> Tuple[int, int]:
    idx_raw = row.get("idx")
    line_no_raw = row.get("line_no", 0)

    try:
        idx = int(idx_raw)
    except Exception:
        idx = 10**18

    try:
        line_no = int(line_no_raw)
    except Exception:
        line_no = 0

    return idx, line_no


def _collect_output_tokens_stats(path: Path) -> Dict[str, float]:
    total = 0.0
    count = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue

            tok: Any = None
            usage = obj.get("token_usage")
            if isinstance(usage, dict):
                for key in ("output_tokens", "completion_tokens"):
                    v = usage.get(key)
                    if isinstance(v, (int, float)):
                        tok = v
                        break

            if tok is None:
                for key in ("output_tokens", "completion_tokens"):
                    v = obj.get(key)
                    if isinstance(v, (int, float)):
                        tok = v
                        break

            if isinstance(tok, (int, float)):
                total += float(tok)
                count += 1

    return {
        "sum": total,
        "count": count,
    }


def _collect_output_tokens_by_idx(path: Path) -> Dict[str, float]:
    out: Dict[str, float] = {}
    nonempty_line_no = 0

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            nonempty_line_no += 1
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue

            tok: Any = None
            usage = obj.get("token_usage")
            if isinstance(usage, dict):
                for key in ("output_tokens", "completion_tokens"):
                    v = usage.get(key)
                    if isinstance(v, (int, float)):
                        tok = v
                        break

            if tok is None:
                for key in ("output_tokens", "completion_tokens"):
                    v = obj.get(key)
                    if isinstance(v, (int, float)):
                        tok = v
                        break

            if not isinstance(tok, (int, float)):
                continue

            idx = obj.get("idx", nonempty_line_no)
            out[str(idx)] = float(tok)

    return out


def _collect_oracle_correct_output_tokens_stats(
    input_path: Path,
    rerun_path: Path,
) -> Dict[str, float]:
    by_idx = _collect_output_tokens_by_idx(input_path)
    total = sum(by_idx.values())
    count = len(by_idx)

    correct_total = 0.0
    correct_count = 0
    for _, row in _iter_jsonl(rerun_path):
        idx = row.get("idx")
        if idx is None:
            continue
        cmp_oracle = row.get("comparison_oracle")
        if not isinstance(cmp_oracle, dict):
            cmp_oracle = row.get("comparison")
        if not isinstance(cmp_oracle, dict):
            continue
        if not bool(cmp_oracle.get("is_correct")):
            continue
        tok = by_idx.get(str(idx))
        if tok is None:
            continue
        correct_total += tok
        correct_count += 1

    return {
        "sum": total,
        "count": count,
        "oracle_correct_sum": correct_total,
        "oracle_correct_count": correct_count,
    }


def _normalize_prediction_backslashes_for_compare(value: Any) -> Any:
    if isinstance(value, str):
        while '\\\\' in value:
            value = value.replace('\\\\', '\\')
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


def _import_construction_module(module_name: str):
    try:
        return importlib.import_module(module_name), None
    except Exception as exc:
        # Some construction modules import matplotlib only for plotting.
        # For rerun comparison we only need test_observation/test_answer.
        msg = str(exc)
        if "No module named 'matplotlib'" not in msg:
            return None, exc

    import sys
    import types

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


def _load_puzzle_comparators(puzzle_name: Optional[str]) -> PuzzleComparators:
    if not puzzle_name:
        return PuzzleComparators(puzzle_type=None, skip_compare=False)

    puzzle_type, _, _ = _parse_puzzle_name(puzzle_name)
    if puzzle_type == "calendar_":
        return PuzzleComparators(
            puzzle_type=puzzle_type,
            skip_compare=True,
            skip_reason="calendar_ comparison is disabled",
        )

    module_name = f"construction.{puzzle_type}"
    module, load_exc = _import_construction_module(module_name)
    if module is None:
        return PuzzleComparators(
            puzzle_type=puzzle_type,
            skip_compare=False,
            load_error=f"failed to import {module_name}: {load_exc}",
        )

    obs_tester = getattr(module, "test_observation", None)
    ans_tester = getattr(module, "test_answer", None)
    if not callable(obs_tester):
        obs_tester = None
    if not callable(ans_tester):
        ans_tester = None

    return PuzzleComparators(
        puzzle_type=puzzle_type,
        skip_compare=False,
        observation_tester=obs_tester,
        answer_tester=ans_tester,
    )


def _run_compare_tester(
    tester: Optional[Callable[[Any, Any], Any]],
    pred: Any,
    gt: Any,
) -> Tuple[bool, str, Optional[str]]:
    if tester is None:
        return pred == gt, "eq_fallback", None

    try:
        ret = tester(pred, gt)
        return bool(ret), "custom_tester", None
    except Exception:
        return False, "custom_tester", traceback.format_exc()


def _summarize_rerun_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    matched = 0
    obs_compared = 0
    obs_match = 0

    ran_oracle = 0
    run_ok_oracle = 0
    ran_e2e = 0
    run_ok_e2e = 0

    compared_oracle = 0
    compare_ok_oracle = 0
    compared_e2e = 0
    compare_ok_e2e = 0

    step_rows = 0
    line_steps_total = 0
    unique_lines_total = 0
    max_call_depth_total = 0
    opcode_steps_total = 0
    call_steps_total = 0
    return_steps_total = 0
    wall_time_total_sec = 0.0

    answer_oracle_ok_metric_rows = 0
    answer_oracle_ok_line_steps_total = 0
    answer_oracle_ok_unique_lines_total = 0
    answer_oracle_ok_max_call_depth_total = 0

    for row in rows:
        if row.get("matched"):
            matched += 1

        obs_cmp = row.get("observation_comparison")
        if isinstance(obs_cmp, dict):
            if bool(obs_cmp.get("has_extracted_observation")) and not bool(obs_cmp.get("skipped", False)):
                obs_compared += 1
                if bool(obs_cmp.get("is_correct")):
                    obs_match += 1

        run_oracle = row.get("run_oracle")
        if not isinstance(run_oracle, dict) and isinstance(row.get("run"), dict):
            run_oracle = row.get("run")

        if isinstance(run_oracle, dict):
            attempted = run_oracle.get("attempted")
            if attempted is None:
                attempted = run_oracle.get("stage") not in ("input", None)
            if bool(attempted):
                ran_oracle += 1
            if bool(run_oracle.get("ok")):
                run_ok_oracle += 1
                metrics = run_oracle.get("metrics")
                if isinstance(metrics, dict):
                    step_rows += 1
                    line_steps_total += int(metrics.get("line_steps", 0) or 0)
                    unique_lines_total += int(metrics.get("unique_lines_executed", 0) or 0)
                    max_call_depth_total += int(metrics.get("max_call_depth", 0) or 0)
                    opcode_steps_total += int(metrics.get("opcode_steps", 0) or 0)
                    call_steps_total += int(metrics.get("call_steps", 0) or 0)
                    return_steps_total += int(metrics.get("return_steps", 0) or 0)
                    wall_time_total_sec += float(metrics.get("wall_time_sec", 0.0) or 0.0)

        run_e2e = row.get("run_e2e")
        if isinstance(run_e2e, dict):
            attempted_e2e = bool(run_e2e.get("attempted"))
            if attempted_e2e:
                ran_e2e += 1
            if bool(run_e2e.get("ok")):
                run_ok_e2e += 1

        cmp_oracle = row.get("comparison_oracle")
        if not isinstance(cmp_oracle, dict) and isinstance(row.get("comparison"), dict):
            cmp_oracle = row.get("comparison")

        if isinstance(cmp_oracle, dict):
            if bool(cmp_oracle.get("has_prediction")) and not bool(cmp_oracle.get("skipped", False)):
                compared_oracle += 1
                if bool(cmp_oracle.get("is_correct")):
                    compare_ok_oracle += 1
                    if isinstance(run_oracle, dict):
                        run_metrics = run_oracle.get("metrics")
                        if isinstance(run_metrics, dict):
                            answer_oracle_ok_metric_rows += 1
                            answer_oracle_ok_line_steps_total += int(run_metrics.get("line_steps", 0) or 0)
                            answer_oracle_ok_unique_lines_total += int(run_metrics.get("unique_lines_executed", 0) or 0)
                            answer_oracle_ok_max_call_depth_total += int(run_metrics.get("max_call_depth", 0) or 0)

        cmp_e2e = row.get("comparison_e2e")
        if isinstance(cmp_e2e, dict):
            if bool(cmp_e2e.get("has_prediction")) and not bool(cmp_e2e.get("skipped", False)):
                compared_e2e += 1
                if bool(cmp_e2e.get("is_correct")):
                    compare_ok_e2e += 1

    return {
        "rows_total": total,
        "rows_matched_dataset": matched,
        "observation_compared": obs_compared,
        "observation_correct": obs_match,
        "code_executed_oracle": ran_oracle,
        "code_execution_success_oracle": run_ok_oracle,
        "code_executed_e2e": ran_e2e,
        "code_execution_success_e2e": run_ok_e2e,
        "answer_compared_oracle": compared_oracle,
        "answer_correct_oracle": compare_ok_oracle,
        "answer_compared_e2e": compared_e2e,
        "answer_correct_e2e": compare_ok_e2e,
        "step_rows": step_rows,
        "line_steps_total": line_steps_total,
        "unique_lines_total": unique_lines_total,
        "max_call_depth_total": max_call_depth_total,
        "opcode_steps_total": opcode_steps_total,
        "call_steps_total": call_steps_total,
        "return_steps_total": return_steps_total,
        "wall_time_total_sec": wall_time_total_sec,
        "answer_oracle_ok_metric_rows": answer_oracle_ok_metric_rows,
        "answer_oracle_ok_line_steps_total": answer_oracle_ok_line_steps_total,
        "answer_oracle_ok_unique_lines_total": answer_oracle_ok_unique_lines_total,
        "answer_oracle_ok_max_call_depth_total": answer_oracle_ok_max_call_depth_total,
        # Backward-compatible aliases
        "code_executed": ran_oracle,
        "code_execution_success": run_ok_oracle,
        "answer_compared": compared_oracle,
        "answer_correct": compare_ok_oracle,
        "answer_ok_metric_rows": answer_oracle_ok_metric_rows,
        "answer_ok_line_steps_total": answer_oracle_ok_line_steps_total,
        "answer_ok_unique_lines_total": answer_oracle_ok_unique_lines_total,
        "answer_ok_max_call_depth_total": answer_oracle_ok_max_call_depth_total,
    }


def run_extracted_file(
    *,
    dataset_path: Path,
    extracted_path: Path,
    output_path: Path,
    puzzle_name: Optional[str] = None,
    match_key: str = "idx",
    dataset_observation_key: str = "observation",
    dataset_answer_key: str = "answer",
    mode: str = "both",
    timeout_sec: float = 10.0,
    fallback_match_by_observation: bool = False,
    show_progress: bool = False,
    progress_label: str = "",
    count_opcodes: bool = False,
    run_backend: str = "plain",
    overwrite: bool = False,
) -> Dict[str, Any]:
    dataset_rows = _read_json_or_jsonl(dataset_path)
    dataset_by_idx, dataset_by_obs = _build_dataset_index(
        dataset_rows,
        key=match_key,
        obs_key=dataset_observation_key,
    )
    base_comparators = _load_puzzle_comparators(puzzle_name)

    comparator_cache: Dict[str, PuzzleComparators] = {}

    def _comparators_for_row_puzzle(row_puzzle: Optional[str]) -> PuzzleComparators:
        if isinstance(row_puzzle, str) and row_puzzle.strip():
            key = row_puzzle.strip()
            got = comparator_cache.get(key)
            if got is None:
                got = _load_puzzle_comparators(key)
                comparator_cache[key] = got
            return got
        return base_comparators

    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing_by_line = {} if overwrite else _load_existing_jsonl_by_line_no(output_path)

    rows_out: List[Dict[str, Any]] = []
    reused = 0
    computed = 0

    total_rows = _count_nonempty_lines(extracted_path) if show_progress else 0
    label = progress_label or extracted_path.name

    for total, (line_no, rec) in enumerate(_iter_jsonl(extracted_path), start=1):
        if show_progress:
            print(f"[rerun] {label} {total}/{total_rows} rows", end="\r", flush=True)

        cached = existing_by_line.get(line_no)
        if cached is not None:
            reused += 1
            rows_out.append(cached)
            continue

        computed += 1

        row_out: Dict[str, Any] = {
            "line_no": line_no,
            "match_key": match_key,
            "mode": mode,
            "run_backend": run_backend,
            "puzzle_type": base_comparators.puzzle_type,
            "source": {
                "dataset": str(dataset_path),
                "extracted": str(extracted_path),
            },
        }
        if base_comparators.load_error:
            row_out["comparison_load_error"] = base_comparators.load_error
        row_out.update(
            {
                "idx": rec.get("idx"),
                "extracted_ok": rec.get("ok"),
            }
        )

        extracted_observation = _try_parse_observation(rec.get("observation"))

        ds_row: Optional[Dict[str, Any]] = None
        used_match = None

        if match_key in rec and str(rec[match_key]) in dataset_by_idx:
            ds_row = dataset_by_idx[str(rec[match_key])]
            used_match = "idx"
        elif fallback_match_by_observation and extracted_observation is not None:
            obs_sig = _json_stable(extracted_observation)
            ds_row = dataset_by_obs.get(obs_sig)
            used_match = "observation"

        if ds_row is None:
            row_out["matched"] = False
            row_out["error"] = "No matching dataset row found."
            rows_out.append(row_out)
            continue

        row_out["matched"] = True
        row_out["matched_by"] = used_match
        row_out["dataset_idx"] = ds_row.get(match_key)

        row_puzzle = ds_row.get("puzzle")
        row_comparators = _comparators_for_row_puzzle(row_puzzle if isinstance(row_puzzle, str) else None)
        row_out["puzzle_type"] = row_comparators.puzzle_type
        if row_comparators.load_error:
            row_out["comparison_load_error"] = row_comparators.load_error
        else:
            row_out.pop("comparison_load_error", None)

        observation = _try_parse_observation(ds_row.get(dataset_observation_key))
        answer = ds_row.get(dataset_answer_key)
        row_out["groundtruth_observation"] = observation
        row_out["groundtruth_answer"] = answer

        if extracted_observation is not None:
            if row_comparators.skip_compare:
                row_out["observation_comparison"] = {
                    "has_extracted_observation": True,
                    "is_correct": None,
                    "skipped": True,
                    "reason": row_comparators.skip_reason,
                    "extracted_observation": extracted_observation,
                }
            else:
                obs_is_correct, obs_method, obs_error = _run_compare_tester(
                    row_comparators.observation_tester,
                    extracted_observation,
                    observation,
                )
                row_out["observation_comparison"] = {
                    "has_extracted_observation": True,
                    "is_correct": obs_is_correct,
                    "method": obs_method,
                    "extracted_observation": extracted_observation,
                }
                if obs_error:
                    row_out["observation_comparison"]["error"] = obs_error
        else:
            row_out["observation_comparison"] = {
                "has_extracted_observation": False,
                "is_correct": False,
                "reason": "No extracted observation to compare.",
            }

        prediction_oracle: Any = None
        prediction_e2e: Any = None
        run_result_oracle: Optional[Dict[str, Any]] = None
        run_result_e2e: Optional[Dict[str, Any]] = None

        if mode in ("run", "both"):
            code = rec.get("code")
            if not isinstance(code, str) or not code.strip():
                run_result_oracle = {
                    "attempted": False,
                    "ok": False,
                    "stage": "input",
                    "error": "Missing/empty code field.",
                }
                run_result_e2e = {
                    "attempted": False,
                    "ok": False,
                    "stage": "input",
                    "error": "Missing/empty code field.",
                }
            else:
                if run_backend == "steps":
                    run_result_oracle = _run_with_timeout(
                        code, observation, timeout_sec, count_opcodes=count_opcodes
                    )
                else:
                    run_result_oracle = _run_with_timeout_plain(code, observation, timeout_sec)
                run_result_oracle["attempted"] = True
                if run_result_oracle.get("ok"):
                    prediction_oracle = _normalize_prediction(run_result_oracle.get("prediction"))
                    prediction_oracle = _normalize_prediction_backslashes_for_compare(prediction_oracle)
                    run_result_oracle["prediction"] = prediction_oracle

                if extracted_observation is None:
                    run_result_e2e = {
                        "attempted": False,
                        "ok": False,
                        "stage": "input",
                        "error": "Missing extracted observation for e2e run.",
                    }
                else:
                    if run_backend == "steps":
                        run_result_e2e = _run_with_timeout(
                            code, extracted_observation, timeout_sec, count_opcodes=count_opcodes
                        )
                    else:
                        run_result_e2e = _run_with_timeout_plain(code, extracted_observation, timeout_sec)
                    run_result_e2e["attempted"] = True
                    if run_result_e2e.get("ok"):
                        prediction_e2e = _normalize_prediction(run_result_e2e.get("prediction"))
                        prediction_e2e = _normalize_prediction_backslashes_for_compare(prediction_e2e)
                        run_result_e2e["prediction"] = prediction_e2e

            row_out["run_oracle"] = run_result_oracle
            row_out["run_e2e"] = run_result_e2e
            # Backward-compatible key
            row_out["run"] = run_result_oracle

        if mode == "compare":
            prediction_raw: Any = None
            if "prediction" in rec:
                prediction_raw = _normalize_prediction(rec.get("prediction"))
                prediction_raw = _normalize_prediction_backslashes_for_compare(prediction_raw)
            elif "answer" in rec:
                prediction_raw = _normalize_prediction(rec.get("answer"))
                prediction_raw = _normalize_prediction_backslashes_for_compare(prediction_raw)
            prediction_oracle = prediction_raw
            prediction_e2e = prediction_raw

        if mode in ("compare", "both"):
            if row_comparators.skip_compare:
                row_out["comparison_oracle"] = {
                    "has_prediction": prediction_oracle is not None,
                    "is_correct": None,
                    "skipped": True,
                    "reason": row_comparators.skip_reason,
                    "prediction": prediction_oracle,
                }
                row_out["comparison_e2e"] = {
                    "has_prediction": prediction_e2e is not None,
                    "is_correct": None,
                    "skipped": True,
                    "reason": row_comparators.skip_reason,
                    "prediction": prediction_e2e,
                }
            else:
                if prediction_oracle is not None:
                    is_correct_oracle, ans_method_oracle, ans_error_oracle = _run_compare_tester(
                        row_comparators.answer_tester,
                        prediction_oracle,
                        answer,
                    )
                    row_out["comparison_oracle"] = {
                        "has_prediction": True,
                        "is_correct": is_correct_oracle,
                        "method": ans_method_oracle,
                        "prediction": prediction_oracle,
                    }
                    if ans_error_oracle:
                        row_out["comparison_oracle"]["error"] = ans_error_oracle
                else:
                    row_out["comparison_oracle"] = {
                        "has_prediction": False,
                        "is_correct": False,
                        "reason": "No prediction available to compare.",
                    }

                if prediction_e2e is not None:
                    is_correct_e2e, ans_method_e2e, ans_error_e2e = _run_compare_tester(
                        row_comparators.answer_tester,
                        prediction_e2e,
                        answer,
                    )
                    row_out["comparison_e2e"] = {
                        "has_prediction": True,
                        "is_correct": is_correct_e2e,
                        "method": ans_method_e2e,
                        "prediction": prediction_e2e,
                    }
                    if ans_error_e2e:
                        row_out["comparison_e2e"]["error"] = ans_error_e2e
                else:
                    row_out["comparison_e2e"] = {
                        "has_prediction": False,
                        "is_correct": False,
                        "reason": "No prediction available to compare.",
                    }

            # Backward-compatible key
            row_out["comparison"] = row_out["comparison_oracle"]

        rows_out.append(row_out)

    rows_out.sort(key=_row_idx_sort_key)
    with output_path.open("w", encoding="utf-8") as out_f:
        for row in rows_out:
            out_f.write(json.dumps(_to_json_safe(row), ensure_ascii=False) + "\n")

    if show_progress:
        print(f"[rerun] {label} done: {len(rows_out)}/{total_rows} rows")

    summary = _summarize_rerun_rows(rows_out)
    summary["reused"] = reused
    summary["computed"] = computed
    return summary


def _parse_puzzle_name(puzzle_name: str) -> Tuple[str, Optional[str], Optional[str]]:
    m = re.fullmatch(r"([a-zA-Z0-9_+\-]+?)_(\d+)_(\d+)", puzzle_name)
    if not m:
        return puzzle_name, None, None
    return m.group(1), m.group(2), m.group(3)


def _resolve_dataset_path(dataset_root: Path, puzzle_name: str, explicit_dataset: Optional[str]) -> Path:
    if explicit_dataset:
        p = Path(explicit_dataset)
        if not p.exists():
            raise FileNotFoundError(f"Dataset not found: {p}")
        return p

    puzzle_type, maxsize, pergroup = _parse_puzzle_name(puzzle_name)

    def find_for_type(pt: str) -> Tuple[List[Path], List[Path]]:
        candidates: List[Path] = []
        if maxsize and pergroup:
            candidates.extend(
                [
                    dataset_root / f"{pt}_dataset_maxsize{maxsize}_pergroup{pergroup}.json",
                    dataset_root / f"{pt}_dataset_maxsize{maxsize}_pergroup{pergroup}.jsonl",
                ]
            )

        candidates.extend(
            [
                dataset_root / f"{pt}_dataset_maxsize10_pergroup1.json",
                dataset_root / f"{pt}_dataset_maxsize10_pergroup1.jsonl",
            ]
        )

        wildcard = sorted(dataset_root.glob(f"{pt}_dataset_*.json")) + sorted(
            dataset_root.glob(f"{pt}_dataset_*.jsonl")
        )
        return candidates, wildcard

    def pick_one(candidates: List[Path], wildcard: List[Path], source_type: str) -> Optional[Path]:
        for c in candidates:
            if c.exists():
                return c
        if len(wildcard) == 1:
            return wildcard[0]
        if wildcard:
            names = "\n".join(str(p) for p in wildcard)
            raise FileNotFoundError(
                f"Multiple dataset candidates for puzzle type '{source_type}'. Use --dataset explicitly.\n{names}"
            )
        return None

    candidates, wildcard = find_for_type(puzzle_type)
    picked = pick_one(candidates, wildcard, puzzle_type)
    if picked is not None:
        return picked

    # Typo-tolerant fallback: map puzzle type to closest available dataset prefix.
    available_types: List[str] = []
    seen = set()
    for p in sorted(dataset_root.glob("*_dataset_*.json")) + sorted(dataset_root.glob("*_dataset_*.jsonl")):
        m = re.match(r"(.+?)_dataset_", p.name)
        if not m:
            continue
        t = m.group(1)
        if t not in seen:
            seen.add(t)
            available_types.append(t)

    close = difflib.get_close_matches(puzzle_type, available_types, n=1, cutoff=0.7)
    if close:
        corrected = close[0]
        candidates2, wildcard2 = find_for_type(corrected)
        picked2 = pick_one(candidates2, wildcard2, corrected)
        if picked2 is not None:
            print(
                f"[dataset] puzzle type '{puzzle_type}' not found; using closest match '{corrected}' -> {picked2}"
            )
            return picked2

    hints = difflib.get_close_matches(puzzle_type, available_types, n=3, cutoff=0.0)
    hint_text = f" Closest dataset types: {', '.join(hints)}." if hints else ""
    raise FileNotFoundError(
        f"No dataset file found for puzzle '{puzzle_name}' under {dataset_root}.{hint_text}"
    )


def _model_name_from_path(path: Path) -> str:
    name = path.name
    if name.startswith("results-"):
        name = name[len("results-") :]
    if name.endswith(".jsonl"):
        name = name[:-6]
    return name


def _normalize_model_name_arg(name: str) -> str:
    out = name.strip()
    if out.startswith("results-"):
        out = out[len("results-") :]
    if out.endswith(".jsonl"):
        out = out[:-6]
    return out


def _model_display_sort_key(model: str) -> Tuple[str, int, str]:
    """
    Group model variants by base name and sort capability suffix from low -> high.
    Examples:
      gpt-5.4-low, gpt-5.4, gpt-5.4-medium, gpt-5.4-high, gpt-5.4-xhigh
    """
    m = model.strip().lower()
    suffix_rank = {
        # Put explicit default/base first.
        "base": 0,
        "default": 0,
        # Then low.
        "low": 1,
        "mini": 2,
        "medium": 3,
        "high": 4,
        "xhigh": 5,
    }

    # Match trailing capability tag (e.g. "-low", "-medium", "-high", "-xhigh").
    mt = re.match(r"^(.*?)-(low|mini|base|default|medium|high|xhigh)$", m)
    if mt:
        base = mt.group(1)
        suf = mt.group(2)
        return (base, suffix_rank.get(suf, 99), m)

    # No explicit suffix: treat as default.
    return (m, suffix_rank["default"], m)


def _pct(numer: int, denom: int) -> str:
    if denom <= 0:
        return "0.0%"
    return f"{(100.0 * numer / denom):.1f}%"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract + rerun for anchor-level single-file evaluation, while keeping "
            "the original extract_and_rerun core logic."
        )
    )
    parser.add_argument(
        "--input-file",
        default="results/results-gpt-5.4.jsonl",
        help="Input raw results jsonl file",
    )
    parser.add_argument(
        "--output-dir",
        default="results/anchor-level",
        help="Directory to write extracted/rerun outputs",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing .extracted/.rerun outputs")
    parser.add_argument("--dataset", default="data/anchor.jsonl", help="Anchor dataset jsonl path")
    parser.add_argument("--keep-think", action="store_true", help="Do not strip <think>...</think> blocks")
    parser.add_argument("--mode", choices=["run", "compare", "both"], default="both")
    parser.add_argument("--timeout-sec", type=float, default=30.0, help="Per-row timeout in seconds")
    parser.add_argument("--match-key", default="idx", help="Key for matching extracted row to dataset row")
    parser.add_argument("--dataset-observation-key", default="observation")
    parser.add_argument("--dataset-answer-key", default="answer")
    parser.add_argument(
        "--fallback-match-by-observation",
        action="store_true",
        help="If idx match fails, fallback to observation-content matching",
    )
    parser.add_argument("--progress", dest="progress", action="store_true", default=True, help="Show per-file rerun progress (default: on)")
    parser.add_argument("--no-progress", dest="progress", action="store_false", help="Disable per-file rerun progress")
    parser.add_argument(
        "--run-backend",
        choices=["plain", "steps"],
        default="plain",
        help=(
            "Execution backend for run/both mode: "
            "'plain' only executes solve() for result correctness; "
            "'steps' uses tracing via run_steps (higher overhead)."
        ),
    )
    parser.add_argument("--count-opcodes", action="store_true", help="Also count opcode-level steps (higher overhead)")
    parser.add_argument("--model-name", default=None, help="Reserved for compatibility; unused in single-file mode")
    args = parser.parse_args()

    input_file = Path(args.input_file)
    output_dir = Path(args.output_dir)
    dataset_path = Path(args.dataset)
    if not input_file.exists():
        raise SystemExit(f"Input file not found: {input_file}")
    if not dataset_path.exists():
        raise SystemExit(f"Dataset not found: {dataset_path}")

    strip_think = not args.keep_think
    output_dir.mkdir(parents=True, exist_ok=True)
    puzzle_name = "all_puzzles"
    print(f"[puzzle] {puzzle_name}")
    print(f"  dataset: {dataset_path}")
    print(f"  input:   {input_file}")
    print(f"  output:  {output_dir}")
    print(f"  backend: {args.run_backend}")

    extracted_file = output_dir / input_file.name.replace(".jsonl", ".extracted.jsonl")
    rerun_file = output_dir / input_file.name.replace(".jsonl", ".rerun.jsonl")

    extract_stats = process_extract_file(
        input_file,
        extracted_file,
        strip_think=strip_think,
        overwrite=args.overwrite,
    )
    rerun_stats = run_extracted_file(
        dataset_path=dataset_path,
        extracted_path=extracted_file,
        output_path=rerun_file,
        puzzle_name=puzzle_name,
        match_key=args.match_key,
        dataset_observation_key=args.dataset_observation_key,
        dataset_answer_key=args.dataset_answer_key,
        mode=args.mode,
        timeout_sec=args.timeout_sec,
        fallback_match_by_observation=args.fallback_match_by_observation,
        show_progress=args.progress,
        progress_label=f"{puzzle_name}/{input_file.name}",
        count_opcodes=args.count_opcodes,
        run_backend=args.run_backend,
        overwrite=args.overwrite,
    )
    output_token_stats = _collect_oracle_correct_output_tokens_stats(input_file, rerun_file)

    summary_rows: List[Dict[str, Any]] = [
        {
            "puzzle": puzzle_name,
            "dataset": str(dataset_path),
            "model": _model_name_from_path(input_file),
            "input_file": str(input_file),
            "extracted_file": str(extracted_file),
            "rerun_file": str(rerun_file),
            "extract": extract_stats,
            "rerun": rerun_stats,
            "output_tokens": output_token_stats,
        }
    ]
    all_results_path = output_dir / "all_results.jsonl"
    with all_results_path.open("w", encoding="utf-8") as f:
        for row in summary_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    model_agg: Dict[str, Dict[str, Any]] = {}
    for row in summary_rows:
        model = row["model"]
        ex = row["extract"]
        rr = row["rerun"]
        ot = row.get("output_tokens") or {}

        if model not in model_agg:
            model_agg[model] = {
                "rows_total": 0,
                "extract_ok": 0,
                "obs_compared": 0,
                "obs_ok": 0,
                "run_executed_oracle": 0,
                "run_ok_oracle": 0,
                "run_executed_e2e": 0,
                "run_ok_e2e": 0,
                "answer_compared_oracle": 0,
                "answer_ok_oracle": 0,
                "answer_compared_e2e": 0,
                "answer_ok_e2e": 0,
                "step_rows": 0,
                "line_steps_total": 0,
                "unique_lines_total": 0,
                "max_call_depth_total": 0,
                "answer_oracle_ok_metric_rows": 0,
                "answer_oracle_ok_line_steps_total": 0,
                "answer_oracle_ok_unique_lines_total": 0,
                "answer_oracle_ok_max_call_depth_total": 0,
                "output_tokens_sum": 0.0,
                "output_tokens_count": 0,
                "output_tokens_oracle_correct_sum": 0.0,
                "output_tokens_oracle_correct_count": 0,
                "puzzles": set(),
            }

        m = model_agg[model]
        m["rows_total"] += ex["total"]
        m["extract_ok"] += ex["ok"]
        m["obs_compared"] += rr["observation_compared"]
        m["obs_ok"] += rr["observation_correct"]
        m["run_executed_oracle"] += rr.get("code_executed_oracle", rr.get("code_executed", 0))
        m["run_ok_oracle"] += rr.get("code_execution_success_oracle", rr.get("code_execution_success", 0))
        m["run_executed_e2e"] += rr.get("code_executed_e2e", 0)
        m["run_ok_e2e"] += rr.get("code_execution_success_e2e", 0)
        m["answer_compared_oracle"] += rr.get("answer_compared_oracle", rr.get("answer_compared", 0))
        m["answer_ok_oracle"] += rr.get("answer_correct_oracle", rr.get("answer_correct", 0))
        m["answer_compared_e2e"] += rr.get("answer_compared_e2e", 0)
        m["answer_ok_e2e"] += rr.get("answer_correct_e2e", 0)
        m["step_rows"] += int(rr.get("step_rows", 0) or 0)
        m["line_steps_total"] += int(rr.get("line_steps_total", 0) or 0)
        m["unique_lines_total"] += int(rr.get("unique_lines_total", 0) or 0)
        m["max_call_depth_total"] += int(rr.get("max_call_depth_total", 0) or 0)
        m["answer_oracle_ok_metric_rows"] += int(rr.get("answer_oracle_ok_metric_rows", rr.get("answer_ok_metric_rows", 0)) or 0)
        m["answer_oracle_ok_line_steps_total"] += int(rr.get("answer_oracle_ok_line_steps_total", rr.get("answer_ok_line_steps_total", 0)) or 0)
        m["answer_oracle_ok_unique_lines_total"] += int(rr.get("answer_oracle_ok_unique_lines_total", rr.get("answer_ok_unique_lines_total", 0)) or 0)
        m["answer_oracle_ok_max_call_depth_total"] += int(rr.get("answer_oracle_ok_max_call_depth_total", rr.get("answer_ok_max_call_depth_total", 0)) or 0)
        m["output_tokens_sum"] += float(ot.get("sum", 0.0) or 0.0)
        m["output_tokens_count"] += int(ot.get("count", 0) or 0)
        m["output_tokens_oracle_correct_sum"] += float(ot.get("oracle_correct_sum", 0.0) or 0.0)
        m["output_tokens_oracle_correct_count"] += int(ot.get("oracle_correct_count", 0) or 0)
        m["puzzles"].add(row["puzzle"])

    table = PrettyTable()
    table.field_names = ["Model", "Rows", "Extract", "Observation", "Run (e2e/oracle)", "Answer (e2e)", "Answer (oracle)", "Avg Output Tokens (oracle_correct/all)", "Avg Max CallDepth (Answer Oracle)", "Puzzles"]
    # table.field_names = ["Model", "Rows", "Extract OK", "Obs OK", "Run OK", "Answer OK", "Avg Line Steps (Answer OK)", "Avg Unique Lines (Answer OK)", "Avg Max CallDepth (Answer OK)", "Puzzles"]
    table.align = "l"

    for model in sorted(model_agg.keys(), key=_model_display_sort_key):
        m = model_agg[model]
        puzzle_list = sorted(m["puzzles"])
        denom = m["answer_oracle_ok_metric_rows"]
        avg_max_call_depth = (m["answer_oracle_ok_max_call_depth_total"] / denom) if denom else 0.0
        avg_output_tokens_all = (m["output_tokens_sum"] / m["output_tokens_count"]) if m["output_tokens_count"] else 0.0
        avg_output_tokens_oracle_correct = (
            (m["output_tokens_oracle_correct_sum"] / m["output_tokens_oracle_correct_count"])
            if m["output_tokens_oracle_correct_count"]
            else 0.0
        )
        # avg_line_steps = (m["answer_ok_line_steps_total"] / denom) if denom else 0.0
        # avg_unique_lines = (m["answer_ok_unique_lines_total"] / denom) if denom else 0.0
        table.add_row(
            [
                model,
                m["rows_total"],
                f"{m['extract_ok']}/{m['rows_total']} ({_pct(m['extract_ok'], m['rows_total'])})",
                f"{m['obs_ok']}/{m['rows_total']} ({_pct(m['obs_ok'], m['rows_total'])})",
                f"{m['run_ok_e2e']}/{m['rows_total']} vs {m['run_ok_oracle']}/{m['rows_total']}",
                f"{m['answer_ok_e2e']}/{m['rows_total']} ({_pct(m['answer_ok_e2e'], m['rows_total'])})",
                f"{m['answer_ok_oracle']}/{m['rows_total']} ({_pct(m['answer_ok_oracle'], m['rows_total'])})",
                f"{avg_output_tokens_oracle_correct:.1f}/{avg_output_tokens_all:.1f}",
                f"{avg_max_call_depth:.1f}",
                ", ".join(puzzle_list),
            ]
        )

    print(f"Input: {input_file}")
    print(f"Output: {output_dir}")
    print(f"Puzzle: {summary_rows[0]['puzzle']}")
    print(f"Dataset: {summary_rows[0]['dataset']}")

    print(table)


if __name__ == "__main__":
    main()
