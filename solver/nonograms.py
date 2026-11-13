from __future__ import annotations

import copy
from functools import lru_cache
from typing import List, Optional, Sequence, Tuple

Cell = int  # -1 unknown, 0 white, 1 black
Grid = List[List[Cell]]
Pos = Tuple[int, int]


@lru_cache(maxsize=None)
def _line_patterns(length: int, runs: Tuple[int, ...]) -> Tuple[Tuple[int, ...], ...]:
    if not runs:
        return (tuple([0] * length),)

    total_blocks = sum(runs)
    gaps = len(runs) - 1
    min_need = total_blocks + gaps
    if min_need > length:
        return tuple()

    out = []

    def dfs(i: int, pos: int, arr: List[int]):
        if i == len(runs):
            if pos < length:
                arr.extend([0] * (length - pos))
            out.append(tuple(arr))
            if pos < length:
                del arr[-(length - pos) :]
            return

        rem_blocks = sum(runs[i:])
        rem_gaps = len(runs) - i - 1
        max_start = length - (rem_blocks + rem_gaps)
        for s in range(pos, max_start + 1):
            add0 = s - pos
            if add0 > 0:
                arr.extend([0] * add0)
            arr.extend([1] * runs[i])
            np = s + runs[i]
            if i < len(runs) - 1:
                arr.append(0)
                dfs(i + 1, np + 1, arr)
                arr.pop()
            else:
                dfs(i + 1, np, arr)
            del arr[-(runs[i] + add0) :]

    dfs(0, 0, [])
    return tuple(out)


