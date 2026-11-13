from __future__ import annotations

import copy
from typing import Dict, List, Optional, Sequence, Set, Tuple

Pos = Tuple[int, int]
Grid = List[List[Optional[int]]]
ValGrid = List[List[int]]  # -1 unknown, 0 safe, 1 mine


class _Constraint:
    def __init__(self, cells: Sequence[Pos], total: int):
        self.cells = tuple(cells)
        self.total = int(total)


class _MinesweeperSolver:
    DIR8 = [
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    ]

    def __init__(self, clue_grid: Grid):
        self.n = len(clue_grid)
        self.m = len(clue_grid[0])
        self.clue_grid = [row[:] for row in clue_grid]

        self.base: ValGrid = [[-1 for _ in range(self.m)] for _ in range(self.n)]
        self.mine_cells: List[Pos] = []
        self.constraints: List[_Constraint] = []
        self.cell_to_constraints: Dict[Pos, List[int]] = {}
        self._last_fail = ""

        for r in range(self.n):
            for c in range(self.m):
                v = self.clue_grid[r][c]
                if v is not None:
                    self.base[r][c] = 0

        for r in range(self.n):
            for c in range(self.m):
                if self.clue_grid[r][c] is None:
                    self.mine_cells.append((r, c))

        for r in range(self.n):
            for c in range(self.m):
                clue = self.clue_grid[r][c]
                if clue is None:
                    continue
                neigh = []
                for dr, dc in self.DIR8:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.n and 0 <= nc < self.m and self.clue_grid[nr][nc] is None:
                        neigh.append((nr, nc))
                self.constraints.append(_Constraint(neigh, int(clue)))

        for i, cons in enumerate(self.constraints):
            for p in cons.cells:
                self.cell_to_constraints.setdefault(p, []).append(i)

    def _msg(self, brief: str, full: str) -> str:
        return brief

    def _state_key(self, grid: ValGrid) -> Tuple[Tuple[int, ...], ...]:
        return tuple(tuple(row) for row in grid)

    def _set_cell(
        self,
        grid: ValGrid,
        r: int,
        c: int,
        v: int,
        why: Optional[str],
        logs: List[Tuple[str, Pos, str]],
    ) -> bool:
        cur = grid[r][c]
        if cur == v:
            return True
        if cur != -1 and cur != v:
            self._last_fail = f"conflict at ({r},{c}): {cur} vs {v}"
            return False
        if self.clue_grid[r][c] is not None and v == 1:
            self._last_fail = f"numbered cell ({r},{c}) cannot be a mine"
            return False

        grid[r][c] = v
        if why is not None:
            token = "F" if v == 1 else "."
            logs.append((token, (r, c), why))
        return True

    def _check_constraints(self, grid: ValGrid) -> bool:
        for i, cons in enumerate(self.constraints):
            mines = 0
            unknown = 0
            for r, c in cons.cells:
                if grid[r][c] == 1:
                    mines += 1
                elif grid[r][c] == -1:
                    unknown += 1
            if mines > cons.total:
                self._last_fail = f"constraint {i} exceeded: mines={mines} > {cons.total}"
                return False
            if mines + unknown < cons.total:
                self._last_fail = f"constraint {i} insufficient: max={mines + unknown} < {cons.total}"
                return False
        return True

    def _propagate_counts(self, grid: ValGrid, logs: List[Tuple[str, Pos, str]]) -> bool:
        changed = False
        for i, cons in enumerate(self.constraints):
            mines = 0
            unknown_cells: List[Pos] = []
            for p in cons.cells:
                v = grid[p[0]][p[1]]
                if v == 1:
                    mines += 1
                elif v == -1:
                    unknown_cells.append(p)
            need = cons.total - mines
            if need < 0 or need > len(unknown_cells):
                self._last_fail = f"constraint {i} impossible (need={need}, unknown={len(unknown_cells)})"
                return False

            if need == 0:
                for r, c in unknown_cells:
                    why = self._msg(
                        f"clue {i} already satisfied",
                        (
                            f"Constraint at numbered cell index {i} already has enough mines; "
                            f"cell ({r},{c}) must be safe."
                        ),
                    )
                    if not self._set_cell(grid, r, c, 0, why, logs):
                        return False
                    changed = True
            elif need == len(unknown_cells):
                for r, c in unknown_cells:
                    why = self._msg(
                        f"clue {i} needs all unknowns",
                        (
                            f"Constraint at numbered cell index {i} still needs {need} mines and has exactly "
                            f"{len(unknown_cells)} unknown neighbors; ({r},{c}) is forced mine."
                        ),
                    )
                    if not self._set_cell(grid, r, c, 1, why, logs):
                        return False
                    changed = True
        return changed

    def _propagate_subset(self, grid: ValGrid, logs: List[Tuple[str, Pos, str]]) -> bool:
        changed = False

        reduced: List[Tuple[Set[Pos], int]] = []
        for i, cons in enumerate(self.constraints):
            mines = 0
            unknown: Set[Pos] = set()
            for p in cons.cells:
                v = grid[p[0]][p[1]]
                if v == 1:
                    mines += 1
                elif v == -1:
                    unknown.add(p)
            rem = cons.total - mines
            if rem < 0 or rem > len(unknown):
                self._last_fail = f"constraint {i} reduced impossible"
                return False
            reduced.append((unknown, rem))

        idxs = [i for i, (s, _) in enumerate(reduced) if s]
        for ii in range(len(idxs)):
            a = idxs[ii]
            sa, ra = reduced[a]
            for jj in range(len(idxs)):
                b = idxs[jj]
                if a == b:
                    continue
                sb, rb = reduced[b]
                if not sa or not sb:
                    continue
                if not sa.issubset(sb):
                    continue

                diff = sb - sa
                need = rb - ra
                if need < 0 or need > len(diff):
                    self._last_fail = f"subset contradiction: {a} subset {b}, need={need}, diff={len(diff)}"
                    return False
                if not diff:
                    continue

                if need == 0:
                    for r, c in sorted(diff):
                        why = self._msg(
                            f"subset {a}->{b}",
                            (
                                f"Unknown-set({a}) is subset of unknown-set({b}); remaining mines are identical, "
                                f"so cells in set difference like ({r},{c}) must be safe."
                            ),
                        )
                        if not self._set_cell(grid, r, c, 0, why, logs):
                            return False
                        changed = True
                elif need == len(diff):
                    for r, c in sorted(diff):
                        why = self._msg(
                            f"subset {a}->{b}",
                            (
                                f"From subset relation {a}->{b}, the difference set must contribute all {need} mines; "
                                f"({r},{c}) is forced mine."
                            ),
                        )
                        if not self._set_cell(grid, r, c, 1, why, logs):
                            return False
                        changed = True

        return changed

    def _propagate(self, grid: ValGrid, enable_subset: bool = True) -> Tuple[bool, List[Tuple[str, Pos, str]]]:
        logs: List[Tuple[str, Pos, str]] = []
        self._last_fail = ""

        while True:
            if not self._check_constraints(grid):
                return False, logs

            changed = False
            got = self._propagate_counts(grid, logs)
            if got is False and self._last_fail:
                return False, logs
            changed = changed or bool(got)

            if enable_subset and not changed:
                got2 = self._propagate_subset(grid, logs)
                if got2 is False and self._last_fail:
                    return False, logs
                changed = changed or bool(got2)

            if not changed:
                break

        return True, logs

    def _is_complete(self, grid: ValGrid) -> bool:
        return all(grid[r][c] != -1 for r in range(self.n) for c in range(self.m) if self.clue_grid[r][c] is None)

    def _check_final(self, grid: ValGrid) -> bool:
        if not self._is_complete(grid):
            self._last_fail = "unresolved mine cells remain"
            return False
        return self._check_constraints(grid)

    def _choose_branch(self, grid: ValGrid) -> Optional[Pos]:
        best = None
        best_score = None
        for r, c in self.mine_cells:
            if grid[r][c] != -1:
                continue
            score = len(self.cell_to_constraints.get((r, c), []))
            key = (-score, r, c)
            if best_score is None or key < best_score:
                best_score = key
                best = (r, c)
        return best

    def _search_one(
        self,
        grid: ValGrid,
        depth: int,
        depth_limit: Optional[int],
        stage: str,
    ) -> Tuple[Optional[ValGrid], List[Tuple[str, Pos, str]]]:
        ok, base_logs = self._propagate(grid, enable_subset=True)
        if not ok:
            return None, []
        if self._check_final(grid):
            return grid, base_logs

        if depth_limit is not None and depth >= depth_limit:
            self._last_fail = f"depth limit reached at d={depth}"
            return None, []

        pos = self._choose_branch(grid)
        if pos is None:
            return None, []
        r, c = pos

        fail_notes: List[str] = []
        order = [1, 0]
        for v in order:
            g2 = copy.deepcopy(grid)
            branch_logs: List[Tuple[str, Pos, str]] = []
            token = "F" if v == 1 else "."
            if fail_notes:
                why = self._msg(
                    f"{stage} backtrack",
                    f"At depth {depth}, previous branch failed ({fail_notes[-1]}), so try ({r},{c})={token}.",
                )
            else:
                why = self._msg(
                    f"{stage} branch",
                    f"At depth {depth}, choose unresolved cell ({r},{c}) and assume {token}.",
                )
            if not self._set_cell(g2, r, c, v, why, branch_logs):
                fail_notes.append(self._last_fail or "assignment conflict")
                continue
            ans, deeper = self._search_one(g2, depth + 1, depth_limit, stage)
            if ans is not None:
                return ans, base_logs + branch_logs + deeper
            fail_notes.append(self._last_fail or "branch failed")

        self._last_fail = f"both branches failed at ({r},{c}): {' ; '.join(fail_notes[:2])}"
        return None, []

    def solve_staged(self) -> Tuple[Optional[ValGrid], List[Tuple[str, Pos, str]]]:
        g0 = copy.deepcopy(self.base)
        ok, logs0 = self._propagate(g0, enable_subset=True)
        if ok and self._check_final(g0):
            return g0, logs0

        for cap in (3, 6):
            g = copy.deepcopy(self.base)
            ans, logs = self._search_one(g, 0, cap, f"short-depth({cap})")
            if ans is not None:
                return ans, logs

        g = copy.deepcopy(self.base)
        return self._search_one(g, 0, None, "full-search")


