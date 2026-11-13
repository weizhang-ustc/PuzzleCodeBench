from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

Pos = Tuple[int, int]
GridNum = List[List[int]]


class LatinRegionSolver:
    def __init__(
        self,
        givens: List[List[Optional[int]]],
        region_of: List[List[int]],
        verbose: bool,
        max_logs: int,
        log_level: str,
    ):
        del verbose, max_logs, log_level

        self.n = len(givens)
        self.givens = [row[:] for row in givens]
        self.region_of = [row[:] for row in region_of]
        self._last_fail = ""

        vals = set(range(1, self.n + 1))
        self.domains: List[List[Set[int]]] = [[set(vals) for _ in range(self.n)] for _ in range(self.n)]

        self.region_cells: Dict[int, List[Pos]] = {}
        for r in range(self.n):
            if len(self.givens[r]) != self.n or len(self.region_of[r]) != self.n:
                raise ValueError("givens/regions must be square n x n")
            for c in range(self.n):
                rid = self.region_of[r][c]
                self.region_cells.setdefault(rid, []).append((r, c))

        for rid, cells in self.region_cells.items():
            if len(cells) != self.n:
                raise ValueError(f"region {rid} size is {len(cells)} but expected {self.n}")

        for r in range(self.n):
            for c in range(self.n):
                v = self.givens[r][c]
                if v is None:
                    continue
                if not isinstance(v, int) or not (1 <= v <= self.n):
                    raise ValueError(f"invalid given at ({r},{c}): {v}")
                self.domains[r][c] = {v}

        self.row_units = [[(r, c) for c in range(self.n)] for r in range(self.n)]
        self.col_units = [[(r, c) for r in range(self.n)] for c in range(self.n)]
        self.region_ids = sorted(self.region_cells)
        self.reg_units = [self.region_cells[rid] for rid in self.region_ids]
        self.units = self.row_units + self.col_units + self.reg_units

    def _snapshot(self):
        return ([[set(s) for s in row] for row in self.domains], self._last_fail)

    def _restore(self, snap):
        self.domains, self._last_fail = snap

    def _unit_feasible(self) -> bool:
        n = self.n
        domains = self.domains

        for unit in self.units:
            seen_fixed = set()
            support = [0] * (n + 1)
            for r, c in unit:
                d = domains[r][c]
                if len(d) == 1:
                    v = next(iter(d))
                    if v in seen_fixed:
                        self._last_fail = f"duplicate fixed values in unit {unit}"
                        return False
                    seen_fixed.add(v)
                for v in d:
                    support[v] = 1
            for v in range(1, n + 1):
                if support[v] == 0:
                    self._last_fail = f"value {v} has no place in unit {unit}"
                    return False
        return True

    def _eliminate_by_fixed(self) -> bool:
        changed = False
        domains = self.domains
        for unit in self.units:
            fixed = {next(iter(domains[r][c])) for r, c in unit if len(domains[r][c]) == 1}
            for r, c in unit:
                d = domains[r][c]
                if len(d) == 1:
                    continue
                nd = d - fixed
                if not nd:
                    self._last_fail = f"empty domain at ({r},{c}) after elimination"
                    return False
                if nd != d:
                    domains[r][c] = nd
                    changed = True
        return changed

    def _hidden_singles(self) -> bool:
        changed = False
        n = self.n
        domains = self.domains

        for unit in self.units:
            count = [0] * (n + 1)
            last_pos: List[Optional[Pos]] = [None] * (n + 1)
            for r, c in unit:
                for v in domains[r][c]:
                    count[v] += 1
                    last_pos[v] = (r, c)

            for v in range(1, n + 1):
                if count[v] == 0:
                    self._last_fail = f"value {v} absent in unit {unit}"
                    return False
                if count[v] == 1:
                    pos = last_pos[v]
                    if pos is None:
                        self._last_fail = f"value {v} absent in unit {unit}"
                        return False
                    r, c = pos
                    if len(domains[r][c]) > 1:
                        domains[r][c] = {v}
                        changed = True
        return changed

    def _propagate(self) -> bool:
        self._last_fail = ""
        while True:
            changed = False

            if not self._unit_feasible():
                return False

            rc = self._eliminate_by_fixed()
            if rc is False and self._last_fail:
                return False
            changed = changed or rc

            hs = self._hidden_singles()
            if hs is False and self._last_fail:
                return False
            changed = changed or hs

            if not changed:
                break
        return True

    def _is_complete(self) -> bool:
        return all(len(self.domains[r][c]) == 1 for r in range(self.n) for c in range(self.n))

    def _build_answer(self) -> GridNum:
        return [[next(iter(self.domains[r][c])) for c in range(self.n)] for r in range(self.n)]

    def _choose_branch(self):
        best = None
        best_key = None

        row_unfixed = [sum(1 for c in range(self.n) if len(self.domains[r][c]) > 1) for r in range(self.n)]
        col_unfixed = [sum(1 for r in range(self.n) if len(self.domains[r][c]) > 1) for c in range(self.n)]
        reg_unfixed: Dict[int, int] = {
            rid: sum(1 for rr, cc in cells if len(self.domains[rr][cc]) > 1)
            for rid, cells in self.region_cells.items()
        }

        for r in range(self.n):
            for c in range(self.n):
                d = self.domains[r][c]
                if len(d) <= 1:
                    continue
                reg = self.region_of[r][c]
                impact = row_unfixed[r] + col_unfixed[c] + reg_unfixed[reg]
                key = (len(d), -impact)
                if best_key is None or key < best_key:
                    best_key = key
                    best = (r, c, sorted(d))

        return best if best is not None else (-1, -1, [])

    def _search_one(self, depth: int, depth_limit: Optional[int]):
        ok = self._propagate()
        if not ok:
            return None
        if self._is_complete():
            return self._build_answer()
        if depth_limit is not None and depth >= depth_limit:
            self._last_fail = f"depth limit reached at d={depth}"
            return None

        r, c, vals = self._choose_branch()
        if not vals:
            return None

        fails = []
        for v in vals:
            snap = self._snapshot()
            self.domains[r][c] = {v}
            ans = self._search_one(depth + 1, depth_limit)
            if ans is not None:
                return ans
            fails.append(self._last_fail or "branch failed")
            self._restore(snap)

        self._last_fail = f"all branches failed at ({r},{c}): {' ; '.join(fails[:2])}"
        return None

    def solve_staged(self):
        snap0 = self._snapshot()
        ok0 = self._propagate()
        if ok0 and self._is_complete():
            ans0 = self._build_answer()
            self._restore(snap0)
            return ans0, []
        self._restore(snap0)

        for cap in (3, 6):
            snap = self._snapshot()
            ans = self._search_one(0, cap)
            self._restore(snap)
            if ans is not None:
                return ans, []

        snapf = self._snapshot()
        ans = self._search_one(0, None)
        self._restore(snapf)
        return ans, []
