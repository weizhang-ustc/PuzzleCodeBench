from __future__ import annotations

import copy
from collections import deque
from typing import Dict, List, Optional, Sequence, Tuple

Cell = str  # '.', 'W', 'B'
Grid = List[List[Cell]]
Pos = Tuple[int, int]


class _Logger:
    def __init__(self, verbose: bool, max_logs: int):
        self.verbose = verbose
        self.max_logs = max_logs
        self.count = 0
        self.seen_pos = set()

    def emit(self, token: str, pos: Pos, why: str):
        if not self.verbose:
            return
        if self.count >= self.max_logs:
            return
        if pos in self.seen_pos:
            return
        self.seen_pos.add(pos)
        print(f"{token} | {pos} | {why}")
        self.count += 1


class _KurodokoSolver:
    DIR4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def __init__(
        self,
        clue_grid: Sequence[Sequence[Optional[int]]],
        verbose: bool,
        max_logs: int,
        log_level: str,
    ):
        self.n = len(clue_grid)
        self.m = len(clue_grid[0])
        self.clue_grid = [[clue_grid[r][c] for c in range(self.m)] for r in range(self.n)]

        self.clues: Dict[Pos, int] = {}
        for r in range(self.n):
            for c in range(self.m):
                v = self.clue_grid[r][c]
                if isinstance(v, int):
                    self.clues[(r, c)] = v

        self.base_grid: Grid = [["." for _ in range(self.m)] for _ in range(self.n)]
        for r, c in self.clues:
            self.base_grid[r][c] = "W"

        row_clues = [0] * self.n
        col_clues = [0] * self.m
        for r, c in self.clues:
            row_clues[r] += 1
            col_clues[c] += 1
        self.influence = [[row_clues[r] + col_clues[c] for c in range(self.m)] for r in range(self.n)]

        self.logger = _Logger(verbose=verbose, max_logs=max_logs)
        self.log_level = log_level

        self._last_fail = ""

    def _msg(self, brief: str, full: str) -> str:
        return full if self.log_level == "full" else brief

    def _in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.n and 0 <= c < self.m

    def _state_key(self, grid: Grid):
        return tuple("".join(row) for row in grid)

    def _dir_info(self, grid: Grid, r: int, c: int, dr: int, dc: int):
        line = []
        rr, cc = r + dr, c + dc
        while self._in_bounds(rr, cc):
            line.append((rr, cc))
            rr += dr
            cc += dc

        mn = 0
        for rr, cc in line:
            if grid[rr][cc] == "W":
                mn += 1
                continue
            break

        mx = 0
        for rr, cc in line:
            if grid[rr][cc] == "B":
                break
            mx += 1

        return mn, mx, line

    def _set_cell(
        self,
        grid: Grid,
        r: int,
        c: int,
        token: Cell,
        reason: Optional[str],
        assignments: List[Tuple[str, Pos, str]],
    ) -> bool:
        cur = grid[r][c]
        if cur == token:
            return True
        if cur != "." and cur != token:
            self._last_fail = f"conflict at ({r},{c}): {cur} vs {token}"
            return False
        if token == "B" and (r, c) in self.clues:
            self._last_fail = f"clue cell ({r},{c}) cannot be black"
            return False

        if cur == ".":
            grid[r][c] = token
            if reason and (r, c) not in self.clues:
                assignments.append((token, (r, c), reason))
            return True

        grid[r][c] = token
        return True

    def _check_black_adjacency_hard(self, grid: Grid) -> bool:
        for r in range(self.n):
            for c in range(self.m):
                if grid[r][c] != "B":
                    continue
                for dr, dc in self.DIR4:
                    nr, nc = r + dr, c + dc
                    if self._in_bounds(nr, nc) and grid[nr][nc] == "B":
                        self._last_fail = f"adjacent black cells at ({r},{c}) and ({nr},{nc})"
                        return False
        return True

    def _white_connectivity_feasible(self, grid: Grid) -> bool:
        whites = [(r, c) for r in range(self.n) for c in range(self.m) if grid[r][c] == "W"]
        if not whites:
            return True

        q = deque([whites[0]])
        seen = {whites[0]}
        while q:
            r, c = q.popleft()
            for dr, dc in self.DIR4:
                nr, nc = r + dr, c + dc
                if not self._in_bounds(nr, nc):
                    continue
                if grid[nr][nc] == "B":
                    continue
                if (nr, nc) in seen:
                    continue
                seen.add((nr, nc))
                q.append((nr, nc))

        for pos in whites:
            if pos not in seen:
                self._last_fail = "white cells are split by black barriers"
                return False
        return True

    def _check_final(self, grid: Grid) -> bool:
        for r in range(self.n):
            for c in range(self.m):
                if grid[r][c] == ".":
                    self._last_fail = "unresolved cells remain"
                    return False

        if not self._check_black_adjacency_hard(grid):
            return False

        whites = [(r, c) for r in range(self.n) for c in range(self.m) if grid[r][c] == "W"]
        if not whites:
            self._last_fail = "no white cells"
            return False

        q = deque([whites[0]])
        seen = {whites[0]}
        while q:
            r, c = q.popleft()
            for dr, dc in self.DIR4:
                nr, nc = r + dr, c + dc
                if self._in_bounds(nr, nc) and grid[nr][nc] == "W" and (nr, nc) not in seen:
                    seen.add((nr, nc))
                    q.append((nr, nc))
        if len(seen) != len(whites):
            self._last_fail = "white cells are disconnected in final grid"
            return False

        for (r, c), clue in self.clues.items():
            if grid[r][c] != "W":
                self._last_fail = f"clue cell ({r},{c}) is not white"
                return False
            cnt = 1
            for dr, dc in self.DIR4:
                rr, cc = r + dr, c + dc
                while self._in_bounds(rr, cc) and grid[rr][cc] == "W":
                    cnt += 1
                    rr += dr
                    cc += dc
            if cnt != clue:
                self._last_fail = f"clue mismatch at ({r},{c}): expected {clue}, got {cnt}"
                return False

        return True

    def _apply_clue_rules(self, grid: Grid, assignments: List[Tuple[str, Pos, str]]) -> bool:
        changed = False

        for (r, c), clue in self.clues.items():
            if not self._set_cell(
                grid,
                r,
                c,
                "W",
                self._msg("clue cell", f"Clue cells are always white, so ({r},{c}) is W."),
                assignments,
            ):
                return False

            per_dir = []
            min_total = 1
            max_total = 1
            for dr, dc in self.DIR4:
                mn, mx, line = self._dir_info(grid, r, c, dr, dc)
                per_dir.append((mn, mx, line))
                min_total += mn
                max_total += mx

            if clue < min_total or clue > max_total:
                self._last_fail = f"clue mismatch at ({r},{c}): clue={clue}, range=[{min_total},{max_total}]"
                return False

            if clue == max_total:
                for _, mx, line in per_dir:
                    for i in range(mx):
                        rr, cc = line[i]
                        reason = self._msg(
                            "max clue saturation",
                            (
                                f"For clue ({r},{c})={clue}, the current max visible count is exactly {max_total}. "
                                f"So each still-visible ray cell, including ({rr},{cc}), must be white."
                            ),
                        )
                        cur = grid[rr][cc]
                        if cur == ".":
                            if not self._set_cell(grid, rr, cc, "W", reason, assignments):
                                return False
                            changed = True

            if clue == min_total:
                for mn, _, line in per_dir:
                    if mn < len(line):
                        rr, cc = line[mn]
                        reason = self._msg(
                            "min clue lock",
                            (
                                f"For clue ({r},{c})={clue}, the guaranteed visible count already reaches {min_total}. "
                                f"So visibility must stop at ({rr},{cc}), forcing it black."
                            ),
                        )
                        if grid[rr][cc] == ".":
                            if not self._set_cell(grid, rr, cc, "B", reason, assignments):
                                return False
                            changed = True

            target = clue - 1
            sum_mn = sum(x[0] for x in per_dir)
            sum_mx = sum(x[1] for x in per_dir)

            for mn_i, mx_i, line in per_dir:
                other_mn = sum_mn - mn_i
                other_mx = sum_mx - mx_i
                low = max(mn_i, target - other_mx)
                high = min(mx_i, target - other_mn)
                if low > high:
                    self._last_fail = f"directional bound contradiction at clue ({r},{c})"
                    return False

                for k in range(low):
                    rr, cc = line[k]
                    reason = self._msg(
                        "bound-low white",
                        (
                            f"Directional lower bound from clue ({r},{c}) forces at least {low} visible cells in this ray. "
                            f"So ({rr},{cc}) must be white."
                        ),
                    )
                    if grid[rr][cc] == ".":
                        if not self._set_cell(grid, rr, cc, "W", reason, assignments):
                            return False
                        changed = True

                if low == high and low < len(line):
                    rr, cc = line[low]
                    reason = self._msg(
                        "bound-exact black",
                        (
                            f"This ray length is fixed to {low} by clue ({r},{c}); "
                            f"the next cell ({rr},{cc}) must be black to stop visibility."
                        ),
                    )
                    if grid[rr][cc] == ".":
                        if not self._set_cell(grid, rr, cc, "B", reason, assignments):
                            return False
                        changed = True

        return changed or True

    def _contradiction_forcing(self, grid: Grid, assignments: List[Tuple[str, Pos, str]]) -> Tuple[bool, bool]:
        unknown = [(r, c) for r in range(self.n) for c in range(self.m) if grid[r][c] == "."]
        if not unknown:
            return True, False

        unknown.sort(key=lambda p: -self.influence[p[0]][p[1]])
        cap = min(24, len(unknown))

        for i in range(cap):
            r, c = unknown[i]
            feasible = []
            failed = {}

            for token in ("B", "W"):
                g2 = copy.deepcopy(grid)
                local = []
                reason = self._msg(
                    f"try {token}",
                    f"Trial for contradiction forcing: assume ({r},{c})={token}.",
                )
                if not self._set_cell(g2, r, c, token, reason, local):
                    failed[token] = self._last_fail
                    continue
                ok, _, _ = self._propagate(g2, enable_contra=False)
                if ok:
                    feasible.append(token)
                else:
                    failed[token] = self._last_fail

            if not feasible:
                self._last_fail = (
                    f"both values impossible at ({r},{c}) during contradiction forcing: "
                    f"B -> {failed.get('B', 'contradiction')}; W -> {failed.get('W', 'contradiction')}"
                )
                return False, False

            if len(feasible) == 1:
                forced = feasible[0]
                other = "W" if forced == "B" else "B"
                why = self._msg(
                    f"assume {other} fails",
                    (
                        f"Assume ({r},{c})={other} leads to contradiction: {failed.get(other, 'no completion')}. "
                        f"Therefore ({r},{c}) is forced to {forced}."
                    ),
                )
                if not self._set_cell(grid, r, c, forced, why, assignments):
                    return False, False
                return True, True

        return True, False

    def _propagate(self, grid: Grid, enable_contra: bool) -> Tuple[bool, bool, List[Tuple[str, Pos, str]]]:
        assignments: List[Tuple[str, Pos, str]] = []

        while True:
            changed = False

            for r in range(self.n):
                for c in range(self.m):
                    if grid[r][c] != "B":
                        continue
                    for dr, dc in self.DIR4:
                        nr, nc = r + dr, c + dc
                        if not self._in_bounds(nr, nc):
                            continue
                        if grid[nr][nc] == "B":
                            self._last_fail = f"adjacent black cells at ({r},{c}) and ({nr},{nc})"
                            return False, False, assignments
                        if grid[nr][nc] == ".":
                            reason = self._msg(
                                "adjacent to black",
                                (
                                    f"Black cells cannot touch orthogonally; since ({r},{c}) is black, "
                                    f"neighbor ({nr},{nc}) must be white."
                                ),
                            )
                            if not self._set_cell(grid, nr, nc, "W", reason, assignments):
                                return False, False, assignments
                            changed = True

            before = self._state_key(grid)
            ok = self._apply_clue_rules(grid, assignments)
            if not ok:
                return False, False, assignments
            if self._state_key(grid) != before:
                changed = True

            if not self._check_black_adjacency_hard(grid):
                return False, False, assignments
            if not self._white_connectivity_feasible(grid):
                return False, False, assignments

            if not changed and enable_contra:
                force_ok, forced = self._contradiction_forcing(grid, assignments)
                if not force_ok:
                    return False, False, assignments
                if forced:
                    changed = True

            if not changed:
                break

        return True, True, assignments

    def _choose_branch(self, grid: Grid) -> Tuple[Optional[Pos], List[str]]:
        best_pos = None
        best_vals: List[str] = []
        best_key = None

        for r in range(self.n):
            for c in range(self.m):
                if grid[r][c] != ".":
                    continue

                feasible = []
                for token in ("B", "W"):
                    g2 = copy.deepcopy(grid)
                    if not self._set_cell(g2, r, c, token, None, []):
                        continue
                    ok, _, _ = self._propagate(g2, enable_contra=False)
                    if ok:
                        feasible.append(token)

                if not feasible:
                    self._last_fail = f"both values impossible at ({r},{c})"
                    return None, []

                key = (len(feasible), -self.influence[r][c])
                if best_key is None or key < best_key:
                    best_key = key
                    best_pos = (r, c)
                    best_vals = feasible
                    if len(feasible) == 1:
                        return best_pos, best_vals

        return best_pos, best_vals

    def _search_one(
        self,
        grid: Grid,
        depth: int,
        depth_limit: Optional[int],
        stage_name: str,
    ) -> Tuple[Optional[Grid], List[Tuple[str, Pos, str]]]:
        ok, _, base_assignments = self._propagate(grid, enable_contra=True)
        if not ok:
            return None, []

        if self._check_final(grid):
            return grid, base_assignments

        if depth_limit is not None and depth >= depth_limit:
            self._last_fail = f"depth limit reached at d={depth}"
            return None, []

        pos, vals = self._choose_branch(grid)
        if pos is None or not vals:
            return None, []

        r, c = pos
        fail_reasons = []

        for token in vals:
            g2 = copy.deepcopy(grid)
            branch_assignments: List[Tuple[str, Pos, str]] = []
            if fail_reasons:
                why = self._msg(
                    f"{stage_name} backtrack",
                    f"At d={depth}, previous branch failed ({fail_reasons[-1]}), so set ({r},{c})={token} and continue.",
                )
            else:
                why = self._msg(
                    f"{stage_name} branch",
                    f"At d={depth}, rules are exhausted; choose branch ({r},{c})={token}.",
                )

            if not self._set_cell(g2, r, c, token, why, branch_assignments):
                fail_reasons.append(self._last_fail)
                continue

            ans, deeper = self._search_one(g2, depth + 1, depth_limit, stage_name)
            if ans is not None:
                return ans, base_assignments + branch_assignments + deeper

            fail_reasons.append(self._last_fail or f"branch ({r},{c})={token} failed")

        self._last_fail = f"both branches failed at ({r},{c}): {' ; '.join(fail_reasons[:2])}"
        return None, []

    def find_one_staged(self) -> Tuple[Optional[Grid], List[Tuple[str, Pos, str]]]:
        # 1) Strong rules only.
        g = copy.deepcopy(self.base_grid)
        ok, _, assignments = self._propagate(g, enable_contra=True)
        if ok and self._check_final(g):
            return g, assignments

        # 2) Short-depth backtracking.
        for cap in (3, 6):
            g2 = copy.deepcopy(self.base_grid)
            ans, logs = self._search_one(g2, depth=0, depth_limit=cap, stage_name=f"short-depth({cap})")
            if ans is not None:
                return ans, logs

        # 3) Full fallback search.
        g3 = copy.deepcopy(self.base_grid)
        return self._search_one(g3, depth=0, depth_limit=None, stage_name="full-search")

