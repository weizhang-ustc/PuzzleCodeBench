from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Tuple

Grid = List[List[str]]


@lru_cache(maxsize=None)
def _row_patterns(n: int) -> Tuple[Tuple[int, ...], ...]:
    if n <= 0 or n % 2 != 0:
        return tuple()
    half = n // 2
    out: List[Tuple[int, ...]] = []

    def dfs(i: int, ones: int, arr: List[int]):
        if i == n:
            if ones == half:
                out.append(tuple(arr))
            return
        for v in (0, 1):
            if v == 1 and ones >= half:
                continue
            if i >= 2 and arr[i - 1] == arr[i - 2] == v:
                continue
            arr.append(v)
            dfs(i + 1, ones + v, arr)
            arr.pop()

    dfs(0, 0, [])
    return tuple(out)


def _norm(v):
    if v is None:
        return None
    s = str(v).strip().upper()
    if s == "B":
        return 1
    if s == "W":
        return 0
    return None


def _parse_mid(k):
    if isinstance(k, tuple) and len(k) == 2:
        return float(k[0]), float(k[1])
    if isinstance(k, str) and "," in k:
        a, b = k.split(",", 1)
        return float(a), float(b)
    raise ValueError(f"invalid key: {k}")


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict) and "original_data" in obs and isinstance(obs["original_data"], dict):
        obs = obs["original_data"]

    if not isinstance(obs, dict) or "data" not in obs:
        raise ValueError("binairoplus observation must include data")

    data = obs["data"]
    if not (isinstance(data, list) and data and isinstance(data[0], list)):
        raise ValueError("binairoplus data must be 2D grid")

    n = len(data)
    if any(len(row) != n for row in data):
        raise ValueError("binairoplus grid must be square")

    givens = [[_norm(v) for v in row] for row in data]

    h = obs.get("horizontal", {}) or {}
    v = obs.get("vertical", {}) or {}

    horiz: Dict[Tuple[int, int], bool] = {}
    vert: Dict[Tuple[int, int], bool] = {}

    for key, sym in h.items():
        r, c = _parse_mid(key)
        rr = int(round(r))
        c1 = int(round(c - 0.5))
        if 0 <= rr < n and 0 <= c1 < n - 1:
            s = str(sym).strip().lower()
            if s in {"=", "x"}:
                horiz[(rr, c1)] = s == "="

    for key, sym in v.items():
        r, c = _parse_mid(key)
        cc = int(round(c))
        r1 = int(round(r - 0.5))
        if 0 <= cc < n and 0 <= r1 < n - 1:
            s = str(sym).strip().lower()
            if s in {"=", "x"}:
                vert[(r1, cc)] = s == "="

    return givens, horiz, vert


class _Solver:
    def __init__(self, givens, horiz, vert):
        self.givens = givens
        self.horiz = horiz
        self.vert = vert
        self.n = len(givens)
        self._dead_cache = set()

        if self.n % 2 != 0:
            raise ValueError("binairoplus requires even board size")

        self.patterns = _row_patterns(self.n)
        if not self.patterns:
            raise ValueError("no row patterns")

        self.cell_mask = [[3 for _ in range(self.n)] for _ in range(self.n)]
        for r in range(self.n):
            for c in range(self.n):
                g = self.givens[r][c]
                if g is None:
                    continue
                self.cell_mask[r][c] = 1 if g == 0 else 2

        all_pids = range(len(self.patterns))
        self.row_domains = [set() for _ in range(self.n)]
        self.col_domains = [set() for _ in range(self.n)]

        for r in range(self.n):
            for pid in all_pids:
                pat = self.patterns[pid]
                ok = True
                for c in range(self.n):
                    g = self.givens[r][c]
                    if g is not None and pat[c] != g:
                        ok = False
                        break
                if not ok:
                    continue
                for c in range(self.n - 1):
                    same = self.horiz.get((r, c))
                    if same is None:
                        continue
                    if (pat[c] == pat[c + 1]) != same:
                        ok = False
                        break
                if ok:
                    self.row_domains[r].add(pid)
            if not self.row_domains[r]:
                raise ValueError(f"row {r} has no candidate")

        for c in range(self.n):
            for pid in all_pids:
                pat = self.patterns[pid]
                ok = True
                for r in range(self.n):
                    g = self.givens[r][c]
                    if g is not None and pat[r] != g:
                        ok = False
                        break
                if not ok:
                    continue
                for r in range(self.n - 1):
                    same = self.vert.get((r, c))
                    if same is None:
                        continue
                    if (pat[r] == pat[r + 1]) != same:
                        ok = False
                        break
                if ok:
                    self.col_domains[c].add(pid)
            if not self.col_domains[c]:
                raise ValueError(f"col {c} has no candidate")

    def _snapshot(self):
        return [set(d) for d in self.row_domains], [set(d) for d in self.col_domains], [row[:] for row in self.cell_mask]

    def _restore(self, snap):
        self.row_domains, self.col_domains, self.cell_mask = snap

    def _state_key(self):
        return (
            tuple(tuple(sorted(d)) for d in self.row_domains),
            tuple(tuple(sorted(d)) for d in self.col_domains),
            tuple(tuple(row) for row in self.cell_mask),
        )

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

    def _prune_row_domains(self):
        changed = False
        for r in range(self.n):
            nd = set()
            for pid in self.row_domains[r]:
                pat = self.patterns[pid]
                ok = True
                for c in range(self.n):
                    bit = 1 if pat[c] == 0 else 2
                    if (self.cell_mask[r][c] & bit) == 0:
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

    def _prune_col_domains(self):
        changed = False
        for c in range(self.n):
            nd = set()
            for pid in self.col_domains[c]:
                pat = self.patterns[pid]
                ok = True
                for r in range(self.n):
                    bit = 1 if pat[r] == 0 else 2
                    if (self.cell_mask[r][c] & bit) == 0:
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

    def _sync_cells_from_domains(self):
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

    def _propagate(self):
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

            ok, ch = self._sync_cells_from_domains()
            if not ok:
                return False
            changed = changed or ch

            if not changed:
                return True

    def _is_complete(self) -> bool:
        return all(len(d) == 1 for d in self.row_domains) and all(len(d) == 1 for d in self.col_domains)

    def _build_answer(self):
        out: Grid = [["W"] * self.n for _ in range(self.n)]
        for r in range(self.n):
            pat = self.patterns[next(iter(self.row_domains[r]))]
            for c in range(self.n):
                out[r][c] = "B" if pat[c] == 1 else "W"
        return out

    def _choose_branch(self):
        best = None
        best_key = None

        for r in range(self.n):
            dsz = len(self.row_domains[r])
            if dsz <= 1:
                continue
            key = (dsz, 0, r)
            if best_key is None or key < best_key:
                best_key = key
                best = ("row", r, sorted(self.row_domains[r]))

        for c in range(self.n):
            dsz = len(self.col_domains[c])
            if dsz <= 1:
                continue
            key = (dsz, 1, c)
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

        key = self._state_key()
        if key in self._dead_cache:
            return None

        kind, idx, vals = self._choose_branch()
        if not vals:
            self._dead_cache.add(key)
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

        self._dead_cache.add(key)
        return None

    def solve(self):
        return self._search()


def solve(observation, verbose: bool = False, max_logs: int = 8000, log_level: str = "brief"):
    del verbose, max_logs, log_level
    givens, horiz, vert = _normalize_observation(observation)
    solver = _Solver(givens, horiz, vert)
    ans = solver.solve()
    return ans if ans is not None else "No Solution"
