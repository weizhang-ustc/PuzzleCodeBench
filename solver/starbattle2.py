from __future__ import annotations

import copy
from typing import Dict, List, Optional, Sequence, Tuple

Grid = List[List[Optional[str]]]
Observation = Sequence[Sequence[int]]
Pos = Tuple[int, int]


def _normalize_observation(observation):
    data = observation
    if isinstance(data, dict):
        data = data.get("data", data.get("regions", data))

    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError("observation must be a non-empty 2D region-id grid")

    width = len(data[0])
    if width == 0:
        raise ValueError("observation rows must be non-empty")

    for row in data:
        if len(row) != width:
            raise ValueError("observation must be rectangular")

    return [list(row) for row in data]


class _StarBattleSolver:
    def __init__(
        self,
        region_grid: Observation,
        stars_per_unit: int,
    ):
        self.region_grid = [list(row) for row in region_grid]
        self.rows = len(self.region_grid)
        self.cols = len(self.region_grid[0])
        self.k = stars_per_unit
        self._last_fail = ""

        region_ids = sorted({rid for row in self.region_grid for rid in row})
        self.region_index: Dict[int, int] = {rid: idx for idx, rid in enumerate(region_ids)}
        self.region_count = len(region_ids)

        self.region_of = [
            [self.region_index[self.region_grid[r][c]] for c in range(self.cols)]
            for r in range(self.rows)
        ]

        self.row_cells = [[(r, c) for c in range(self.cols)] for r in range(self.rows)]
        self.col_cells = [[(r, c) for r in range(self.rows)] for c in range(self.cols)]
        self.reg_cells: List[List[Pos]] = [[] for _ in range(self.region_count)]
        for r in range(self.rows):
            for c in range(self.cols):
                self.reg_cells[self.region_of[r][c]].append((r, c))

        # cell_state: -1 unknown, 0 non-star, 1 star
        self.cell_state = [[-1] * self.cols for _ in range(self.rows)]
        self.blocked = [[0] * self.cols for _ in range(self.rows)]

        self.row_left = [self.k] * self.rows
        self.col_left = [self.k] * self.cols
        self.reg_left = [self.k] * self.region_count

        self._neighbors8 = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)]

        self.influence = [[0] * self.cols for _ in range(self.rows)]
        for r in range(self.rows):
            for c in range(self.cols):
                reg = self.region_of[r][c]
                self.influence[r][c] = len(self.row_cells[r]) + len(self.col_cells[c]) + len(self.reg_cells[reg])

    def _msg(self, brief: str, full: str) -> str:
        return brief

    def _in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols

    def _snapshot(self):
        return (
            copy.deepcopy(self.cell_state),
            copy.deepcopy(self.blocked),
            self.row_left[:],
            self.col_left[:],
            self.reg_left[:],
            self._last_fail,
        )

    def _restore(self, snap):
        self.cell_state, self.blocked, self.row_left, self.col_left, self.reg_left, self._last_fail = snap

    def _state_key(self):
        rows = []
        for r in range(self.rows):
            rows.append("".join(str(self.cell_state[r][c]) for c in range(self.cols)))
        return tuple(rows)

    def _can_place_star(self, r: int, c: int) -> bool:
        if self.cell_state[r][c] != -1:
            return False
        if self.blocked[r][c] != 0:
            return False
        if self.row_left[r] <= 0 or self.col_left[c] <= 0:
            return False
        if self.reg_left[self.region_of[r][c]] <= 0:
            return False
        return True

    def _set_nonstar(self, r: int, c: int, why: Optional[str], logs: List[Tuple[str, Pos, str]]) -> bool:
        cur = self.cell_state[r][c]
        if cur == 0:
            return True
        if cur == 1:
            self._last_fail = f"conflict at ({r},{c}): already star, cannot set non-star"
            return False
        self.cell_state[r][c] = 0
        if why is not None:
            logs.append(("X", (r, c), why))
        return True

    def _set_star(self, r: int, c: int, why: Optional[str], logs: List[Tuple[str, Pos, str]]) -> bool:
        cur = self.cell_state[r][c]
        if cur == 1:
            return True
        if cur == 0:
            self._last_fail = f"conflict at ({r},{c}): already non-star, cannot set star"
            return False
        if not self._can_place_star(r, c):
            self._last_fail = f"cannot place star at ({r},{c})"
            return False

        self.cell_state[r][c] = 1
        self.row_left[r] -= 1
        self.col_left[c] -= 1
        reg = self.region_of[r][c]
        self.reg_left[reg] -= 1

        for dr, dc in self._neighbors8:
            nr, nc = r + dr, c + dc
            if self._in_bounds(nr, nc):
                self.blocked[nr][nc] += 1

        if why is not None:
            logs.append(("S", (r, c), why))
        return True

    def _validate_remaining_counts(self) -> bool:
        if any(v < 0 for v in self.row_left):
            self._last_fail = "row quota overfilled"
            return False
        if any(v < 0 for v in self.col_left):
            self._last_fail = "column quota overfilled"
            return False
        if any(v < 0 for v in self.reg_left):
            self._last_fail = "region quota overfilled"
            return False

        sr = sum(self.row_left)
        sc = sum(self.col_left)
        sg = sum(self.reg_left)
        if not (sr == sc == sg):
            self._last_fail = f"remaining quota mismatch rows={sr}, cols={sc}, regions={sg}"
            return False
        return True

    def _unit_force(self, unit_cells: List[Pos], need: int, unit_name: str, logs: List[Tuple[str, Pos, str]]) -> bool:
        # Stars fixed in this unit are already accounted by need (= left quota).
        cands = [(r, c) for (r, c) in unit_cells if self._can_place_star(r, c)]
        unknowns = [(r, c) for (r, c) in unit_cells if self.cell_state[r][c] == -1]

        if need < 0:
            self._last_fail = f"{unit_name} overfilled"
            return False
        if need > len(cands):
            self._last_fail = f"{unit_name} needs {need} stars but only {len(cands)} candidates remain"
            return False

        if need == 0:
            for r, c in unknowns:
                why = self._msg(
                    f"{unit_name} quota met",
                    f"{unit_name} already has required stars, so ({r},{c}) is forced non-star.",
                )
                if not self._set_nonstar(r, c, why, logs):
                    return False

        if need == len(cands):
            for r, c in cands:
                why = self._msg(
                    f"{unit_name} all candidates",
                    f"{unit_name} still needs {need} stars and has exactly {len(cands)} candidates, so ({r},{c}) must be a star.",
                )
                if not self._set_star(r, c, why, logs):
                    return False

        return True

    def _propagate(self) -> Tuple[bool, List[Tuple[str, Pos, str]]]:
        logs: List[Tuple[str, Pos, str]] = []

        while True:
            changed = False

            if not self._validate_remaining_counts():
                return False, logs

            # Rule: adjacency around confirmed stars.
            for r in range(self.rows):
                for c in range(self.cols):
                    if self.cell_state[r][c] != 1:
                        continue
                    for dr, dc in self._neighbors8:
                        nr, nc = r + dr, c + dc
                        if not self._in_bounds(nr, nc):
                            continue
                        if self.cell_state[nr][nc] == 1 and (nr, nc) != (r, c):
                            self._last_fail = f"adjacent stars conflict at ({r},{c}) and ({nr},{nc})"
                            return False, logs
                        if self.cell_state[nr][nc] == -1:
                            why = self._msg(
                                "adjacent to star",
                                f"Stars cannot touch (including diagonals), so ({nr},{nc}) is non-star.",
                            )
                            if not self._set_nonstar(nr, nc, why, logs):
                                return False, logs

            # Rule: impossible candidates become non-stars.
            for r in range(self.rows):
                for c in range(self.cols):
                    if self.cell_state[r][c] != -1:
                        continue
                    if not self._can_place_star(r, c):
                        why = self._msg(
                            "impossible star",
                            f"Cell ({r},{c}) cannot satisfy star constraints/quota, so it is non-star.",
                        )
                        if not self._set_nonstar(r, c, why, logs):
                            return False, logs

            # Unit forcing: rows, columns, regions.
            for r in range(self.rows):
                if not self._unit_force(self.row_cells[r], self.row_left[r], f"row {r}", logs):
                    return False, logs
            for c in range(self.cols):
                if not self._unit_force(self.col_cells[c], self.col_left[c], f"col {c}", logs):
                    return False, logs
            for g in range(self.region_count):
                if not self._unit_force(self.reg_cells[g], self.reg_left[g], f"region {g}", logs):
                    return False, logs

            if not self._validate_remaining_counts():
                return False, logs

            # Detect whether we changed in this round by comparing unknown count / quotas snapshot.
            # (Fast enough for puzzle sizes in this repo.)
            # Using state hash keeps logic simple and robust.
            state_before = self._state_key()
            # no-op; we already applied all rules. changed iff any log appended since loop start.
            # To avoid extra bookkeeping, we infer from whether new logs were added.
            # If no log was added in this iteration, we are at fixed point.
            if not logs:
                break

            # If logs were added but state no longer changes in next pass, loop exits next iteration.
            # Prepare next iteration by clearing logs visibility check via a marker.
            # We still need to return all logs, so we keep a cumulative list and use counter snapshot.
            # Implement with a manual index check.
            # (Handled below by per-iteration counting.)
            break

        # Proper fixed-point iteration with per-iteration delta logs.
        # Re-run in a controlled loop to avoid missing chained implications.
        cumulative = logs[:]
        while True:
            start = len(cumulative)

            if not self._validate_remaining_counts():
                return False, cumulative

            for r in range(self.rows):
                for c in range(self.cols):
                    if self.cell_state[r][c] != 1:
                        continue
                    for dr, dc in self._neighbors8:
                        nr, nc = r + dr, c + dc
                        if not self._in_bounds(nr, nc):
                            continue
                        if self.cell_state[nr][nc] == 1 and (nr, nc) != (r, c):
                            self._last_fail = f"adjacent stars conflict at ({r},{c}) and ({nr},{nc})"
                            return False, cumulative
                        if self.cell_state[nr][nc] == -1:
                            why = self._msg("adjacent to star", f"Stars cannot touch, so ({nr},{nc}) is non-star.")
                            if not self._set_nonstar(nr, nc, why, cumulative):
                                return False, cumulative

            for r in range(self.rows):
                for c in range(self.cols):
                    if self.cell_state[r][c] != -1:
                        continue
                    if not self._can_place_star(r, c):
                        why = self._msg("impossible star", f"Cell ({r},{c}) cannot be star, so it is non-star.")
                        if not self._set_nonstar(r, c, why, cumulative):
                            return False, cumulative

            for r in range(self.rows):
                if not self._unit_force(self.row_cells[r], self.row_left[r], f"row {r}", cumulative):
                    return False, cumulative
            for c in range(self.cols):
                if not self._unit_force(self.col_cells[c], self.col_left[c], f"col {c}", cumulative):
                    return False, cumulative
            for g in range(self.region_count):
                if not self._unit_force(self.reg_cells[g], self.reg_left[g], f"region {g}", cumulative):
                    return False, cumulative

            if not self._validate_remaining_counts():
                return False, cumulative

            if len(cumulative) == start:
                break

        return True, cumulative

    def _is_complete(self) -> bool:
        if any(v != 0 for v in self.row_left):
            return False
        if any(v != 0 for v in self.col_left):
            return False
        if any(v != 0 for v in self.reg_left):
            return False
        return all(self.cell_state[r][c] != -1 for r in range(self.rows) for c in range(self.cols))

    def _choose_branch_cell(self) -> Tuple[Optional[Pos], List[str], Dict[str, str]]:
        best_pos = None
        best_tokens: List[str] = []
        best_key = None
        best_fail: Dict[str, str] = {}

        for r in range(self.rows):
            for c in range(self.cols):
                if self.cell_state[r][c] != -1:
                    continue

                feasible = []
                fail_reason: Dict[str, str] = {}

                for token in ("S", "X"):
                    snap = self._snapshot()
                    local: List[Tuple[str, Pos, str]] = []
                    ok = False
                    if token == "S":
                        ok = self._set_star(r, c, None, local)
                    else:
                        ok = self._set_nonstar(r, c, None, local)
                    if ok:
                        ok, _ = self._propagate()
                    if ok:
                        feasible.append(token)
                    else:
                        fail_reason[token] = self._last_fail or "contradiction"
                    self._restore(snap)

                if not feasible:
                    self._last_fail = f"both S/X impossible at ({r},{c})"
                    return None, [], fail_reason

                key = (len(feasible), -self.influence[r][c])
                if best_key is None or key < best_key:
                    best_key = key
                    best_pos = (r, c)
                    best_tokens = feasible
                    best_fail = fail_reason
                    if len(feasible) == 1:
                        return best_pos, best_tokens, best_fail

        return best_pos, best_tokens, best_fail

    def _choose_branch_cell_fast(self) -> Tuple[Optional[Pos], List[str]]:
        best_pos = None
        best_tokens: List[str] = []
        best_key = None

        for r in range(self.rows):
            for c in range(self.cols):
                if self.cell_state[r][c] != -1:
                    continue
                tokens = ["S", "X"] if self._can_place_star(r, c) else ["X"]
                key = (len(tokens), -self.influence[r][c])
                if best_key is None or key < best_key:
                    best_key = key
                    best_pos = (r, c)
                    best_tokens = tokens
                    if len(tokens) == 1:
                        return best_pos, best_tokens

        return best_pos, best_tokens

    def _search_one(self, depth: int, depth_limit: Optional[int], stage: str):
        ok, base_logs = self._propagate()
        if not ok:
            return None, []

        if self._is_complete():
            return self._capture_solution(), base_logs

        if depth_limit is not None and depth >= depth_limit:
            self._last_fail = f"depth limit reached at d={depth}"
            return None, []

        pos, tokens = self._choose_branch_cell_fast()
        if pos is None or not tokens:
            return None, []

        r, c = pos
        fail_chain = []

        for token in tokens:
            snap = self._snapshot()
            branch_logs: List[Tuple[str, Pos, str]] = []

            if fail_chain:
                why = self._msg(
                    f"{stage} backtrack",
                    f"At d={depth}, previous branch failed ({fail_chain[-1]}), so set ({r},{c})={token}.",
                )
            else:
                why = self._msg(
                    f"{stage} branch",
                    f"At d={depth}, rule propagation is saturated; choose ({r},{c})={token}.",
                )

            if token == "S":
                set_ok = self._set_star(r, c, why, branch_logs)
            else:
                set_ok = self._set_nonstar(r, c, why, branch_logs)

            if set_ok:
                ans, deeper = self._search_one(depth + 1, depth_limit, stage)
                if ans is not None:
                    return ans, base_logs + branch_logs + deeper

            fail_chain.append(self._last_fail or f"branch ({r},{c})={token} failed")
            self._restore(snap)

        self._last_fail = f"both branches failed at ({r},{c})"
        return None, []

    def _capture_solution(self) -> Grid:
        out: Grid = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        for r in range(self.rows):
            for c in range(self.cols):
                if self.cell_state[r][c] == 1:
                    out[r][c] = "S"
        return out



    def _solve_fast(self) -> Optional[Grid]:
        stars = [[False] * self.cols for _ in range(self.rows)]
        blocked = [[0] * self.cols for _ in range(self.rows)]
        row_left = [self.k] * self.rows
        col_left = [self.k] * self.cols
        reg_left = [self.k] * self.region_count

        def can_place(r: int, c: int) -> bool:
            if stars[r][c]:
                return False
            if blocked[r][c] != 0:
                return False
            if row_left[r] <= 0 or col_left[c] <= 0:
                return False
            if reg_left[self.region_of[r][c]] <= 0:
                return False
            return True

        def place(r: int, c: int):
            stars[r][c] = True
            row_left[r] -= 1
            col_left[c] -= 1
            reg_left[self.region_of[r][c]] -= 1
            touched = []
            for dr, dc in self._neighbors8:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    blocked[nr][nc] += 1
                    touched.append((nr, nc))
            return touched

        def unplace(r: int, c: int, touched):
            for nr, nc in touched:
                blocked[nr][nc] -= 1
            stars[r][c] = False
            row_left[r] += 1
            col_left[c] += 1
            reg_left[self.region_of[r][c]] += 1

        def infeasible(start_row: int) -> bool:
            for r in range(start_row, self.rows):
                if row_left[r] < 0:
                    return True
            if any(v < 0 for v in col_left) or any(v < 0 for v in reg_left):
                return True

            row_avail = [0] * self.rows
            col_avail = [0] * self.cols
            reg_avail = [0] * self.region_count
            for r in range(start_row, self.rows):
                for c in range(self.cols):
                    if can_place(r, c):
                        row_avail[r] += 1
                        col_avail[c] += 1
                        reg_avail[self.region_of[r][c]] += 1

            for r in range(start_row, self.rows):
                if row_avail[r] < row_left[r]:
                    return True
            for c in range(self.cols):
                if col_avail[c] < col_left[c]:
                    return True
            for g in range(self.region_count):
                if reg_avail[g] < reg_left[g]:
                    return True
            return False

        def row_patterns(r: int):
            need = row_left[r]
            if need == 0:
                return [[]]
            candidates = [c for c in range(self.cols) if can_place(r, c)]
            if len(candidates) < need:
                return []
            out = []

            def dfs(idx: int, picked: List[int], reg_use: Dict[int, int]):
                if len(picked) == need:
                    out.append(picked[:])
                    return
                remain = need - len(picked)
                if len(candidates) - idx < remain:
                    return
                for i in range(idx, len(candidates)):
                    c = candidates[i]
                    if picked and c - picked[-1] <= 1:
                        continue
                    reg = self.region_of[r][c]
                    used = reg_use.get(reg, 0)
                    if used >= reg_left[reg]:
                        continue
                    picked.append(c)
                    reg_use[reg] = used + 1
                    dfs(i + 1, picked, reg_use)
                    picked.pop()
                    if used == 0:
                        del reg_use[reg]
                    else:
                        reg_use[reg] = used

            dfs(0, [], {})
            out.sort(key=lambda cols: sum(col_left[c] for c in cols))
            return out

        def search(r: int) -> bool:
            if r == self.rows:
                return all(v == 0 for v in row_left) and all(v == 0 for v in col_left) and all(v == 0 for v in reg_left)
            if infeasible(r):
                return False
            pats = row_patterns(r)
            if not pats:
                return False
            for cols in pats:
                touched_all = []
                ok = True
                for c in cols:
                    if not can_place(r, c):
                        ok = False
                        break
                    touched_all.append((c, place(r, c)))
                if ok and row_left[r] == 0 and search(r + 1):
                    return True
                for c, touched in reversed(touched_all):
                    unplace(r, c, touched)
            return False

        if not search(0):
            return None
        out: Grid = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        for r in range(self.rows):
            for c in range(self.cols):
                if stars[r][c]:
                    out[r][c] = "S"
        return out

    def solve_unique(self) -> Optional[Grid]:
        fast_answer = self._solve_fast()
        if fast_answer is not None:
            return fast_answer

        snap0 = self._snapshot()
        ok0, _ = self._propagate()
        if ok0 and self._is_complete():
            answer = self._capture_solution()
            self._restore(snap0)
            return answer
        self._restore(snap0)

        for cap in (3, 6):
            snap = self._snapshot()
            ans, _ = self._search_one(depth=0, depth_limit=cap, stage=f"short-depth({cap})")
            self._restore(snap)
            if ans is not None:
                return ans

        snap = self._snapshot()
        ans, _ = self._search_one(depth=0, depth_limit=None, stage="full-search")
        self._restore(snap)
        return ans


def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 6000,
    log_level: str = "brief",
):
    region_grid = _normalize_observation(observation)
    solver = _StarBattleSolver(
        region_grid=region_grid,
        stars_per_unit=2,
    )
    answer = solver.solve_unique()
    return answer if answer is not None else "No Solution"
