from __future__ import annotations

from typing import List, Optional, Set, Tuple

Pos = Tuple[int, int]
GridNum = List[List[int]]


class _RenzokuSolver:
    def __init__(self, givens, adjacent):
        self.n = len(givens)
        self.givens = [row[:] for row in givens]
        self.adjacent = set(adjacent)
        self._last_fail = ""

        vals = set(range(1, self.n + 1))
        self.domains = [[set(vals) for _ in range(self.n)] for _ in range(self.n)]
        self.known = [[None for _ in range(self.n)] for _ in range(self.n)]
        for r in range(self.n):
            if len(self.givens[r]) != self.n:
                raise ValueError("renzoku grid must be square")
            for c in range(self.n):
                v = self.givens[r][c]
                if v is not None:
                    iv = int(v)
                    self.domains[r][c] = {iv}
                    self.known[r][c] = iv

        self.edges: List[Tuple[Pos, Pos, bool]] = []
        for r in range(self.n):
            for c in range(self.n - 1):
                self.edges.append(((r, c), (r, c + 1), (float(r), c + 0.5) in self.adjacent))
        for r in range(self.n - 1):
            for c in range(self.n):
                self.edges.append(((r, c), (r + 1, c), (r + 0.5, float(c)) in self.adjacent))

    def _snapshot(self):
        return ([[set(s) for s in row] for row in self.domains], [row[:] for row in self.known], self._last_fail)

    def _restore(self, snap):
        self.domains, self.known, self._last_fail = snap

    def _units(self):
        for r in range(self.n):
            yield [(r, c) for c in range(self.n)], f"row {r}"
        for c in range(self.n):
            yield [(r, c) for r in range(self.n)], f"col {c}"

    @staticmethod
    def _supported(va: int, vb: int, consecutive: bool) -> bool:
        return (abs(va - vb) == 1) if consecutive else (abs(va - vb) != 1)

    def _record_new_fixed(self) -> bool:
        changed = False
        for r in range(self.n):
            for c in range(self.n):
                if len(self.domains[r][c]) != 1:
                    continue
                v = next(iter(self.domains[r][c]))
                if self.known[r][c] == v:
                    continue
                self.known[r][c] = v
                changed = True
        return changed

    def _unit_feasible(self) -> bool:
        for cells, name in self._units():
            fixed = [next(iter(self.domains[r][c])) for r, c in cells if len(self.domains[r][c]) == 1]
            if len(set(fixed)) != len(fixed):
                self._last_fail = f"duplicate fixed value in {name}"
                return False
            for v in range(1, self.n + 1):
                if not any(v in self.domains[r][c] for r, c in cells):
                    self._last_fail = f"value {v} has no place in {name}"
                    return False
        return True

    def _eliminate_latin(self) -> bool:
        changed = False
        for cells, name in self._units():
            fixed = {next(iter(self.domains[r][c])) for r, c in cells if len(self.domains[r][c]) == 1}
            for r, c in cells:
                if len(self.domains[r][c]) == 1:
                    continue
                nd = self.domains[r][c] - fixed
                if not nd:
                    self._last_fail = f"empty domain at ({r},{c}) after {name} elimination"
                    return False
                if nd != self.domains[r][c]:
                    self.domains[r][c] = nd
                    changed = True
        return changed

    def _hidden_single(self) -> bool:
        changed = False
        for cells, name in self._units():
            for v in range(1, self.n + 1):
                spots = [(r, c) for r, c in cells if v in self.domains[r][c]]
                if not spots:
                    self._last_fail = f"value {v} absent from {name}"
                    return False
                if len(spots) == 1:
                    r, c = spots[0]
                    if self.domains[r][c] != {v}:
                        self.domains[r][c] = {v}
                        changed = True
        return changed

    def _pair_prune(self) -> bool:
        changed = False
        for a, b, consecutive in self.edges:
            ra, ca = a
            rb, cb = b
            da = self.domains[ra][ca]
            db = self.domains[rb][cb]
            nda = {va for va in da if any(self._supported(va, vb, consecutive) for vb in db)}
            ndb = {vb for vb in db if any(self._supported(va, vb, consecutive) for va in da)}
            if not nda or not ndb:
                self._last_fail = f"adjacency contradiction between {a} and {b}"
                return False
            if nda != da:
                self.domains[ra][ca] = nda
                changed = True
            if ndb != db:
                self.domains[rb][cb] = ndb
                changed = True
        return changed

    def _propagate(self):
        self._last_fail = ""
        while True:
            changed = False
            if not self._unit_feasible():
                return False
            for step in (self._eliminate_latin, self._hidden_single, self._pair_prune):
                ok = step()
                if ok is False and self._last_fail:
                    return False
                changed = changed or ok
            changed = self._record_new_fixed() or changed
            if not changed:
                break
        return True

    def _is_complete(self) -> bool:
        return all(len(self.domains[r][c]) == 1 for r in range(self.n) for c in range(self.n))

    def _build_answer(self) -> GridNum:
        return [[next(iter(self.domains[r][c])) for c in range(self.n)] for r in range(self.n)]

    def _final_valid(self) -> bool:
        grid = self._build_answer()
        vals = set(range(1, self.n + 1))
        for r in range(self.n):
            if set(grid[r]) != vals:
                self._last_fail = f"row {r} invalid in final"
                return False
        for c in range(self.n):
            if set(grid[r][c] for r in range(self.n)) != vals:
                self._last_fail = f"col {c} invalid in final"
                return False
        for a, b, consecutive in self.edges:
            va = grid[a[0]][a[1]]
            vb = grid[b[0]][b[1]]
            if not self._supported(va, vb, consecutive):
                self._last_fail = f"adjacency mismatch on {a}-{b}"
                return False
        return True

    def _choose_branch(self):
        best = None
        best_vals = []
        best_key = None
        for r in range(self.n):
            for c in range(self.n):
                d = self.domains[r][c]
                if len(d) <= 1:
                    continue
                deg = sum(1 for a, b, _ in self.edges if a == (r, c) or b == (r, c))
                key = (len(d), -deg, r, c)
                if best_key is None or key < best_key:
                    best_key = key
                    best = (r, c)
                    best_vals = sorted(d)
        return best, best_vals

    def _search_one(self, depth: int, depth_limit: Optional[int], stage: str):
        ok = self._propagate()
        if not ok:
            return None
        if self._is_complete():
            return self._build_answer() if self._final_valid() else None
        if depth_limit is not None and depth >= depth_limit:
            self._last_fail = f"depth limit reached at d={depth}"
            return None
        pos, vals = self._choose_branch()
        if pos is None:
            return None
        r, c = pos
        fails = []
        for v in vals:
            snap = self._snapshot()
            self.domains[r][c] = {v}
            self._record_new_fixed()
            ans = self._search_one(depth + 1, depth_limit, stage)
            if ans is not None:
                return ans
            fails.append(self._last_fail or "branch failed")
            self._restore(snap)
        self._last_fail = f"all branches failed at ({r},{c}): {' ; '.join(fails[:2])}"
        return None

    def solve_staged(self):
        for cap in (0, 3, 6, None):
            snap = self._snapshot()
            stage = "rules-only" if cap == 0 else (f"short-depth({cap})" if cap is not None else "full-search")
            ans = self._search_one(0, cap, stage)
            self._restore(snap)
            if ans is not None:
                return ans
        return None


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict) and "original_data" in obs and isinstance(obs["original_data"], dict):
        obs = obs["original_data"]
    if not isinstance(obs, dict):
        raise ValueError("renzoku observation must be dict")
    data = obs.get("data")
    adjacent = obs.get("adjacent", [])
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError("renzoku data must be 2D list")
    n = len(data)
    if any(len(row) != n for row in data):
        raise ValueError("renzoku grid must be square")
    return [[None if v is None else int(v) for v in row] for row in data], [(float(r), float(c)) for r, c in adjacent]


def solve(observation, verbose: bool = False, max_logs: int = 8000, log_level: str = "brief"):
    if log_level not in {"brief", "full"}:
        raise ValueError("log_level must be 'brief' or 'full'")
    givens, adjacent = _normalize_observation(observation)
    solver = _RenzokuSolver(givens, adjacent)
    answer = solver.solve_staged()
    if answer is None:
        return "No Solution"
    return answer
