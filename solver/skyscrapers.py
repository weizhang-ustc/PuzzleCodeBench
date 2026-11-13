from __future__ import annotations

from itertools import permutations
from typing import List, Optional, Sequence, Tuple

GridNum = List[List[int]]


def _visible(seq: Sequence[int]) -> int:
    top = 0
    cnt = 0
    for v in seq:
        if v > top:
            top = v
            cnt += 1
    return cnt


class _SkyscraperSolver:
    def __init__(self, clues):
        self.clues = {k: list(v) for k, v in clues.items()}
        self.n = len(self.clues['U'])
        self._last_fail = ''

        if any(len(self.clues[k]) != self.n for k in ('U', 'D', 'L', 'R')):
            raise ValueError('all skyscraper clue arrays must have the same size')

        all_rows = list(permutations(range(1, self.n + 1)))
        self.row_cands = []
        self.col_cands = []
        for r in range(self.n):
            left = self.clues['L'][r]
            right = self.clues['R'][r]
            self.row_cands.append([
                p for p in all_rows if (left is None or _visible(p) == left) and (right is None or _visible(p[::-1]) == right)
            ])
        for c in range(self.n):
            up = self.clues['U'][c]
            down = self.clues['D'][c]
            self.col_cands.append([
                p for p in all_rows if (up is None or _visible(p) == up) and (down is None or _visible(p[::-1]) == down)
            ])

        self.domains = [[set(range(1, self.n + 1)) for _ in range(self.n)] for _ in range(self.n)]

    def _snapshot(self):
        return ([list(v) for v in self.row_cands], [list(v) for v in self.col_cands], [[set(s) for s in row] for row in self.domains], self._last_fail)

    def _restore(self, snap):
        self.row_cands, self.col_cands, self.domains, self._last_fail = snap

    def _refresh_domains(self) -> bool:
        changed = False
        for r in range(self.n):
            if not self.row_cands[r]:
                self._last_fail = f'row {r} has no candidates'
                return False
            for c in range(self.n):
                row_vals = {p[c] for p in self.row_cands[r]}
                col_vals = {p[r] for p in self.col_cands[c]}
                nd = self.domains[r][c] & row_vals & col_vals
                if not nd:
                    self._last_fail = f'cell ({r},{c}) emptied'
                    return False
                if nd != self.domains[r][c]:
                    self.domains[r][c] = nd
                    changed = True
        return changed

    def _filter_rows(self) -> bool:
        changed = False
        for r in range(self.n):
            new = [p for p in self.row_cands[r] if all(p[c] in self.domains[r][c] for c in range(self.n))]
            if not new:
                self._last_fail = f'row {r} candidates exhausted'
                return False
            if len(new) != len(self.row_cands[r]):
                self.row_cands[r] = new
                changed = True
        return changed

    def _filter_cols(self) -> bool:
        changed = False
        for c in range(self.n):
            new = [p for p in self.col_cands[c] if all(p[r] in self.domains[r][c] for r in range(self.n))]
            if not new:
                self._last_fail = f'col {c} candidates exhausted'
                return False
            if len(new) != len(self.col_cands[c]):
                self.col_cands[c] = new
                changed = True
        return changed

    def _hidden_singles(self) -> bool:
        changed = False
        for r in range(self.n):
            for v in range(1, self.n + 1):
                spots = [c for c in range(self.n) if any(p[c] == v for p in self.row_cands[r])]
                if not spots:
                    self._last_fail = f'row {r} cannot place {v}'
                    return False
                if len(spots) == 1:
                    c = spots[0]
                    if self.domains[r][c] != {v}:
                        self.domains[r][c] = {v}
                        changed = True
        for c in range(self.n):
            for v in range(1, self.n + 1):
                spots = [r for r in range(self.n) if any(p[r] == v for p in self.col_cands[c])]
                if not spots:
                    self._last_fail = f'col {c} cannot place {v}'
                    return False
                if len(spots) == 1:
                    r = spots[0]
                    if self.domains[r][c] != {v}:
                        self.domains[r][c] = {v}
                        changed = True
        return changed

    def _propagate(self):
        self._last_fail = ''
        while True:
            changed = False
            for step in (self._refresh_domains, self._filter_rows, self._filter_cols, self._hidden_singles):
                ok = step()
                if ok is False and self._last_fail:
                    return False
                changed = changed or ok
            if not changed:
                break
        return True

    def _is_complete(self) -> bool:
        return all(len(self.row_cands[r]) == 1 for r in range(self.n))

    def _build_answer(self) -> GridNum:
        return [list(self.row_cands[r][0]) for r in range(self.n)]

    def _final_valid(self) -> bool:
        if not self._is_complete():
            self._last_fail = 'not complete'
            return False
        grid = self._build_answer()
        vals = set(range(1, self.n + 1))
        for r in range(self.n):
            if set(grid[r]) != vals:
                self._last_fail = f'row {r} invalid'
                return False
            if self.clues['L'][r] is not None and _visible(grid[r]) != self.clues['L'][r]:
                self._last_fail = f'left clue mismatch at row {r}'
                return False
            if self.clues['R'][r] is not None and _visible(grid[r][::-1]) != self.clues['R'][r]:
                self._last_fail = f'right clue mismatch at row {r}'
                return False
        for c in range(self.n):
            col = [grid[r][c] for r in range(self.n)]
            if set(col) != vals:
                self._last_fail = f'col {c} invalid'
                return False
            if self.clues['U'][c] is not None and _visible(col) != self.clues['U'][c]:
                self._last_fail = f'top clue mismatch at col {c}'
                return False
            if self.clues['D'][c] is not None and _visible(col[::-1]) != self.clues['D'][c]:
                self._last_fail = f'bottom clue mismatch at col {c}'
                return False
        return True

    def _choose_branch(self):
        best_kind = None
        best_idx = None
        best_vals = []
        best_key = None
        for r in range(self.n):
            if len(self.row_cands[r]) > 1:
                key = (len(self.row_cands[r]), 0, r)
                if best_key is None or key < best_key:
                    best_key = key
                    best_kind = 'row'
                    best_idx = r
                    best_vals = list(self.row_cands[r])
        for c in range(self.n):
            if len(self.col_cands[c]) > 1:
                key = (len(self.col_cands[c]), 1, c)
                if best_key is None or key < best_key:
                    best_key = key
                    best_kind = 'col'
                    best_idx = c
                    best_vals = list(self.col_cands[c])
        return best_kind, best_idx, best_vals

    def _search_one(self, depth: int, depth_limit: Optional[int]):
        ok = self._propagate()
        if not ok:
            return None
        if self._is_complete():
            return self._build_answer() if self._final_valid() else None
        if depth_limit is not None and depth >= depth_limit:
            self._last_fail = f'depth limit reached at d={depth}'
            return None
        kind, idx, vals = self._choose_branch()
        if idx is None:
            return None
        fails = []
        for cand in vals:
            snap = self._snapshot()
            if kind == 'row':
                self.row_cands[idx] = [cand]
            else:
                self.col_cands[idx] = [cand]
            ans = self._search_one(depth + 1, depth_limit)
            if ans is not None:
                return ans
            fails.append(self._last_fail or 'branch failed')
            self._restore(snap)
        self._last_fail = f"all branches failed on {kind} {idx}: {' ; '.join(fails[:2])}"
        return None

    def solve_staged(self):
        for cap in (0, 3, 6, None):
            snap = self._snapshot()
            ans = self._search_one(0, cap)
            self._restore(snap)
            if ans is not None:
                return ans
        return None


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict) and 'original_data' in obs and isinstance(obs['original_data'], dict):
        obs = obs['original_data']
    if not isinstance(obs, dict):
        raise ValueError('skyscrapers observation must be dict')
    clues = {k: list(obs.get(k, [])) for k in ('U', 'D', 'L', 'R')}
    if not clues['U']:
        raise ValueError('missing skyscraper clues')
    return clues


def solve(observation, verbose: bool = False, max_logs: int = 8000, log_level: str = 'brief'):
    if log_level not in {'brief', 'full'}:
        raise ValueError("log_level must be 'brief' or 'full'")
    clues = _normalize_observation(observation)
    solver = _SkyscraperSolver(clues)
    answer = solver.solve_staged()
    if answer is None:
        return 'No Solution'
    return answer
