from __future__ import annotations

from itertools import product
from typing import Dict, List, Optional, Set, Tuple

Pos = Tuple[int, int]
Cell = Tuple[int, int]
Grid = List[List[str]]


class _DSU:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> bool:
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return False
        self.p[rb] = ra
        return True


class _SlantSolver:
    def __init__(self, clues):
        self.clues = clues
        self.n = len(clues) - 1
        self._last_fail = ''
        self._dead_cache = set()
        self.domains = [[{'/', '\\'} for _ in range(self.n)] for _ in range(self.n)]
        self.dot_index = {(r, c): r * (self.n + 1) + c for r in range(self.n + 1) for c in range(self.n + 1)}
        self.dot_incident: Dict[Pos, List[Cell]] = {(r, c): [] for r in range(self.n + 1) for c in range(self.n + 1)}
        for r in range(self.n):
            for c in range(self.n):
                for dot in self._edge_of((r, c), '/'):
                    self.dot_incident[dot].append((r, c))
                for dot in self._edge_of((r, c), '\\'):
                    self.dot_incident[dot].append((r, c))
        self.weights = [
            [sum(1 for dr in (0, 1) for dc in (0, 1) if self.clues[r + dr][c + dc] is not None) for c in range(self.n)]
            for r in range(self.n)
        ]

    @staticmethod
    def _edge_of(cell: Cell, token: str):
        r, c = cell
        if token == '/':
            return ((r, c + 1), (r + 1, c))
        return ((r, c), (r + 1, c + 1))

    def _uses_dot(self, cell: Cell, token: str, dot: Pos) -> bool:
        return dot in self._edge_of(cell, token)

    def _snapshot(self):
        return ([[set(s) for s in row] for row in self.domains], self._last_fail)

    def _restore(self, snap):
        self.domains, self._last_fail = snap

    def _state_key(self):
        arr = bytearray(self.n * self.n)
        k = 0
        for r in range(self.n):
            for c in range(self.n):
                d = self.domains[r][c]
                if len(d) == 2:
                    arr[k] = 3
                elif '/' in d:
                    arr[k] = 1
                else:
                    arr[k] = 2
                k += 1
        return bytes(arr)

    def _build_fixed_dsu(self):
        dsu = _DSU((self.n + 1) * (self.n + 1))
        for r in range(self.n):
            for c in range(self.n):
                if len(self.domains[r][c]) != 1:
                    continue
                token = next(iter(self.domains[r][c]))
                a, b = self._edge_of((r, c), token)
                ia = self.dot_index[a]
                ib = self.dot_index[b]
                if dsu.find(ia) == dsu.find(ib):
                    self._last_fail = f'fixed diagonals already form a loop through {a}-{b}'
                    return None
                dsu.union(ia, ib)
        return dsu

    def _loop_prune(self) -> bool:
        changed = False
        dsu = self._build_fixed_dsu()
        if dsu is None:
            return False
        for r in range(self.n):
            for c in range(self.n):
                if len(self.domains[r][c]) == 1:
                    continue
                nd = set()
                for token in self.domains[r][c]:
                    a, b = self._edge_of((r, c), token)
                    if dsu.find(self.dot_index[a]) != dsu.find(self.dot_index[b]):
                        nd.add(token)
                if not nd:
                    self._last_fail = f'both slants make a loop at ({r},{c})'
                    return False
                if nd != self.domains[r][c]:
                    self.domains[r][c] = nd
                    changed = True
        return changed

    def _dot_support_prune(self) -> bool:
        changed = False
        for dot, cells in self.dot_incident.items():
            clue = self.clues[dot[0]][dot[1]]
            if clue is None:
                continue
            incident = []
            for cell in set(cells):
                vals = sorted(self.domains[cell[0]][cell[1]])
                incident.append((cell, vals))
            supported = {cell: set() for cell, _ in incident}
            ok_any = False
            for choice in product(*[vals for _, vals in incident]):
                cnt = sum(1 for (cell, _), token in zip(incident, choice) if self._uses_dot(cell, token, dot))
                if cnt != clue:
                    continue
                ok_any = True
                for (cell, _), token in zip(incident, choice):
                    supported[cell].add(token)
            if not ok_any:
                self._last_fail = f'dot clue at {dot} has no support'
                return False
            for cell, keep in supported.items():
                if not keep:
                    self._last_fail = f'cell {cell} has no supporting orientation for clue {dot}'
                    return False
                d = self.domains[cell[0]][cell[1]]
                if keep != d:
                    self.domains[cell[0]][cell[1]] = keep
                    changed = True
        return changed

    def _propagate(self):
        self._last_fail = ''
        while True:
            changed = False
            for step in (self._dot_support_prune, self._loop_prune):
                ok = step()
                if ok is False and self._last_fail:
                    return False
                changed = changed or ok
            if not changed:
                break
        return True

    def _force_by_contradiction_lite(self, max_cells: int = 10) -> bool:
        choices = []
        for r in range(self.n):
            for c in range(self.n):
                if len(self.domains[r][c]) > 1:
                    choices.append(((len(self.domains[r][c]), -self.weights[r][c], r, c), r, c))
        if not choices:
            return True
        choices.sort(key=lambda x: x[0])
        for _, r, c in choices[:max_cells]:
            vals = sorted(self.domains[r][c])
            feasible = []
            for token in vals:
                snap = self._snapshot()
                self.domains[r][c] = {token}
                ok = self._propagate()
                self._restore(snap)
                if ok:
                    feasible.append(token)
            if not feasible:
                self._last_fail = f'both orientations fail at ({r},{c})'
                return False
            if len(feasible) == 1:
                self.domains[r][c] = {feasible[0]}
                if not self._propagate():
                    return False
                return True
        return True

    def _is_complete(self) -> bool:
        return all(len(self.domains[r][c]) == 1 for r in range(self.n) for c in range(self.n))

    def _build_answer(self) -> Grid:
        return [[next(iter(self.domains[r][c])) for c in range(self.n)] for r in range(self.n)]

    def _final_valid(self) -> bool:
        dsu = _DSU((self.n + 1) * (self.n + 1))
        for r in range(self.n):
            for c in range(self.n):
                if len(self.domains[r][c]) != 1:
                    self._last_fail = 'final state incomplete'
                    return False
                token = next(iter(self.domains[r][c]))
                a, b = self._edge_of((r, c), token)
                ia = self.dot_index[a]
                ib = self.dot_index[b]
                if dsu.find(ia) == dsu.find(ib):
                    self._last_fail = 'loop exists in final state'
                    return False
                dsu.union(ia, ib)
        for r in range(self.n + 1):
            for c in range(self.n + 1):
                clue = self.clues[r][c]
                if clue is None:
                    continue
                cnt = 0
                for cell in set(self.dot_incident[(r, c)]):
                    token = next(iter(self.domains[cell[0]][cell[1]]))
                    cnt += 1 if self._uses_dot(cell, token, (r, c)) else 0
                if cnt != clue:
                    self._last_fail = f'clue mismatch at {(r, c)}'
                    return False
        return True

    def _choose_branch(self):
        best = None
        best_key = None
        for r in range(self.n):
            for c in range(self.n):
                if len(self.domains[r][c]) <= 1:
                    continue
                key = (len(self.domains[r][c]), -self.weights[r][c], r, c)
                if best_key is None or key < best_key:
                    best_key = key
                    best = (r, c)
        if best is None:
            return None, []
        r, c = best
        return best, sorted(self.domains[r][c])

    def _search_one(self, depth: int, depth_limit: Optional[int]):
        use_dead_cache = depth_limit is None
        key0 = self._state_key()
        if use_dead_cache and key0 in self._dead_cache:
            return None

        if not self._propagate():
            if use_dead_cache:
                self._dead_cache.add(key0)
            return None
        if depth <= 1:
            if not self._force_by_contradiction_lite():
                if use_dead_cache:
                    self._dead_cache.add(key0)
                return None
        if self._is_complete():
            return self._build_answer() if self._final_valid() else None
        if depth_limit is not None and depth >= depth_limit:
            self._last_fail = f'depth limit reached at d={depth}'
            return None
        pos, vals = self._choose_branch()
        if pos is None:
            if use_dead_cache:
                self._dead_cache.add(self._state_key())
            return None
        r, c = pos
        trials = []
        deep_order = not (self.n >= 15 and depth >= 2)
        if deep_order:
            for token in vals:
                snap = self._snapshot()
                self.domains[r][c] = {token}
                ok2 = self._propagate()
                unk = sum(1 for rr in range(self.n) for cc in range(self.n) if len(self.domains[rr][cc]) > 1)
                self._restore(snap)
                if ok2:
                    trials.append((unk, token))
            if not trials:
                self._last_fail = f'both orientations infeasible at ({r},{c})'
                if use_dead_cache:
                    self._dead_cache.add(self._state_key())
                return None
            trials.sort()
        else:
            trials = [(0, token) for token in vals]

        fails = []
        for _, token in trials:
            snap = self._snapshot()
            self.domains[r][c] = {token}
            ans = self._search_one(depth + 1, depth_limit)
            if ans is not None:
                return ans
            fails.append(self._last_fail or 'branch failed')
            self._restore(snap)
        self._last_fail = f"all branches failed at ({r},{c}): {' ; '.join(fails[:2])}"
        if use_dead_cache:
            self._dead_cache.add(self._state_key())
        return None

    def solve_staged(self):
        self._dead_cache.clear()
        caps = (0, None) if self.n >= 15 else (0, 3, 6, None)
        for cap in caps:
            snap = self._snapshot()
            ans = self._search_one(0, cap)
            self._restore(snap)
            if ans is not None:
                return ans
        return None


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict) and 'original_data' in obs and isinstance(obs['original_data'], dict):
        obs = obs['original_data'].get('data', obs)
    if isinstance(obs, dict) and 'data' in obs:
        obs = obs['data']
    if isinstance(obs, dict):
        if not obs:
            raise ValueError('slant clues cannot be empty')
        max_r = max(r for r, _ in obs.keys())
        max_c = max(c for _, c in obs.keys())
        n = max(max_r, max_c)
        grid = [[None for _ in range(n + 1)] for _ in range(n + 1)]
        for (r, c), v in obs.items():
            grid[int(r)][int(c)] = int(v)
        return grid
    if not isinstance(obs, list) or not obs or not isinstance(obs[0], list):
        raise ValueError('slant observation must be clue grid')
    size = len(obs)
    if any(len(row) != size for row in obs):
        raise ValueError('slant clue grid must be square')
    return [[None if v is None else int(v) for v in row] for row in obs]


def solve(observation, verbose: bool = False, max_logs: int = 8000, log_level: str = 'brief'):
    if log_level not in {'brief', 'full'}:
        raise ValueError("log_level must be 'brief' or 'full'")
    clues = _normalize_observation(observation)
    solver = _SlantSolver(clues)
    answer = solver.solve_staged()
    if answer is None:
        return 'No Solution'
    return answer