class _NonogramSolver:
    def __init__(
        self,
        row_runs: Sequence[Sequence[int]],
        col_runs: Sequence[Sequence[int]],
    ):
        self.row_runs = [tuple(int(x) for x in rr) for rr in row_runs]
        self.col_runs = [tuple(int(x) for x in cc) for cc in col_runs]
        self.h = len(self.row_runs)
        self.w = len(self.col_runs)
        self.base: Grid = [[-1 for _ in range(self.w)] for _ in range(self.h)]

    def _set_cell(self, grid: Grid, r: int, c: int, v: int) -> bool:
        cur = grid[r][c]
        if cur == v:
            return True
        if cur != -1 and cur != v:
            return False
        grid[r][c] = v
        return True

    def _fit_row(self, r: int, grid: Grid):
        pats = _line_patterns(self.w, self.row_runs[r])
        out = []
        row = grid[r]
        for p in pats:
            ok = True
            for i, v in enumerate(row):
                if v != -1 and v != p[i]:
                    ok = False
                    break
            if ok:
                out.append(p)
        return out

    def _fit_col(self, c: int, grid: Grid):
        pats = _line_patterns(self.h, self.col_runs[c])
        out = []
        for p in pats:
            ok = True
            for r in range(self.h):
                v = grid[r][c]
                if v != -1 and v != p[r]:
                    ok = False
                    break
            if ok:
                out.append(p)
        return out

    def _propagate(self, grid: Grid):
        while True:
            changed = False

            row_pats = []
            for r in range(self.h):
                pats = self._fit_row(r, grid)
                if not pats:
                    return False
                row_pats.append(pats)

                for c in range(self.w):
                    vals = {p[c] for p in pats}
                    if len(vals) == 1:
                        forced = next(iter(vals))
                        if grid[r][c] == forced:
                            continue
                        if not self._set_cell(grid, r, c, forced):
                            return False
                        changed = True

            col_pats = []
            for c in range(self.w):
                pats = self._fit_col(c, grid)
                if not pats:
                    return False
                col_pats.append(pats)

                for r in range(self.h):
                    vals = {p[r] for p in pats}
                    if len(vals) == 1:
                        forced = next(iter(vals))
                        if grid[r][c] == forced:
                            continue
                        if not self._set_cell(grid, r, c, forced):
                            return False
                        changed = True

            valid_col_sets = [set(pats) for pats in col_pats]
            for r in range(self.h):
                new_pats = []
                for p in row_pats[r]:
                    ok = True
                    for c in range(self.w):
                        if not any(cp[r] == p[c] for cp in valid_col_sets[c]):
                            ok = False
                            break
                    if ok:
                        new_pats.append(p)
                if not new_pats:
                    return False
                row_pats[r] = new_pats

            if not changed:
                break

        return True

    def _check_final(self, grid: Grid) -> bool:
        for r in range(self.h):
            for c in range(self.w):
                if grid[r][c] == -1:
                    return False

        for r in range(self.h):
            line = tuple(grid[r][c] for c in range(self.w))
            if line not in _line_patterns(self.w, self.row_runs[r]):
                return False

        for c in range(self.w):
            line = tuple(grid[r][c] for r in range(self.h))
            if line not in _line_patterns(self.h, self.col_runs[c]):
                return False

        return True

    def _choose_branch(self, grid: Grid) -> Optional[Pos]:
        best = None
        best_key = None
        for r in range(self.h):
            pats = self._fit_row(r, grid)
            if len(pats) <= 1:
                continue
            for c in range(self.w):
                if grid[r][c] != -1:
                    continue
                vals = {p[c] for p in pats}
                if len(vals) <= 1:
                    continue
                row_entropy = len(pats)
                col_entropy = len(self._fit_col(c, grid))
                key = (row_entropy + col_entropy, r, c)
                if best_key is None or key < best_key:
                    best_key = key
                    best = (r, c)

        if best is not None:
            return best

        for r in range(self.h):
            for c in range(self.w):
                if grid[r][c] == -1:
                    return (r, c)
        return None

    def _search_one(self, grid: Grid, depth: int, depth_limit: Optional[int]):
        ok = self._propagate(grid)
        if not ok:
            return None
        if self._check_final(grid):
            return grid
        if depth_limit is not None and depth >= depth_limit:
            return None

        pos = self._choose_branch(grid)
        if pos is None:
            return None
        r, c = pos

        for v in (1, 0):
            g2 = copy.deepcopy(grid)
            if not self._set_cell(g2, r, c, v):
                continue
            ans = self._search_one(g2, depth + 1, depth_limit)
            if ans is not None:
                return ans

        return None

    def solve_staged(self):
        g0 = copy.deepcopy(self.base)
        ok = self._propagate(g0)
        if ok and self._check_final(g0):
            return g0

        for cap in (3, 6):
            g = copy.deepcopy(self.base)
            ans = self._search_one(g, 0, cap)
            if ans is not None:
                return ans

        g = copy.deepcopy(self.base)
        return self._search_one(g, 0, None)


def _normalize_runs_item(x):
    if x is None:
        return tuple()
    if isinstance(x, (list, tuple)):
        return tuple(int(v) for v in x if int(v) > 0)
    v = int(x)
    return tuple() if v <= 0 else (v,)


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict):
        if "row_black_runs" in obs and "col_black_runs" in obs:
            return [list(r) for r in obs["row_black_runs"]], [list(c) for c in obs["col_black_runs"]]
        if "original_data" in obs and isinstance(obs["original_data"], dict):
            od = obs["original_data"]
            rr = od.get("row_black_runs", od.get("row_numbers"))
            cc = od.get("col_black_runs", od.get("col_numbers"))
            if rr is not None and cc is not None:
                return [list(r) for r in rr], [list(c) for c in cc]

    raise ValueError("nonograms observation must contain row_black_runs and col_black_runs")


def _build_answer(grid: Grid):
    return [["B" if v == 1 else None for v in row] for row in grid]


def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 10000,
    log_level: str = "brief",
):
    row_runs, col_runs = _normalize_observation(observation)
    row_runs = [list(_normalize_runs_item(x)) for x in row_runs]
    col_runs = [list(_normalize_runs_item(x)) for x in col_runs]

    solver = _NonogramSolver(row_runs, col_runs)
    ans = solver.solve_staged()
    if ans is None:
        return "No Solution"
    return _build_answer(ans)