def _normalize_observation(observation) -> Grid:
    obs = observation
    if isinstance(obs, dict):
        if "data" in obs and isinstance(obs["data"], list):
            obs = obs["data"]
        elif "original_data" in obs and isinstance(obs["original_data"], dict) and "data" in obs["original_data"]:
            obs = obs["original_data"]["data"]

    if not (isinstance(obs, list) and obs and isinstance(obs[0], list)):
        raise ValueError("minesweeper observation must be a 2D list or dict with data")

    n = len(obs)
    m = len(obs[0])
    grid: Grid = [[None for _ in range(m)] for _ in range(n)]
    for r in range(n):
        if len(obs[r]) != m:
            raise ValueError("minesweeper grid must be rectangular")
        for c in range(m):
            v = obs[r][c]
            grid[r][c] = None if v is None else int(v)
    return grid


def _build_answer(grid: ValGrid, clue_grid: Grid):
    n, m = len(grid), len(grid[0])
    out = [[None for _ in range(m)] for _ in range(n)]
    for r in range(n):
        for c in range(m):
            if clue_grid[r][c] is None and grid[r][c] == 1:
                out[r][c] = "F"
    return out



def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 8000,
    log_level: str = "brief",
):
    clue_grid = _normalize_observation(observation)
    solver = _MinesweeperSolver(clue_grid)
    ans, _ = solver.solve_staged()
    if ans is None:
        return "No Solution"
    return _build_answer(ans, clue_grid)
