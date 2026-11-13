from __future__ import annotations

import re

from solver._latin_region_core import LatinRegionSolver


def _parse_unit(value):
    if isinstance(value, int):
        return value, value
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return int(value[0]), int(value[1])
    if isinstance(value, str):
        m = re.findall(r"\d+", value)
        if len(m) == 1:
            x = int(m[0])
            return x, x
        if len(m) >= 2:
            return int(m[0]), int(m[1])
    if isinstance(value, dict):
        if "rows" in value and "cols" in value:
            return int(value["rows"]), int(value["cols"])
        if "r" in value and "c" in value:
            return int(value["r"]), int(value["c"])
    raise ValueError(f"Invalid unit spec: {value}")


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict) and "original_data" in obs and isinstance(obs["original_data"], dict):
        orig = obs["original_data"]
        if "data" in orig:
            obs = {
                "data": orig["data"],
                "unit": orig.get("unit", obs.get("column/row", obs.get("unit"))),
            }

    if not isinstance(obs, dict) or "data" not in obs:
        raise ValueError("sudoku observation must include data")

    data = obs["data"]
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError("sudoku data must be non-empty 2D list")

    n = len(data)
    if any(len(row) != n for row in data):
        raise ValueError("sudoku grid must be square")

    unit_spec = obs.get("unit")
    if unit_spec is None:
        root = int(round(n ** 0.5))
        if root * root != n:
            raise ValueError("unit is required for non-square-subgrid sudoku")
        unit_r, unit_c = root, root
    else:
        unit_r, unit_c = _parse_unit(unit_spec)

    if unit_r <= 0 or unit_c <= 0 or n % unit_r != 0 or n % unit_c != 0:
        raise ValueError(f"invalid unit {unit_r}x{unit_c} for size {n}")

    givens = [[None if v is None else int(v) for v in row] for row in data]

    region_of = [[-1 for _ in range(n)] for _ in range(n)]
    rid = 0
    for r0 in range(0, n, unit_r):
        for c0 in range(0, n, unit_c):
            for r in range(r0, r0 + unit_r):
                for c in range(c0, c0 + unit_c):
                    region_of[r][c] = rid
            rid += 1

    return givens, region_of


def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 8000,
    log_level: str = "brief",
):
    givens, region_of = _normalize_observation(observation)
    solver = LatinRegionSolver(givens, region_of, False, 0, "brief")
    answer, _ = solver.solve_staged()
    if answer is None:
        return "No Solution"
    return answer
