from __future__ import annotations

import copy
from typing import List, Optional, Sequence, Set, Tuple

Pos = Tuple[int, int]
Grid = List[List[Optional[int]]]
ValGrid = List[List[int]]  # -1 unknown, 0 white, 1 black


class _Constraint:
    def __init__(self, cells: Sequence[Pos], total: int):
        self.cells = tuple(cells)
        self.total = int(total)


class _MosaicSolver:
    def __init__(self, clue_grid: Grid):
        self.n = len(clue_grid)
        self.m = len(clue_grid[0])
        self.clue_grid = [row[:] for row in clue_grid]
        self._last_fail = ""

        self.base: ValGrid = [[-1 for _ in range(self.m)] for _ in range(self.n)]
        self.cells: List[Pos] = [(r, c) for r in range(self.n) for c in range(self.m)]
        self.constraints: List[_Constraint] = []
        self.cell_to_constraints = {(r, c): [] for r in range(self.n) for c in range(self.m)}

        for r in range(self.n):
            for c in range(self.m):
                clue = self.clue_grid[r][c]
                if clue is None:
                    continue
                box = []
                for rr in range(max(0, r - 1), min(self.n - 1, r + 1) + 1):
                    for cc in range(max(0, c - 1), min(self.m - 1, c + 1) + 1):
                        box.append((rr, cc))
                idx = len(self.constraints)
                self.constraints.append(_Constraint(box, int(clue)))
                for p in box:
                    self.cell_to_constraints[p].append(idx)

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
            self._last_fail = f"conflict at ({r},{c})"
            return False
        grid[r][c] = v
        if why is not None:
            token = "B" if v == 1 else "."
            logs.append((token, (r, c), why))
        return True

    def _check_constraints(self, grid: ValGrid) -> bool:
        for i, cons in enumerate(self.constraints):
            black = 0
            unknown = 0
            for r, c in cons.cells:
                v = grid[r][c]
                if v == 1:
                    black += 1
                elif v == -1:
                    unknown += 1
            if black > cons.total:
                self._last_fail = f"constraint {i} exceeded"
                return False
            if black + unknown < cons.total:
                self._last_fail = f"constraint {i} cannot reach clue"
                return False
        return True

    def _propagate_counts(self, grid: ValGrid, logs: List[Tuple[str, Pos, str]]) -> bool:
        changed = False
        for i, cons in enumerate(self.constraints):
            black = 0
            unknown_cells: List[Pos] = []
            for p in cons.cells:
                v = grid[p[0]][p[1]]
                if v == 1:
                    black += 1
                elif v == -1:
                    unknown_cells.append(p)
            need = cons.total - black
            if need < 0 or need > len(unknown_cells):
                self._last_fail = f"constraint {i} impossible"
                return False

            if need == 0:
                for r, c in unknown_cells:
                    why = self._msg(
                        f"clue {i} saturated",
                        f"3x3 clue constraint {i} is already filled; cell ({r},{c}) must be white.",
                    )
                    if not self._set_cell(grid, r, c, 0, why, logs):
                        return False
                    changed = True
            elif need == len(unknown_cells):
                for r, c in unknown_cells:
                    why = self._msg(
                        f"clue {i} needs all",
                        (
                            f"Constraint {i} still needs {need} black cells and has exactly {len(unknown_cells)} unknowns; "
                            f"({r},{c}) must be black."
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
            black = 0
            unknown: Set[Pos] = set()
            for p in cons.cells:
                v = grid[p[0]][p[1]]
                if v == 1:
                    black += 1
                elif v == -1:
                    unknown.add(p)
            rem = cons.total - black
            if rem < 0 or rem > len(unknown):
                self._last_fail = f"constraint {i} reduced impossible"
                return False
            reduced.append((unknown, rem))

        idxs = [i for i, (s, _) in enumerate(reduced) if s]
        for a in idxs:
            sa, ra = reduced[a]
            for b in idxs:
                if a == b:
                    continue
                sb, rb = reduced[b]
                if not sa.issubset(sb):
                    continue
                diff = sb - sa
                need = rb - ra
                if need < 0 or need > len(diff):
                    self._last_fail = f"subset contradiction {a}->{b}"
                    return False
                if not diff:
                    continue
                if need == 0:
                    for r, c in sorted(diff):
                        why = self._msg(
                            f"subset {a}->{b}",
                            f"Unknown cells of constraint {a} are subset of {b}; difference cell ({r},{c}) must be white.",
                        )
                        if not self._set_cell(grid, r, c, 0, why, logs):
                            return False
                        changed = True
                elif need == len(diff):
                    for r, c in sorted(diff):
                        why = self._msg(
                            f"subset {a}->{b}",
                            f"Constraint difference between {a} and {b} forces ({r},{c}) black.",
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
            c1 = self._propagate_counts(grid, logs)
            if c1 is False and self._last_fail:
                return False, logs
            changed = changed or bool(c1)

            if enable_subset and not changed:
                c2 = self._propagate_subset(grid, logs)
                if c2 is False and self._last_fail:
                    return False, logs
                changed = changed or bool(c2)

            if not changed:
                break
        return True, logs

    def _is_complete(self, grid: ValGrid) -> bool:
        return all(grid[r][c] != -1 for r in range(self.n) for c in range(self.m))

    def _check_final(self, grid: ValGrid) -> bool:
        if not self._is_complete(grid):
            self._last_fail = "unresolved cells remain"
            return False
        return self._check_constraints(grid)

    def _choose_branch(self, grid: ValGrid) -> Optional[Pos]:
        best = None
        best_key = None
        for r in range(self.n):
            for c in range(self.m):
                if grid[r][c] != -1:
                    continue
                score = len(self.cell_to_constraints[(r, c)])
                key = (-score, r, c)
                if best_key is None or key < best_key:
                    best_key = key
                    best = (r, c)
        return best

    def _search_one(self, grid: ValGrid, depth: int, depth_limit: Optional[int], stage: str):
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
        for v in (1, 0):
            g2 = copy.deepcopy(grid)
            branch_logs: List[Tuple[str, Pos, str]] = []
            token = "B" if v == 1 else "."
            why = self._msg(
                f"{stage} branch",
                f"At depth {depth}, constraints stall; assume ({r},{c})={token} and continue.",
            )
            if fail_notes:
                why = self._msg(
                    f"{stage} backtrack",
                    f"Previous attempt failed ({fail_notes[-1]}), so try ({r},{c})={token}.",
                )
            if not self._set_cell(g2, r, c, v, why, branch_logs):
                fail_notes.append(self._last_fail or "assignment conflict")
                continue
            ans, deeper = self._search_one(g2, depth + 1, depth_limit, stage)
            if ans is not None:
                return ans, base_logs + branch_logs + deeper
            fail_notes.append(self._last_fail or "branch failed")

        self._last_fail = f"all branches fail at ({r},{c}): {' ; '.join(fail_notes[:2])}"
        return None, []

    def solve_staged(self):
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
        raise ValueError("mosaic observation must be a 2D list or dict with data")

    n = len(obs)
    m = len(obs[0])
    grid: Grid = [[None for _ in range(m)] for _ in range(n)]
    for r in range(n):
        if len(obs[r]) != m:
            raise ValueError("mosaic grid must be rectangular")
        for c in range(m):
            v = obs[r][c]
            grid[r][c] = None if v is None else int(v)
    return grid


def _build_answer(grid: ValGrid):
    n, m = len(grid), len(grid[0])
    return [["B" if grid[r][c] == 1 else None for c in range(m)] for r in range(n)]



def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 8000,
    log_level: str = "brief",
):
    clue_grid = _normalize_observation(observation)
    solver = _MosaicSolver(clue_grid)
    ans, _ = solver.solve_staged()
    if ans is None:
        return "No Solution"
    return _build_answer(ans)