def _normalize_observation(observation):
    if isinstance(observation, dict):
        if "data" in observation and isinstance(observation["data"], list):
            observation = observation["data"]
        elif (
            "original_data" in observation
            and isinstance(observation["original_data"], dict)
            and "data" in observation["original_data"]
        ):
            observation = observation["original_data"]["data"]

    if isinstance(observation, list) and observation and isinstance(observation[0], list):
        n = len(observation)
        m = len(observation[0])
        for row in observation:
            if len(row) != m:
                raise ValueError("kurodoko observation grid must be rectangular")
        clue_grid = [[None for _ in range(m)] for _ in range(n)]
        for r in range(n):
            for c in range(m):
                if isinstance(observation[r][c], int):
                    clue_grid[r][c] = int(observation[r][c])
        return clue_grid

    if isinstance(observation, dict) and observation and all(
        isinstance(k, tuple) and len(k) == 2 for k in observation
    ):
        clues = {(int(r), int(c)): int(v) for (r, c), v in observation.items()}
        max_r = max(r for r, _ in clues)
        max_c = max(c for _, c in clues)
        n, m = max_r + 1, max_c + 1
        clue_grid = [[None for _ in range(m)] for _ in range(n)]
        for (r, c), v in clues.items():
            clue_grid[r][c] = v
        return clue_grid

    raise ValueError("unsupported observation format for kurodoko")



