from __future__ import annotations

from typing import List, Optional, Set, Tuple

Pos = Tuple[int, int]
Grid = List[List[Optional[str]]]


class _StarBattleXSolver:
    def __init__(self, grid):
        self.n = len(grid)
        self.grid = [row[:] for row in grid]
        self._last_fail = ''
        self.domains = []
        self.known = [None] * self.n
        for r in range(self.n):
            if len(self.grid[r]) != self.n:
                raise ValueError('starbattlex grid must be square')
            allowed = {c for c in range(self.n) if self.grid[r][c] != 'B'}
            if not allowed:
                raise ValueError(f'row {r} has no legal star cell')
            self.domains.append(set(allowed))

    def _msg(self, brief: str, full: str) -> str:
        return brief

    def _snapshot(self):
        return ([set(d) for d in self.domains], self.known[:], self._last_fail)

    def _restore(self, snap):
        self.domains, self.known, self._last_fail = snap

    def _state_key(self):
        return tuple(tuple(sorted(d)) for d in self.domains)

    def _record_new_fixed(self, context: str, logs):
        changed = False
        for r in range(self.n):
            if len(self.domains[r]) != 1:
                continue
            c = next(iter(self.domains[r]))
            if self.known[r] == c:
                continue
            self.known[r] = c
            why = f"{context}: row {r} only allows col {c}"
            logs.append(('S', (r, c), why))
            changed = True
        return changed

    def _basic_feasible(self) -> bool:
        for r in range(self.n):
            if not self.domains[r]:
                self._last_fail = f'row {r} has empty domain'
                return False
        for c in range(self.n):
            if not any(c in self.domains[r] for r in range(self.n)):
                self._last_fail = f'column {c} has no possible star'
                return False
        return True

    def _propagate_fixed(self) -> bool:
        changed = False
        fixed = [(r, next(iter(self.domains[r]))) for r in range(self.n) if len(self.domains[r]) == 1]
        for r, c in fixed:
            for rr in range(self.n):
                if rr != r and c in self.domains[rr]:
                    self.domains[rr].discard(c)
                    changed = True
            for rr in (r - 1, r + 1):
                if 0 <= rr < self.n:
                    for cc in (c - 1, c, c + 1):
                        if 0 <= cc < self.n and cc in self.domains[rr] and len(self.domains[rr]) > 1:
                            self.domains[rr].discard(cc)
                            changed = True
        return changed

    def _hidden_column(self) -> bool:
        changed = False
        for c in range(self.n):
            spots = [r for r in range(self.n) if c in self.domains[r]]
            if not spots:
                self._last_fail = f'column {c} has no support'
                return False
            if len(spots) == 1:
                r = spots[0]
                if self.domains[r] != {c}:
                    self.domains[r] = {c}
                    changed = True
        return changed

    def _adjacency_pair_prune(self) -> bool:
        changed = False
        for r in range(self.n - 1):
            d1 = self.domains[r]
            d2 = self.domains[r + 1]
            nd1 = {c1 for c1 in d1 if any(abs(c1 - c2) > 1 for c2 in d2)}
            nd2 = {c2 for c2 in d2 if any(abs(c1 - c2) > 1 for c1 in d1)}
            if not nd1 or not nd2:
                self._last_fail = f'rows {r} and {r + 1} cannot avoid touching'
                return False
            if nd1 != d1:
                self.domains[r] = nd1
                changed = True
            if nd2 != d2:
                self.domains[r + 1] = nd2
                changed = True
        return changed

    def _matching_feasible(self) -> bool:
        match_to_row = {}

        def dfs(r: int, seen: Set[int]) -> bool:
            for c in sorted(self.domains[r]):
                if c in seen:
                    continue
                seen.add(c)
                if c not in match_to_row or dfs(match_to_row[c], seen):
                    match_to_row[c] = r
                    return True
            return False

        for r in range(self.n):
            if not dfs(r, set()):
                self._last_fail = 'row/column matching impossible'
                return False
        return True

    def _propagate(self):
        logs = []
        self._last_fail = ''
        while True:
            changed = False
            for step in (self._propagate_fixed, self._hidden_column, self._adjacency_pair_prune):
                ok = step()
                if ok is False and self._last_fail:
                    return False, logs
                changed = changed or ok
            if not self._basic_feasible() or not self._matching_feasible():
                return False, logs
            ctx = self._msg('row/column/adjacency forcing', 'obstacle filtering plus row/column uniqueness and neighbor-row king-adjacency forcing')
            changed = self._record_new_fixed(ctx, logs) or changed
            if not changed:
                break
        return True, logs

    def _is_complete(self) -> bool:
        return all(len(d) == 1 for d in self.domains)

    def _build_answer(self) -> Grid:
        out = [[None for _ in range(self.n)] for _ in range(self.n)]
        for r in range(self.n):
            out[r][next(iter(self.domains[r]))] = 'S'
        return out

    def _final_valid(self) -> bool:
        cols = set()
        prev = None
        for r in range(self.n):
            if len(self.domains[r]) != 1:
                self._last_fail = 'incomplete final state'
                return False
            c = next(iter(self.domains[r]))
            if c in cols:
                self._last_fail = f'duplicate column {c}'
                return False
            if self.grid[r][c] == 'B':
                self._last_fail = f'star on obstacle ({r},{c})'
                return False
            if prev is not None and abs(prev - c) <= 1:
                self._last_fail = f'adjacent stars on rows {r - 1},{r}'
                return False
            cols.add(c)
            prev = c
        return True

    def _choose_branch(self):
        best = None
        best_vals = []
        best_key = None
        for r in range(self.n):
            d = self.domains[r]
            if len(d) <= 1:
                continue
            pressure = sum(1 for rr in (r - 1, r + 1) if 0 <= rr < self.n)
            key = (len(d), -pressure, r)
            if best_key is None or key < best_key:
                best_key = key
                best = r
                best_vals = sorted(d)
        return best, best_vals

    def _search_one(self, depth: int, depth_limit: Optional[int], stage: str):
        ok, base_logs = self._propagate()
        if not ok:
            return None, []
        if self._is_complete():
            return (self._build_answer(), base_logs) if self._final_valid() else (None, [])
        if depth_limit is not None and depth >= depth_limit:
            self._last_fail = f'depth limit reached at d={depth}'
            return None, []
        r, vals = self._choose_branch()
        if r is None:
            return None, []
        fails = []
        for c in vals:
            snap = self._snapshot()
            branch_logs = []
            self.domains[r] = {c}
            ctx = self._msg(f'{stage} branch row {r}->col {c}', f'{stage} branch at depth {depth}: try placing row {r} in column {c}')
            self._record_new_fixed(ctx, branch_logs)
            ans, deeper = self._search_one(depth + 1, depth_limit, stage)
            if ans is not None:
                return ans, base_logs + branch_logs + deeper
            fails.append(self._last_fail or 'branch failed')
            self._restore(snap)
        self._last_fail = f"all branches failed on row {r}: {' ; '.join(fails[:2])}"
        return None, []

    def solve_staged(self):
        for cap in (0, 3, 6, None):
            snap = self._snapshot()
            stage = 'rules-only' if cap == 0 else (f'short-depth({cap})' if cap is not None else 'full-search')
            ans, logs = self._search_one(0, cap, stage)
            self._restore(snap)
            if ans is not None:
                return ans, logs
        return None, []


def _normalize_observation(observation):
    data = observation
    if isinstance(data, dict) and 'original_data' in data and isinstance(data['original_data'], dict):
        data = data['original_data'].get('data', data)
    # New construction observation format: {'data': obstacle_grid}
    if isinstance(data, dict) and 'data' in data:
        data = data['data']
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError('starbattlex observation must be square grid')
    n = len(data)
    if any(len(row) != n for row in data):
        raise ValueError('starbattlex grid must be square')
    return [row[:] for row in data]


def solve(observation, verbose: bool = False, max_logs: int = 8000, log_level: str = 'brief'):
    grid = _normalize_observation(observation)
    solver = _StarBattleXSolver(grid)
    answer, _ = solver.solve_staged()
    if answer is None:
        return 'No Solution'
    return answer
