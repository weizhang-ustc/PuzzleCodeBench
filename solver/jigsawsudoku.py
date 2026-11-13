from __future__ import annotations

from solver._latin_region_core import LatinRegionSolver


def _normalize_region_grid(data, n=None):
    if isinstance(data, dict):
        data = data.get("region", data.get("regions", data.get("data", data)))

    if not isinstance(data, list) or not data:
        raise ValueError("regions must be a non-empty list")

    if isinstance(data[0], list) and data[0] and not isinstance(data[0][0], tuple):
        grid = [row[:] for row in data]
        if n is not None and (len(grid) != n or any(len(row) != n for row in grid)):
            raise ValueError("region grid shape mismatch")
        return grid

    if n is None:
        max_r = max(r for region in data for r, _ in region)
        max_c = max(c for region in data for _, c in region)
        n = max(max_r, max_c) + 1
    grid = [[None for _ in range(n)] for _ in range(n)]
    for rid, cells in enumerate(data):
        for r, c in cells:
            grid[r][c] = rid
    return grid


def _normalize_givens(data, n):
    if isinstance(data, dict):
        grid = [[None for _ in range(n)] for _ in range(n)]
        for (r, c), v in data.items():
            grid[int(r)][int(c)] = int(v)
        return grid
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError("givens must be dict or 2D list")
    if len(data) != n or any(len(row) != n for row in data):
        raise ValueError("givens shape mismatch")
    return [[None if v is None else int(v) for v in row] for row in data]


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict) and "original_data" in obs and isinstance(obs["original_data"], dict):
        orig = obs["original_data"]
        n = obs.get("column/row")
        region_grid = _normalize_region_grid(orig.get("region", orig.get("regions", orig)), n=n)
        givens = _normalize_givens(orig.get("data", {}), len(region_grid))
        return givens, region_grid

    if not isinstance(obs, dict):
        raise ValueError("jigsawsudoku observation must be dict")

    region_grid = _normalize_region_grid(obs.get("regions", obs.get("region", obs)))
    n = len(region_grid)
    givens = _normalize_givens(obs.get("givens", obs.get("data", {})), n)
    return givens, region_grid


def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 8000,
    log_level: str = "brief",
):
    del verbose, max_logs, log_level

    givens, region_of = _normalize_observation(observation)
    solver = LatinRegionSolver(givens, region_of, False, 0, "brief")
    answer, _ = solver.solve_staged()
    return answer if answer is not None else "No Solution"
