from __future__ import annotations

from typing import List, Optional, Set, Tuple

Pos = Tuple[int, int]
GridBW = List[List[Optional[str]]]


class _KakurasuSolver:
    def __init__(self, row_sum: List[int], col_sum: List[int]):
        self.n = len(row_sum)
        self.row_sum = list(row_sum)
        self.col_sum = list(col_sum)
        if len(self.col_sum) != self.n:
            raise ValueError("row_sum/col_sum length mismatch")
        self.row_w = [i + 1 for i in range(self.n)]
        self.col_w = [i + 1 for i in range(self.n)]

        self._last_fail = ""

        all_row = self._patterns_for_target(self.col_w, self.row_sum)
        all_col = self._patterns_for_target(self.row_w, self.col_sum)
        self.row_domains: List[Set[int]] = [set(pats) for pats in all_row]
        self.col_domains: List[Set[int]] = [set(pats) for pats in all_col]
        if any(not d for d in self.row_domains) or any(not d for d in self.col_domains):
            raise ValueError("invalid kakurasu sums")

        self.cell_mask = [[3 for _ in range(self.n)] for _ in range(self.n)]

    def _snapshot(self):
        return (
            [set(d) for d in self.row_domains],
            [set(d) for d in self.col_domains],
            [row[:] for row in self.cell_mask],
            self._last_fail,
        )

    def _restore(self, snap):
        self.row_domains, self.col_domains, self.cell_mask, self._last_fail = snap

    def _patterns_for_target(self, weights: List[int], targets: List[int]) -> List[List[int]]:
        n = len(weights)
        all_masks = []
        for t in targets:
            pats = []
            for m in range(1 << n):
                s = 0
                for i in range(n):
                    if (m >> i) & 1:
                        s += weights[i]
                if s == t:
                    pats.append(m)
            all_masks.append(pats)
        return all_masks

    def _row_possible_mask(self, r: int, c: int) -> int:
        m = 0
        bit = 1 << c
        for pat in self.row_domains[r]:
            m |= 2 if (pat & bit) else 1
            if m == 3:
                return 3
        return m

    def _col_possible_mask(self, r: int, c: int) -> int:
        m = 0
        bit = 1 << r
        for pat in self.col_domains[c]:
            m |= 2 if (pat & bit) else 1
            if m == 3:
                return 3
        return m

    def _prune_row_domains(self) -> bool:
        changed = False
        for r in range(self.n):
            nd = set()
            for pat in self.row_domains[r]:
                ok = True
                for c in range(self.n):
                    bit = 2 if ((pat >> c) & 1) else 1
                    if self.cell_mask[r][c] & bit == 0:
                        ok = False
                        break
                if ok:
                    nd.add(pat)
            if not nd:
                self._last_fail = f"row {r} has no feasible pattern"
                return False
            if nd != self.row_domains[r]:
                self.row_domains[r] = nd
                changed = True
        return changed

    def _prune_col_domains(self) -> bool:
        changed = False
        for c in range(self.n):
            nd = set()
            for pat in self.col_domains[c]:
                ok = True
                for r in range(self.n):
                    bit = 2 if ((pat >> r) & 1) else 1
                    if self.cell_mask[r][c] & bit == 0:
                        ok = False
                        break
                if ok:
                    nd.add(pat)
            if not nd:
                self._last_fail = f"col {c} has no feasible pattern"
                return False
            if nd != self.col_domains[c]:
                self.col_domains[c] = nd
                changed = True
        return changed

    def _sync_cells(self) -> bool:
        changed = False
        for r in range(self.n):
            for c in range(self.n):
                m = self._row_possible_mask(r, c) & self._col_possible_mask(r, c) & self.cell_mask[r][c]
                if m == 0:
                    self._last_fail = f"cell ({r},{c}) impossible"
                    return False
                if m != self.cell_mask[r][c]:
                    self.cell_mask[r][c] = m
                    changed = True
        return changed

    def _propagate(self) -> bool:
        self._last_fail = ""
        while True:
            changed = False

            rr = self._prune_row_domains()
            if rr is False and self._last_fail:
                return False
            changed = changed or rr

            cc = self._prune_col_domains()
            if cc is False and self._last_fail:
                return False
            changed = changed or cc

            sc = self._sync_cells()
            if sc is False and self._last_fail:
                return False
            changed = changed or sc

            if not changed:
                break

        return True

    def _is_complete(self) -> bool:
        return all(m in (1, 2) for row in self.cell_mask for m in row)

    def _build_answer(self) -> GridBW:
        out: GridBW = [[None for _ in range(self.n)] for _ in range(self.n)]
        for r in range(self.n):
            for c in range(self.n):
                out[r][c] = "B" if self.cell_mask[r][c] == 2 else None
        return out

    def _choose_branch(self):
        best = None
        best_key = None

        for r in range(self.n):
            if len(self.row_domains[r]) > 1:
                key = (len(self.row_domains[r]), 0)
                if best_key is None or key < best_key:
                    best_key = key
                    best = ("row", r, sorted(self.row_domains[r]))

        for c in range(self.n):
            if len(self.col_domains[c]) > 1:
                key = (len(self.col_domains[c]), 1)
                if best_key is None or key < best_key:
                    best_key = key
                    best = ("col", c, sorted(self.col_domains[c]))

        if best is None:
            return "", -1, []
        return best

    def _search_one(self, depth: int, depth_limit: Optional[int]):
        if not self._propagate():
            return None
        if self._is_complete():
            return self._build_answer()
        if depth_limit is not None and depth >= depth_limit:
            return None

        kind, idx, vals = self._choose_branch()
        if not vals:
            return None

        for v in vals:
            snap = self._snapshot()
            if kind == "row":
                self.row_domains[idx] = {v}
            else:
                self.col_domains[idx] = {v}
            self._sync_cells()
            ans = self._search_one(depth + 1, depth_limit)
            if ans is not None:
                return ans
            self._restore(snap)

        return None

    def solve_staged(self):
        snap0 = self._snapshot()
        if self._propagate() and self._is_complete():
            ans0 = self._build_answer()
            self._restore(snap0)
            return ans0
        self._restore(snap0)

        for cap in (3, 6):
            snap = self._snapshot()
            ans = self._search_one(0, cap)
            self._restore(snap)
            if ans is not None:
                return ans

        snapf = self._snapshot()
        ans = self._search_one(0, None)
        self._restore(snapf)
        return ans


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict) and "original_data" in obs and isinstance(obs["original_data"], dict):
        obs = obs["original_data"]

    if not isinstance(obs, dict):
        raise ValueError("kakurasu observation must be dict")

    row_sum = obs.get("row_sum")
    col_sum = obs.get("col_sum")
    if row_sum is None or col_sum is None:
        raise ValueError("kakurasu needs row_sum and col_sum")

    return [int(v) for v in row_sum], [int(v) for v in col_sum]


def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 8000,
    log_level: str = "brief",
):
    del verbose, max_logs, log_level

    row_sum, col_sum = _normalize_observation(observation)
    solver = _KakurasuSolver(row_sum, col_sum)
    answer = solver.solve_staged()
    return answer if answer is not None else "No Solution"