def _build_answer_grid(clue_grid: Sequence[Sequence[Optional[int]]], color_grid: Grid):
    n = len(clue_grid)
    m = len(clue_grid[0])
    out = [[None for _ in range(m)] for _ in range(n)]
    for r in range(n):
        for c in range(m):
            clue = clue_grid[r][c]
            if isinstance(clue, int):
                out[r][c] = clue
            else:
                out[r][c] = "B" if color_grid[r][c] == "B" else None
    return out



def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 8000,
    log_level: str = "brief",
):
    """
    Solve Kurodoko.

    Returns:
    - solved full grid in construction/kurodoko.py answer format:
      clue ints stay ints, black cells are 'B', white non-clue cells are None.
    - "No Solution" if unsatisfiable or non-unique.

    Log format (when verbose=True):
    - one line per determined non-clue cell
    - exact template: TOKEN | POS | WHY
    - log_level='brief' or 'full'
    """
    if log_level not in {"brief", "full"}:
        raise ValueError("log_level must be 'brief' or 'full'")

    clue_grid = _normalize_observation(observation)

    # Find one solution with staged priority:
    # strong rules > short-depth backtracking > full search fallback.
    solver = _KurodokoSolver(
        clue_grid=clue_grid,
        verbose=verbose,
        max_logs=max_logs,
        log_level=log_level,
    )
    one, _ = solver.find_one_staged()
    if one is None:
        return "No Solution"
    return _build_answer_grid(clue_grid, one)
