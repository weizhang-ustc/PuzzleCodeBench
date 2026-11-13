from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Tuple

Pos = Tuple[int, int]
GridBW = List[List[Optional[str]]]


class _HitoriSolver:
    DIR4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def __init__(self, grid: List[List[int]]):
        self.n = len(grid)
        self.grid = [row[:] for row in grid]
        if any(len(row) != self.n for row in self.grid):
            raise ValueError("hitori grid must be square")

        self._last_fail = ""
        self._dead_cache = set()

        self.dom = [[3 for _ in range(self.n)] for _ in range(self.n)]

        self.row_groups: Dict[Tuple[int, int], List[int]] = {}
        self.col_groups: Dict[Tuple[int, int], List[int]] = {}
        for r in range(self.n):
            pos = {}
            for c in range(self.n):
                pos.setdefault(self.grid[r][c], []).append(c)
            for v, cols in pos.items():
                if len(cols) > 1:
                    self.row_groups[(r, v)] = cols
        for c in range(self.n):
            pos = {}
            for r in range(self.n):
                pos.setdefault(self.grid[r][c], []).append(r)
            for v, rows in pos.items():
                if len(rows) > 1:
                    self.col_groups[(c, v)] = rows

    def _inb(self, r: int, c: int) -> bool:
        return 0 <= r < self.n and 0 <= c < self.n

    def _snapshot(self):
        return [row[:] for row in self.dom], self._last_fail

    def _restore(self, snap):
        self.dom, self._last_fail = snap

    def _state_key(self):
        return tuple(tuple(row) for row in self.dom)

    def _force(self, r: int, c: int, token: int) -> bool:
        cur = self.dom[r][c]
        mask = 1 if token == 0 else 2
        if cur == mask:
            return True
        if cur & mask == 0:
            self._last_fail = f"conflict at ({r},{c})"
            return False
        self.dom[r][c] = mask
        return True

    def _adjacency_rules(self) -> bool:
        changed = False
        for r in range(self.n):
            for c in range(self.n):
                if self.dom[r][c] != 2:
                    continue
                for dr, dc in self.DIR4:
                    nr, nc = r + dr, c + dc
                    if not self._inb(nr, nc):
                        continue
                    if self.dom[nr][nc] == 2:
                        self._last_fail = f"adjacent black cells at ({r},{c}) and ({nr},{nc})"
                        return False
                    if self.dom[nr][nc] == 3:
                        if not self._force(nr, nc, 0):
                            return False
                        changed = True
        return changed

    def _duplicate_rules(self) -> bool:
        changed = False

        for (r, v), cols in self.row_groups.items():
            white_cols = [c for c in cols if self.dom[r][c] == 1]
            if len(white_cols) > 1:
                self._last_fail = f"row {r} has duplicate white value {v}"
                return False
            if len(white_cols) == 1:
                keep = white_cols[0]
                for c in cols:
                    if c == keep:
                        continue
                    if self.dom[r][c] != 2:
                        if not self._force(r, c, 1):
                            return False
                        changed = True

        for (c, v), rows in self.col_groups.items():
            white_rows = [r for r in rows if self.dom[r][c] == 1]
            if len(white_rows) > 1:
                self._last_fail = f"col {c} has duplicate white value {v}"
                return False
            if len(white_rows) == 1:
                keep = white_rows[0]
                for r in rows:
                    if r == keep:
                        continue
                    if self.dom[r][c] != 2:
                        if not self._force(r, c, 1):
                            return False
                        changed = True

        return changed

    def _white_connectivity_feasible(self) -> bool:
        pot = [(r, c) for r in range(self.n) for c in range(self.n) if self.dom[r][c] & 1]
        if not pot:
            self._last_fail = "no potential white cells"
            return False

        fixed = [(r, c) for r in range(self.n) for c in range(self.n) if self.dom[r][c] == 1]
        if not fixed:
            return True

        start = fixed[0]
        q = deque([start])
        seen = {start}
        while q:
            r, c = q.popleft()
            for dr, dc in self.DIR4:
                nr, nc = r + dr, c + dc
                if self._inb(nr, nc) and (self.dom[nr][nc] & 1) and (nr, nc) not in seen:
                    seen.add((nr, nc))
                    q.append((nr, nc))

        for p in fixed:
            if p not in seen:
                self._last_fail = "fixed white cells disconnected"
                return False
        return True

    def _probe_forcing(self) -> bool:
        changed = False
        for r in range(self.n):
            for c in range(self.n):
                if self.dom[r][c] != 3:
                    continue

                fail_black = False
                snap = self._snapshot()
                if not self._force(r, c, 1):
                    fail_black = True
                else:
                    fail_black = not self._propagate(enable_probe=False)
                self._restore(snap)

                fail_white = False
                snap = self._snapshot()
                if not self._force(r, c, 0):
                    fail_white = True
                else:
                    fail_white = not self._propagate(enable_probe=False)
                self._restore(snap)

                if fail_black and fail_white:
                    self._last_fail = f"both colors fail at ({r},{c})"
                    return False
                if fail_black:
                    if not self._force(r, c, 0):
                        return False
                    changed = True
                elif fail_white:
                    if not self._force(r, c, 1):
                        return False
                    changed = True
        return changed

    def _propagate(self, enable_probe: bool) -> bool:
        self._last_fail = ""
        while True:
            changed = False

            ad = self._adjacency_rules()
            if ad is False and self._last_fail:
                return False
            changed = changed or ad

            dp = self._duplicate_rules()
            if dp is False and self._last_fail:
                return False
            changed = changed or dp

            if not self._white_connectivity_feasible():
                return False

            if not changed and enable_probe:
                pb = self._probe_forcing()
                if pb is False and self._last_fail:
                    return False
                changed = changed or pb

            if not changed:
                break

        return True

    def _check_final(self) -> bool:
        if any(self.dom[r][c] == 3 for r in range(self.n) for c in range(self.n)):
            self._last_fail = "unresolved cells remain"
            return False

        for r in range(self.n):
            for c in range(self.n):
                if self.dom[r][c] != 2:
                    continue
                for dr, dc in self.DIR4:
                    nr, nc = r + dr, c + dc
                    if self._inb(nr, nc) and self.dom[nr][nc] == 2:
                        self._last_fail = "adjacent black cells in final"
                        return False

        for r in range(self.n):
            seen = set()
            for c in range(self.n):
                if self.dom[r][c] == 2:
                    continue
                v = self.grid[r][c]
                if v in seen:
                    self._last_fail = f"row {r} duplicate white {v}"
                    return False
                seen.add(v)

        for c in range(self.n):
            seen = set()
            for r in range(self.n):
                if self.dom[r][c] == 2:
                    continue
                v = self.grid[r][c]
                if v in seen:
                    self._last_fail = f"col {c} duplicate white {v}"
                    return False
                seen.add(v)

        whites = [(r, c) for r in range(self.n) for c in range(self.n) if self.dom[r][c] == 1]
        if not whites:
            self._last_fail = "no white cells"
            return False

        q = deque([whites[0]])
        seen = {whites[0]}
        while q:
            r, c = q.popleft()
            for dr, dc in self.DIR4:
                nr, nc = r + dr, c + dc
                if self._inb(nr, nc) and self.dom[nr][nc] == 1 and (nr, nc) not in seen:
                    seen.add((nr, nc))
                    q.append((nr, nc))

        if len(seen) != len(whites):
            self._last_fail = "white cells disconnected in final"
            return False

        return True

    def _build_answer(self) -> GridBW:
        return [["B" if self.dom[r][c] == 2 else None for c in range(self.n)] for r in range(self.n)]

    def _choose_branch(self):
        best = None
        best_key = None
        for r in range(self.n):
            for c in range(self.n):
                if self.dom[r][c] != 3:
                    continue
                conflict = 0
                v = self.grid[r][c]
                conflict += sum(1 for j in range(self.n) if j != c and self.grid[r][j] == v)
                conflict += sum(1 for i in range(self.n) if i != r and self.grid[i][c] == v)
                key = (-conflict, r, c)
                if best_key is None or key < best_key:
                    best_key = key
                    best = (r, c)
        return best

    def _search_one(self, depth: int, depth_limit: Optional[int], use_cache: bool):
        key = self._state_key()
        if use_cache and key in self._dead_cache:
            return None

        if not self._propagate(enable_probe=True):
            if use_cache:
                self._dead_cache.add(key)
            return None
        if self._check_final():
            return self._build_answer()
        if depth_limit is not None and depth >= depth_limit:
            return None

        pos = self._choose_branch()
        if pos is None:
            if use_cache:
                self._dead_cache.add(key)
            return None
        r, c = pos

        for token in (1, 0):
            snap = self._snapshot()
            if self._force(r, c, token):
                ans = self._search_one(depth + 1, depth_limit, use_cache)
                if ans is not None:
                    return ans
            self._restore(snap)

        if use_cache:
            self._dead_cache.add(self._state_key())
        return None

    def solve_staged(self):
        snap0 = self._snapshot()
        if self._propagate(enable_probe=True) and self._check_final():
            ans0 = self._build_answer()
            self._restore(snap0)
            return ans0
        self._restore(snap0)

        for cap in (3, 6):
            snap = self._snapshot()
            ans = self._search_one(0, cap, use_cache=False)
            self._restore(snap)
            if ans is not None:
                return ans

        self._dead_cache.clear()
        snapf = self._snapshot()
        ans = self._search_one(0, None, use_cache=True)
        self._restore(snapf)
        return ans


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict) and "original_data" in obs and isinstance(obs["original_data"], dict):
        obs = obs["original_data"].get("data")

    if isinstance(obs, dict) and "data" in obs:
        obs = obs["data"]

    if not isinstance(obs, list) or not obs or not isinstance(obs[0], list):
        raise ValueError("hitori observation must be a 2D grid")

    n = len(obs)
    if any(len(row) != n for row in obs):
        raise ValueError("hitori grid must be square")

    return [[int(v) for v in row] for row in obs]


def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 8000,
    log_level: str = "brief",
):
    del verbose, max_logs, log_level

    grid = _normalize_observation(observation)
    solver = _HitoriSolver(grid)
    answer = solver.solve_staged()
    return answer if answer is not None else "No Solution"
