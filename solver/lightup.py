from __future__ import annotations

import copy
from typing import Dict, List, Optional, Sequence, Tuple

Pos = Tuple[int, int]
Cell = int  # -2 black, -1 unknown white, 0 no-bulb white, 1 bulb white
Grid = List[List[Cell]]


class _LightupSolver:
    DIR4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def __init__(self, black_grid: Sequence[Sequence[Optional[int]]]):
        self.n = len(black_grid)
        self.m = len(black_grid[0])
        self.black_grid = [[black_grid[r][c] for c in range(self.m)] for r in range(self.n)]
        self._last_fail = ""

        self.base: Grid = [[-2 if self.black_grid[r][c] is not None else -1 for c in range(self.m)] for r in range(self.n)]
        self.white_cells: List[Pos] = [(r, c) for r in range(self.n) for c in range(self.m) if self.black_grid[r][c] is None]
        self.numbered: Dict[Pos, int] = {
            (r, c): int(self.black_grid[r][c])
            for r in range(self.n)
            for c in range(self.m)
            if isinstance(self.black_grid[r][c], int) and int(self.black_grid[r][c]) >= 0
        }

        self.row_segments: List[List[Pos]] = []
        self.col_segments: List[List[Pos]] = []
        self.row_seg_of: Dict[Pos, int] = {}
        self.col_seg_of: Dict[Pos, int] = {}
        self._build_segments()

        self.illum_sources: Dict[Pos, set[Pos]] = {p: set() for p in self.white_cells}
        self._build_illum_sources()

        self.num_neighbors: Dict[Pos, List[Pos]] = {}
        for (r, c), _k in self.numbered.items():
            neigh = []
            for dr, dc in self.DIR4:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.n and 0 <= nc < self.m and self.black_grid[nr][nc] is None:
                    neigh.append((nr, nc))
            self.num_neighbors[(r, c)] = neigh

        self.cell_weight: Dict[Pos, int] = {}
        for p in self.white_cells:
            w = 0
            w += len(self.illum_sources[p])
            rs = self.row_segments[self.row_seg_of[p]]
            cs = self.col_segments[self.col_seg_of[p]]
            w += len(rs) + len(cs)
            for neigh in self.num_neighbors.values():
                if p in neigh:
                    w += 5
            self.cell_weight[p] = w

    def _build_segments(self):
        for r in range(self.n):
            c = 0
            while c < self.m:
                if self.black_grid[r][c] is not None:
                    c += 1
                    continue
                seg = []
                while c < self.m and self.black_grid[r][c] is None:
                    seg.append((r, c))
                    c += 1
                idx = len(self.row_segments)
                self.row_segments.append(seg)
                for p in seg:
                    self.row_seg_of[p] = idx

        for c in range(self.m):
            r = 0
            while r < self.n:
                if self.black_grid[r][c] is not None:
                    r += 1
                    continue
                seg = []
                while r < self.n and self.black_grid[r][c] is None:
                    seg.append((r, c))
                    r += 1
                idx = len(self.col_segments)
                self.col_segments.append(seg)
                for p in seg:
                    self.col_seg_of[p] = idx

    def _build_illum_sources(self):
        for p in self.white_cells:
            rs = self.row_segments[self.row_seg_of[p]]
            cs = self.col_segments[self.col_seg_of[p]]
            self.illum_sources[p].update(rs)
            self.illum_sources[p].update(cs)

    def _state_key(self, grid: Grid):
        return tuple(tuple(row) for row in grid)

    def _set_cell(self, grid: Grid, r: int, c: int, v: int) -> bool:
        if self.black_grid[r][c] is not None:
            self._last_fail = f"cannot assign black cell ({r},{c})"
            return False
        cur = grid[r][c]
        if cur == v:
            return True
        if cur != -1 and cur != v:
            self._last_fail = f"conflict at ({r},{c})"
            return False
        grid[r][c] = v
        return True

    def _check_number_bounds(self, grid: Grid) -> bool:
        for pos, k in self.numbered.items():
            neigh = self.num_neighbors[pos]
            bulbs = 0
            unknown = 0
            for r, c in neigh:
                if grid[r][c] == 1:
                    bulbs += 1
                elif grid[r][c] == -1:
                    unknown += 1
            if bulbs > k:
                self._last_fail = f"number clue {pos} exceeded ({bulbs}>{k})"
                return False
            if bulbs + unknown < k:
                self._last_fail = f"number clue {pos} cannot reach {k}"
                return False
        return True

    def _check_segment_bounds(self, grid: Grid) -> bool:
        for i, seg in enumerate(self.row_segments):
            bulbs = sum(1 for r, c in seg if grid[r][c] == 1)
            if bulbs > 1:
                self._last_fail = f"row segment {i} has multiple bulbs"
                return False
        for i, seg in enumerate(self.col_segments):
            bulbs = sum(1 for r, c in seg if grid[r][c] == 1)
            if bulbs > 1:
                self._last_fail = f"col segment {i} has multiple bulbs"
                return False
        return True

    def _check_illum_feasible(self, grid: Grid) -> bool:
        for p in self.white_cells:
            if any(grid[r][c] == 1 for r, c in self.illum_sources[p]):
                continue
            if not any(grid[r][c] != 0 for r, c in self.illum_sources[p]):
                self._last_fail = f"cell {p} cannot be illuminated"
                return False
        return True

    def _propagate_numbers(self, grid: Grid):
        changed = False
        for pos, k in self.numbered.items():
            neigh = self.num_neighbors[pos]
            bulbs = sum(1 for r, c in neigh if grid[r][c] == 1)
            unknown = [(r, c) for r, c in neigh if grid[r][c] == -1]
            need = k - bulbs
            if need < 0 or need > len(unknown):
                self._last_fail = f"number clue {pos} impossible"
                return None

            if need == 0:
                for r, c in unknown:
                    if not self._set_cell(grid, r, c, 0):
                        return None
                    changed = True
            elif need == len(unknown):
                for r, c in unknown:
                    if not self._set_cell(grid, r, c, 1):
                        return None
                    changed = True

        return changed

    def _propagate_segments(self, grid: Grid):
        changed = False

        for i, seg in enumerate(self.row_segments):
            bulbs = [(r, c) for r, c in seg if grid[r][c] == 1]
            unknown = [(r, c) for r, c in seg if grid[r][c] == -1]
            if len(bulbs) > 1:
                self._last_fail = f"row segment {i} has two bulbs"
                return None
            if len(bulbs) == 1:
                for r, c in unknown:
                    if not self._set_cell(grid, r, c, 0):
                        return None
                    changed = True

        for i, seg in enumerate(self.col_segments):
            bulbs = [(r, c) for r, c in seg if grid[r][c] == 1]
            unknown = [(r, c) for r, c in seg if grid[r][c] == -1]
            if len(bulbs) > 1:
                self._last_fail = f"col segment {i} has two bulbs"
                return None
            if len(bulbs) == 1:
                for r, c in unknown:
                    if not self._set_cell(grid, r, c, 0):
                        return None
                    changed = True

        return changed

    def _propagate_illum(self, grid: Grid):
        changed = False
        for p in self.white_cells:
            if any(grid[r][c] == 1 for r, c in self.illum_sources[p]):
                continue
            possible = [(r, c) for r, c in self.illum_sources[p] if grid[r][c] != 0]
            if not possible:
                self._last_fail = f"white cell {p} cannot be illuminated"
                return None
            if len(possible) == 1:
                r, c = possible[0]
                if not self._set_cell(grid, r, c, 1):
                    return None
                changed = True
        return changed

    def _propagate(self, grid: Grid) -> bool:
        self._last_fail = ""

        while True:
            if not self._check_number_bounds(grid):
                return False
            if not self._check_segment_bounds(grid):
                return False
            if not self._check_illum_feasible(grid):
                return False

            changed = False
            c1 = self._propagate_numbers(grid)
            if c1 is None:
                return False
            changed = changed or bool(c1)

            c2 = self._propagate_segments(grid)
            if c2 is None:
                return False
            changed = changed or bool(c2)

            c3 = self._propagate_illum(grid)
            if c3 is None:
                return False
            changed = changed or bool(c3)

            if not changed:
                break

        return True

    def _is_complete(self, grid: Grid) -> bool:
        return all(grid[r][c] != -1 for r, c in self.white_cells)

    def _check_final(self, grid: Grid) -> bool:
        if not self._is_complete(grid):
            self._last_fail = "unresolved white cells remain"
            return False
        if not self._check_number_bounds(grid):
            return False
        if not self._check_segment_bounds(grid):
            return False
        for p in self.white_cells:
            if not any(grid[r][c] == 1 for r, c in self.illum_sources[p]):
                self._last_fail = f"white cell {p} not illuminated"
                return False
        return True

    def _choose_branch(self, grid: Grid) -> Optional[Pos]:
        best = None
        best_key = None
        for p in self.white_cells:
            r, c = p
            if grid[r][c] != -1:
                continue
            illum_deg = len([q for q in self.illum_sources[p] if grid[q[0]][q[1]] != 0])
            key = (illum_deg, -self.cell_weight[p], r, c)
            if best_key is None or key < best_key:
                best_key = key
                best = p
        return best

    def _search_one(self, grid: Grid, depth: int, depth_limit: Optional[int]) -> Optional[Grid]:
        if not self._propagate(grid):
            return None
        if self._check_final(grid):
            return grid

        if depth_limit is not None and depth >= depth_limit:
            self._last_fail = f"depth limit reached at d={depth}"
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

        self._last_fail = f"both branches failed at ({r},{c})"
        return None

    def solve_staged(self) -> Optional[Grid]:
        g0 = copy.deepcopy(self.base)
        if self._propagate(g0) and self._check_final(g0):
            return g0

        for cap in (3, 6):
            g = copy.deepcopy(self.base)
            ans = self._search_one(g, 0, cap)
            if ans is not None:
                return ans

        g = copy.deepcopy(self.base)
        return self._search_one(g, 0, None)


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict):
        if "data" in obs and isinstance(obs["data"], list):
            obs = obs["data"]
        elif "original_data" in obs and isinstance(obs["original_data"], dict) and "data" in obs["original_data"]:
            obs = obs["original_data"]["data"]

    if isinstance(obs, dict) and all(isinstance(k, tuple) and len(k) == 2 for k in obs):
        max_r = max(r for r, _ in obs)
        max_c = max(c for _, c in obs)
        n, m = max_r + 1, max_c + 1
        grid = [[None for _ in range(m)] for _ in range(n)]
        for (r, c), v in obs.items():
            grid[r][c] = int(v)
        return grid

    if not (isinstance(obs, list) and obs and isinstance(obs[0], list)):
        raise ValueError("lightup observation must be 2D list or dict")

    n = len(obs)
    m = len(obs[0])
    grid = [[None for _ in range(m)] for _ in range(n)]
    for r in range(n):
        if len(obs[r]) != m:
            raise ValueError("lightup grid must be rectangular")
        for c in range(m):
            v = obs[r][c]
            grid[r][c] = None if v is None else int(v)
    return grid


def _build_answer(grid: Grid):
    n, m = len(grid), len(grid[0])
    out = [[None for _ in range(m)] for _ in range(n)]
    for r in range(n):
        for c in range(m):
            if grid[r][c] == 1:
                out[r][c] = "B"
    return out


def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 10000,
    log_level: str = "brief",
):
    del verbose, max_logs, log_level

    black_grid = _normalize_observation(observation)
    solver = _LightupSolver(black_grid)
    ans = solver.solve_staged()
    if ans is None:
        return "No Solution"

    return _build_answer(ans)
