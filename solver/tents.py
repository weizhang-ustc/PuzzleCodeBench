from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

Pos = Tuple[int, int]
Grid = List[List[Optional[str]]]


class _TentSolver:
    DIR4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    DIR8 = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]

    def __init__(self, trees, row_counts, col_counts):
        self.n = len(trees)
        self.trees_grid = [row[:] for row in trees]
        self.row_need = list(row_counts)
        self.col_need = list(col_counts)
        self._last_fail = ''

        self.trees: List[Pos] = []
        for r in range(self.n):
            if len(self.trees_grid[r]) != self.n:
                raise ValueError('tents grid must be square')
            for c in range(self.n):
                if self.trees_grid[r][c] == 'T':
                    self.trees.append((r, c))
        self.tree_idx = {p: i for i, p in enumerate(self.trees)}

        self.tree_domains: List[Set[Pos]] = [set() for _ in self.trees]
        self.tree_fixed: List[Optional[Pos]] = [None for _ in self.trees]
        self.cell_trees: Dict[Pos, Set[int]] = {}
        self.cell_state: Dict[Pos, int] = {}

        for r in range(self.n):
            for c in range(self.n):
                if self.trees_grid[r][c] == 'T':
                    continue
                owners = []
                for dr, dc in self.DIR4:
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < self.n and 0 <= cc < self.n and self.trees_grid[rr][cc] == 'T':
                        owners.append(self.tree_idx[(rr, cc)])
                if owners:
                    self.cell_trees[(r, c)] = set(owners)
                    self.cell_state[(r, c)] = -1
                    for ti in owners:
                        self.tree_domains[ti].add((r, c))

        for ti, dom in enumerate(self.tree_domains):
            if not dom:
                raise ValueError(f'tree {self.trees[ti]} has no legal tent cell')

        self.row_left = self.row_need[:]
        self.col_left = self.col_need[:]

    def _msg(self, brief: str, full: str) -> str:
        return brief

    def _snapshot(self):
        return ([set(d) for d in self.tree_domains], self.tree_fixed[:], {k: set(v) for k, v in self.cell_trees.items()}, dict(self.cell_state), self.row_left[:], self.col_left[:], self._last_fail)

    def _restore(self, snap):
        self.tree_domains, self.tree_fixed, self.cell_trees, self.cell_state, self.row_left, self.col_left, self._last_fail = snap

    def _state_key(self):
        return (tuple(tuple(sorted(d)) for d in self.tree_domains), tuple(sorted((cell, st, tuple(sorted(self.cell_trees.get(cell, set())))) for cell, st in self.cell_state.items())))

    def _drop_candidate(self, ti: int, cell: Pos, reason: str, logs) -> bool:
        if cell not in self.tree_domains[ti]:
            return True
        if self.tree_fixed[ti] == cell:
            self._last_fail = f'cannot remove fixed tent {cell} from tree {self.trees[ti]}'
            return False
        self.tree_domains[ti].remove(cell)
        if cell in self.cell_trees:
            self.cell_trees[cell].discard(ti)
            if not self.cell_trees[cell] and self.cell_state.get(cell, -1) == -1:
                self.cell_state[cell] = 0
                why = reason
                logs.append(('X', cell, why))
        if self.tree_fixed[ti] is None and not self.tree_domains[ti]:
            self._last_fail = f'tree {self.trees[ti]} lost all candidates'
            return False
        return True

    def _assign_tree(self, ti: int, cell: Pos, reason: str, logs) -> bool:
        if cell not in self.tree_domains[ti]:
            self._last_fail = f'{cell} unavailable for tree {self.trees[ti]}'
            return False
        if self.tree_fixed[ti] == cell:
            return True
        if self.tree_fixed[ti] is not None and self.tree_fixed[ti] != cell:
            self._last_fail = f'tree {self.trees[ti]} already fixed elsewhere'
            return False
        if self.cell_state.get(cell, -1) == 1 and self.tree_fixed[ti] != cell:
            self._last_fail = f'cell {cell} already used by another tree'
            return False
        self.tree_fixed[ti] = cell
        if self.cell_state.get(cell, -1) != 1:
            self.cell_state[cell] = 1
            self.row_left[cell[0]] -= 1
            self.col_left[cell[1]] -= 1
            if self.row_left[cell[0]] < 0 or self.col_left[cell[1]] < 0:
                self._last_fail = f'row/col quota exceeded by tent at {cell}'
                return False
        for other in list(self.tree_domains[ti]):
            if other != cell:
                if not self._drop_candidate(ti, other, f'tree {self.trees[ti]} already uses {cell}', logs):
                    return False
        self.tree_domains[ti] = {cell}
        for other_ti in list(self.cell_trees.get(cell, set())):
            if other_ti != ti:
                if not self._drop_candidate(other_ti, cell, f'cell {cell} already reserved for tree {self.trees[ti]}', logs):
                    return False
        self.cell_trees[cell] = {ti}
        for dr, dc in self.DIR8:
            rr, cc = cell[0] + dr, cell[1] + dc
            other = (rr, cc)
            if other in self.cell_trees and self.cell_state.get(other, -1) == -1:
                for other_ti in list(self.cell_trees[other]):
                    if not self._drop_candidate(other_ti, other, f'tent at {cell} forbids touching cell {other}', logs):
                        return False
        why = reason
        logs.append(('t', cell, why))
        return True

    def _basic_bounds(self) -> bool:
        if any(v < 0 for v in self.row_left) or any(v < 0 for v in self.col_left):
            self._last_fail = 'negative row/column quota'
            return False
        remaining = sum(1 for v in self.tree_fixed if v is None)
        if sum(self.row_left) != remaining or sum(self.col_left) != remaining:
            self._last_fail = 'remaining tents mismatch tree count'
            return False
        for ti, dom in enumerate(self.tree_domains):
            if self.tree_fixed[ti] is None and not dom:
                self._last_fail = f'tree {self.trees[ti]} has no candidates'
                return False
        for r in range(self.n):
            avail = sum(1 for cell, st in self.cell_state.items() if st == -1 and cell[0] == r)
            if self.row_left[r] > avail:
                self._last_fail = f'row {r} lacks enough candidate cells'
                return False
        for c in range(self.n):
            avail = sum(1 for cell, st in self.cell_state.items() if st == -1 and cell[1] == c)
            if self.col_left[c] > avail:
                self._last_fail = f'col {c} lacks enough candidate cells'
                return False
        return True

    def _matching_feasible(self) -> bool:
        match_cell: Dict[Pos, int] = {}

        def dfs(ti: int, seen: Set[Pos]) -> bool:
            for cell in sorted(self.tree_domains[ti]):
                if self.cell_state.get(cell, -1) == 0 or cell in seen:
                    continue
                seen.add(cell)
                if cell not in match_cell or dfs(match_cell[cell], seen):
                    match_cell[cell] = ti
                    return True
            return False

        for ti in range(len(self.trees)):
            if self.tree_fixed[ti] is not None:
                continue
            if not dfs(ti, set()):
                self._last_fail = 'tree-to-cell matching impossible'
                return False
        return True

    def _force_singletons(self, logs) -> bool:
        changed = False
        for ti in range(len(self.trees)):
            if self.tree_fixed[ti] is None and len(self.tree_domains[ti]) == 1:
                cell = next(iter(self.tree_domains[ti]))
                if not self._assign_tree(ti, cell, self._msg(f'tree {self.trees[ti]} only candidate', f'tree {self.trees[ti]} has exactly one remaining candidate cell {cell}'), logs):
                    return False
                changed = True
        return changed

    def _row_col_rules(self, logs) -> bool:
        changed = False
        for r in range(self.n):
            cells = [cell for cell, st in self.cell_state.items() if st == -1 and cell[0] == r]
            if self.row_left[r] == 0:
                for cell in cells:
                    for ti in list(self.cell_trees.get(cell, set())):
                        if not self._drop_candidate(ti, cell, f'row {r} quota already filled', logs):
                            return False
                        changed = True
        for c in range(self.n):
            cells = [cell for cell, st in self.cell_state.items() if st == -1 and cell[1] == c]
            if self.col_left[c] == 0:
                for cell in cells:
                    for ti in list(self.cell_trees.get(cell, set())):
                        if not self._drop_candidate(ti, cell, f'col {c} quota already filled', logs):
                            return False
                        changed = True
        return changed

    def _propagate(self):
        logs = []
        self._last_fail = ''
        while True:
            if not self._basic_bounds() or not self._matching_feasible():
                return False, logs
            changed = False
            for step in (self._force_singletons, self._row_col_rules):
                ok = step(logs)
                if ok is False and self._last_fail:
                    return False, logs
                changed = changed or ok
            if not changed:
                break
        return True, logs

    def _is_complete(self) -> bool:
        return all(v is not None for v in self.tree_fixed)

    def _build_answer(self) -> Grid:
        out = [[None for _ in range(self.n)] for _ in range(self.n)]
        for cell, st in self.cell_state.items():
            if st == 1:
                out[cell[0]][cell[1]] = 't'
        return out

    def _final_valid(self) -> bool:
        if not self._is_complete():
            self._last_fail = 'not all trees matched'
            return False
        if any(self.row_left) or any(self.col_left):
            self._last_fail = 'row/column quotas unfinished'
            return False
        tents = [cell for cell, st in self.cell_state.items() if st == 1]
        if len(tents) != len(self.trees):
            self._last_fail = 'tent count mismatch'
            return False
        tent_set = set(tents)
        for cell in tents:
            for dr, dc in self.DIR8:
                other = (cell[0] + dr, cell[1] + dc)
                if other in tent_set and other != cell:
                    self._last_fail = f'tents touch at {cell} and {other}'
                    return False
        return True

    def _choose_branch(self):
        best = None
        best_vals = []
        best_key = None
        for ti, dom in enumerate(self.tree_domains):
            if self.tree_fixed[ti] is not None:
                continue
            vals = sorted(dom, key=lambda cell: (self.row_left[cell[0]] + self.col_left[cell[1]], cell))
            key = (len(vals), ti)
            if best_key is None or key < best_key:
                best_key = key
                best = ti
                best_vals = vals
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
        ti, vals = self._choose_branch()
        if ti is None:
            return None, []
        fails = []
        for cell in vals:
            snap = self._snapshot()
            branch_logs = []
            if self._assign_tree(ti, cell, self._msg(f'{stage} branch tree {self.trees[ti]}->{cell}', f'{stage} branch at depth {depth}: try pairing tree {self.trees[ti]} with cell {cell}'), branch_logs):
                ans, deeper = self._search_one(depth + 1, depth_limit, stage)
                if ans is not None:
                    return ans, base_logs + branch_logs + deeper
            fails.append(self._last_fail or 'branch failed')
            self._restore(snap)
        self._last_fail = f"all tent branches failed for tree {self.trees[ti]}: {' ; '.join(fails[:2])}"
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
    obs = observation
    if isinstance(obs, dict) and 'original_data' in obs and isinstance(obs['original_data'], dict):
        obs = obs['original_data']
    if not isinstance(obs, dict):
        raise ValueError('tents observation must be dict')
    trees = obs.get('trees', obs.get('tree'))
    row_counts = obs.get('row_tent_counts', obs.get('L_nums'))
    col_counts = obs.get('col_tent_counts', obs.get('U_nums'))
    if trees is None or row_counts is None or col_counts is None:
        raise ValueError('tents observation missing fields')
    return [row[:] for row in trees], list(row_counts), list(col_counts)


def solve(observation, verbose: bool = False, max_logs: int = 8000, log_level: str = 'brief'):
    trees, row_counts, col_counts = _normalize_observation(observation)
    solver = _TentSolver(trees, row_counts, col_counts)
    answer, _ = solver.solve_staged()
    if answer is None:
        return 'No Solution'
    return answer
