from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Optional, Set, Tuple

Pos = Tuple[int, int]
GridBW = List[List[str]]


@lru_cache(maxsize=None)
def _all_patterns(n: int) -> Tuple[Tuple[int, ...], ...]:
    if n % 2 != 0 or n <= 0:
        return tuple()
    half = n // 2
    out: List[Tuple[int, ...]] = []

    def dfs(i: int, b: int, w: int, arr: List[int]):
        if i == n:
            if b == half and w == half:
                out.append(tuple(arr))
            return
        for v in (0, 1):
            if v == 1 and b >= half:
                continue
            if v == 0 and w >= half:
                continue
            if i >= 2 and arr[i - 1] == arr[i - 2] == v:
                continue
            arr.append(v)
            dfs(i + 1, b + (v == 1), w + (v == 0), arr)
            arr.pop()

    dfs(0, 0, 0, [])
    return tuple(out)


def _norm_cell(v) -> Optional[int]:
    if v is None:
        return None
    s = str(v).strip().upper()
    if s == "B":
        return 1
    if s == "W":
        return 0
    return None


def _normalize_observation(observation):
    data = observation
    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]
        elif "original_data" in data and isinstance(data["original_data"], dict):
            data = data["original_data"].get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError("binairo observation must be a non-empty 2D grid")
    n = len(data)
    if any(len(row) != n for row in data):
        raise ValueError("binairo grid must be square")
    return [[_norm_cell(v) for v in row] for row in data]


class _BinairoSolver:
    def __init__(self, clue_grid):
        self.n = len(clue_grid)
        self.givens = clue_grid

        self.patterns = list(_all_patterns(self.n))
        if not self.patterns:
            raise ValueError("binairo size must be positive and even")

        all_idx = set(range(len(self.patterns)))
        self.row_domains: List[Set[int]] = [set(all_idx) for _ in range(self.n)]
        self.col_domains: List[Set[int]] = [set(all_idx) for _ in range(self.n)]
        self.cell_mask = [[3 for _ in range(self.n)] for _ in range(self.n)]
        for r in range(self.n):
            for c in range(self.n):
                g = self.givens[r][c]
                if g is None:
                    continue
                self.cell_mask[r][c] = 1 if g == 0 else 2

    def _snapshot(self):
        return [set(d) for d in self.row_domains], [set(d) for d in self.col_domains], [row[:] for row in self.cell_mask]

    def _restore(self, snap):
        self.row_domains, self.col_domains, self.cell_mask = snap

    def _mask_from_row_domain(self, r: int, c: int) -> int:
        m = 0
        for pid in self.row_domains[r]:
            m |= 1 if self.patterns[pid][c] == 0 else 2
            if m == 3:
                return 3
        return m

    def _mask_from_col_domain(self, r: int, c: int) -> int:
        m = 0
        for pid in self.col_domains[c]:
            m |= 1 if self.patterns[pid][r] == 0 else 2
            if m == 3:
                return 3
        return m

    def _prune_row_domains(self) -> Tuple[bool, bool]:
        changed = False
        for r in range(self.n):
            nd = set()
            for pid in self.row_domains[r]:
                pat = self.patterns[pid]
                ok = True
                for c in range(self.n):
                    bit = 1 if pat[c] == 0 else 2
                    if self.cell_mask[r][c] & bit == 0:
                        ok = False
                        break
                if ok:
                    nd.add(pid)
            if not nd:
                return False, False
            if nd != self.row_domains[r]:
                self.row_domains[r] = nd
                changed = True
        return True, changed

    def _prune_col_domains(self) -> Tuple[bool, bool]:
        changed = False
        for c in range(self.n):
            nd = set()
            for pid in self.col_domains[c]:
                pat = self.patterns[pid]
                ok = True
                for r in range(self.n):
                    bit = 1 if pat[r] == 0 else 2
                    if self.cell_mask[r][c] & bit == 0:
                        ok = False
                        break
                if ok:
                    nd.add(pid)
            if not nd:
                return False, False
            if nd != self.col_domains[c]:
                self.col_domains[c] = nd
                changed = True
        return True, changed

    def _apply_line_uniqueness(self) -> Tuple[bool, bool]:
        changed = False

        fixed_rows: Dict[int, int] = {}
        for r in range(self.n):
            if len(self.row_domains[r]) == 1:
                pid = next(iter(self.row_domains[r]))
                if pid in fixed_rows:
                    return False, False
                fixed_rows[pid] = r
        for pid, rr in fixed_rows.items():
            for r in range(self.n):
                if r == rr or len(self.row_domains[r]) == 1:
                    continue
                if pid in self.row_domains[r]:
                    self.row_domains[r].remove(pid)
                    if not self.row_domains[r]:
                        return False, False
                    changed = True

        fixed_cols: Dict[int, int] = {}
        for c in range(self.n):
            if len(self.col_domains[c]) == 1:
                pid = next(iter(self.col_domains[c]))
                if pid in fixed_cols:
                    return False, False
                fixed_cols[pid] = c
        for pid, cc in fixed_cols.items():
            for c in range(self.n):
                if c == cc or len(self.col_domains[c]) == 1:
                    continue
                if pid in self.col_domains[c]:
                    self.col_domains[c].remove(pid)
                    if not self.col_domains[c]:
                        return False, False
                    changed = True

        return True, changed

    def _sync_cells_from_domains(self) -> Tuple[bool, bool]:
        changed = False
        for r in range(self.n):
            for c in range(self.n):
                nm = self.cell_mask[r][c] & self._mask_from_row_domain(r, c) & self._mask_from_col_domain(r, c)
                if nm == 0:
                    return False, False
                if nm != self.cell_mask[r][c]:
                    self.cell_mask[r][c] = nm
                    changed = True
        return True, changed

    def _propagate(self) -> bool:
        while True:
            changed = False

            ok, ch = self._prune_row_domains()
            if not ok:
                return False
            changed = changed or ch

            ok, ch = self._prune_col_domains()
            if not ok:
                return False
            changed = changed or ch

            ok, ch = self._apply_line_uniqueness()
            if not ok:
                return False
            changed = changed or ch

            ok, ch = self._sync_cells_from_domains()
            if not ok:
                return False
            changed = changed or ch

            if not changed:
                return True

    def _is_complete(self) -> bool:
        return all(len(d) == 1 for d in self.row_domains) and all(len(d) == 1 for d in self.col_domains)

    def _build_answer(self) -> GridBW:
        out: GridBW = [["W"] * self.n for _ in range(self.n)]
        for r in range(self.n):
            pat = self.patterns[next(iter(self.row_domains[r]))]
            for c in range(self.n):
                out[r][c] = "B" if pat[c] == 1 else "W"
        return out

    def _choose_branch(self) -> Tuple[str, int, List[int]]:
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

    def _search(self):
        if not self._propagate():
            return None
        if self._is_complete():
            return self._build_answer()

        kind, idx, vals = self._choose_branch()
        if not vals:
            return None

        for pid in vals:
            snap = self._snapshot()
            if kind == "row":
                self.row_domains[idx] = {pid}
            else:
                self.col_domains[idx] = {pid}
            ans = self._search()
            if ans is not None:
                return ans
            self._restore(snap)
        return None

    def solve(self):
        return self._search()


def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 8000,
    log_level: str = "brief",
):
    del verbose, max_logs, log_level
    clue_grid = _normalize_observation(observation)
    solver = _BinairoSolver(clue_grid)
    answer = solver.solve()
    return answer if answer is not None else "No Solution"
