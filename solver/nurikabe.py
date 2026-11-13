from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Set, Tuple

Pos = Tuple[int, int]
Grid = List[List[int]]  # -1 unknown, 0 black, >0 island id


class _NurikabeSolver:
    DIR4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

    def __init__(self, number_grid: List[List[Optional[int]]]):
        self.n = len(number_grid)
        self.nums = [row[:] for row in number_grid]
        self.state: Grid = [[-1 for _ in range(self.n)] for _ in range(self.n)]
        self._last_fail = ""
        self._dead = set()

        self.cells = [(r, c) for r in range(self.n) for c in range(self.n)]
        self.neighbors: List[List[List[Pos]]] = [[[] for _ in range(self.n)] for _ in range(self.n)]
        for r in range(self.n):
            for c in range(self.n):
                if r > 0:
                    self.neighbors[r][c].append((r - 1, c))
                if r + 1 < self.n:
                    self.neighbors[r][c].append((r + 1, c))
                if c > 0:
                    self.neighbors[r][c].append((r, c - 1))
                if c + 1 < self.n:
                    self.neighbors[r][c].append((r, c + 1))

        self.clues: List[Tuple[Pos, int]] = []
        for r in range(self.n):
            if len(self.nums[r]) != self.n:
                raise ValueError("nurikabe grid must be square")
            for c in range(self.n):
                v = self.nums[r][c]
                if v is not None:
                    self.clues.append(((r, c), int(v)))

        self.k = len(self.clues)
        self.targets = [v for _, v in self.clues]
        self.black_target = self.n * self.n - sum(self.targets)

        self.island_cells: List[Set[Pos]] = [set() for _ in range(self.k)]
        for i, ((r, c), _) in enumerate(self.clues, start=1):
            self.state[r][c] = i
            self.island_cells[i - 1].add((r, c))

        self.black_count = 0
        self.unknown_count = self.n * self.n - self.k
        self._rev = 0
        self._reach_cache_rev = -1
        self._reach_cache: Dict[int, Set[Pos]] = {}
        self._reach_union_cache: Optional[Set[Pos]] = None

    def _inb(self, r: int, c: int) -> bool:
        return 0 <= r < self.n and 0 <= c < self.n

    def _neighbors(self, r: int, c: int):
        yield from self.neighbors[r][c]

    def _snapshot(self):
        return (
            [row[:] for row in self.state],
            [set(s) for s in self.island_cells],
            self.black_count,
            self.unknown_count,
            self._rev,
            self._last_fail,
        )

    def _restore(self, snap):
        self.state, self.island_cells, self.black_count, self.unknown_count, self._rev, self._last_fail = snap
        self._reach_cache_rev = -1
        self._reach_cache = {}
        self._reach_union_cache = None

    def _state_key(self):
        return tuple(tuple(row) for row in self.state)

    def _set_black(self, r: int, c: int) -> bool:
        cur = self.state[r][c]
        if cur == 0:
            return True
        if cur > 0:
            self._last_fail = f"cannot black clue/island cell ({r},{c})"
            return False
        self.state[r][c] = 0
        self.black_count += 1
        self.unknown_count -= 1
        self._rev += 1
        return True

    def _set_island(self, r: int, c: int, iid: int) -> bool:
        cur = self.state[r][c]
        if cur == iid:
            return True
        if cur == 0 or (cur > 0 and cur != iid):
            self._last_fail = f"cell ({r},{c}) cannot join island {iid}"
            return False
        self.state[r][c] = iid
        self.island_cells[iid - 1].add((r, c))
        self.unknown_count -= 1
        self._rev += 1
        return True

    def _check_numbered_white(self) -> bool:
        for i, ((r, c), _) in enumerate(self.clues, start=1):
            if self.state[r][c] != i:
                self._last_fail = f"clue cell ({r},{c}) changed"
                return False
        return True

    def _check_black_2x2(self) -> bool:
        for r in range(self.n - 1):
            for c in range(self.n - 1):
                if (
                    self.state[r][c] == 0
                    and self.state[r + 1][c] == 0
                    and self.state[r][c + 1] == 0
                    and self.state[r + 1][c + 1] == 0
                ):
                    self._last_fail = f"2x2 black at ({r},{c})"
                    return False
        return True

    def _check_black_quota(self) -> bool:
        b = self.black_count
        u = self.unknown_count
        if b > self.black_target or b + u < self.black_target:
            self._last_fail = "black quota impossible"
            return False
        return True

    def _black_connectivity_feasible(self) -> bool:
        if self.black_count == 0:
            return True

        start = None
        for r, c in self.cells:
            if self.state[r][c] == 0:
                start = (r, c)
                break
        if start is None:
            return True

        seen = {start}
        q = deque([start])
        while q:
            r, c = q.popleft()
            for rr, cc in self.neighbors[r][c]:
                if self.state[rr][cc] > 0 or (rr, cc) in seen:
                    continue
                seen.add((rr, cc))
                q.append((rr, cc))

        for r, c in self.cells:
            if self.state[r][c] == 0 and (r, c) not in seen:
                self._last_fail = "black cells cannot stay connected"
                return False
        return True

    def _island_frontier(self, iid: int) -> Set[Pos]:
        out: Set[Pos] = set()
        for r, c in self.island_cells[iid - 1]:
            for rr, cc in self.neighbors[r][c]:
                if self.state[rr][cc] == -1:
                    out.add((rr, cc))
        return out

    def _island_reachable(self, iid: int) -> Set[Pos]:
        if self._reach_cache_rev != self._rev:
            self._reach_cache_rev = self._rev
            self._reach_cache = {}
            self._reach_union_cache = None
        cached = self._reach_cache.get(iid)
        if cached is not None:
            return cached

        start = next(iter(self.island_cells[iid - 1]))
        seen = {start}
        q = deque([start])
        state = self.state
        neighbors = self.neighbors
        while q:
            r, c = q.popleft()
            for rr, cc in neighbors[r][c]:
                st = state[rr][cc]
                if st == 0 or (st > 0 and st != iid) or (rr, cc) in seen:
                    continue
                seen.add((rr, cc))
                q.append((rr, cc))
        self._reach_cache[iid] = seen
        return seen

    def _reachable_union(self) -> Set[Pos]:
        if self._reach_cache_rev != self._rev:
            self._reach_cache_rev = self._rev
            self._reach_cache = {}
            self._reach_union_cache = None
        if self._reach_union_cache is not None:
            return self._reach_union_cache

        union: Set[Pos] = set()
        for iid in range(1, self.k + 1):
            union.update(self._island_reachable(iid))
        self._reach_union_cache = union
        return union

    def _island_bounds_ok(self) -> bool:
        for iid in range(1, self.k + 1):
            size = len(self.island_cells[iid - 1])
            tgt = self.targets[iid - 1]
            if size > tgt:
                self._last_fail = f"island {iid} too large"
                return False
            if size < tgt:
                reach = self._island_reachable(iid)
                if len(reach) < tgt:
                    self._last_fail = f"island {iid} cannot reach size {tgt}"
                    return False
        return True

    def _reachability_forcing(self) -> bool:
        changed = False
        reachable_union = self._reachable_union()

        for r, c in self.cells:
            if self.state[r][c] != -1:
                continue

            if (r, c) not in reachable_union:
                if not self._set_black(r, c):
                    return False
                changed = True

        return changed

    def _separation_rule(self) -> bool:
        changed = False
        for r, c in self.cells:
            if self.state[r][c] != -1:
                continue
            adj_islands = set()
            for rr, cc in self.neighbors[r][c]:
                if self.state[rr][cc] > 0:
                    adj_islands.add(self.state[rr][cc])
            if len(adj_islands) >= 2:
                if not self._set_black(r, c):
                    return False
                changed = True
        return changed

    def _quota_forcing(self) -> bool:
        changed = False
        b = self.black_count
        unknown = [(r, c) for r, c in self.cells if self.state[r][c] == -1]
        if b == self.black_target:
            for r, c in unknown:
                cand = [iid for iid in self._adjacent_islands(r, c) if len(self.island_cells[iid - 1]) < self.targets[iid - 1]]
                if len(cand) == 1:
                    if not self._set_island(r, c, cand[0]):
                        return False
                    changed = True
        elif b + len(unknown) == self.black_target:
            for r, c in unknown:
                if not self._set_black(r, c):
                    return False
                changed = True
        return changed

    def _adjacent_islands(self, r: int, c: int) -> Set[int]:
        out = set()
        for rr, cc in self.neighbors[r][c]:
            if self.state[rr][cc] > 0:
                out.add(self.state[rr][cc])
        return out

    def _island_forcing(self) -> bool:
        changed = False
        for iid in range(1, self.k + 1):
            tgt = self.targets[iid - 1]
            cells = self.island_cells[iid - 1]
            if len(cells) == tgt:
                for r, c in list(cells):
                    for rr, cc in self.neighbors[r][c]:
                        if self.state[rr][cc] == -1:
                            if not self._set_black(rr, cc):
                                return False
                            changed = True
                continue

            reach = self._island_reachable(iid)
            if len(reach) == tgt:
                for r, c in reach:
                    if self.state[r][c] == -1:
                        if not self._set_island(r, c, iid):
                            return False
                        changed = True
                continue

            frontier = self._island_frontier(iid)
            if len(cells) < tgt and len(frontier) == 1:
                (fr, fc) = next(iter(frontier))
                if not self._set_island(fr, fc, iid):
                    return False
                changed = True

        return changed

    def _propagate(self):
        self._last_fail = ""
        while True:
            if not self._check_numbered_white() or not self._check_black_2x2() or not self._check_black_quota():
                return False
            if not self._black_connectivity_feasible() or not self._island_bounds_ok():
                return False

            changed = False
            for fn in (self._separation_rule, self._reachability_forcing, self._island_forcing, self._quota_forcing):
                res = fn()
                if res is False and self._last_fail:
                    return False
                changed = changed or bool(res)

            if not changed:
                break
        return True

    def _final_ok(self) -> bool:
        if any(self.state[r][c] == -1 for r, c in self.cells):
            return False

        if not self._check_numbered_white() or not self._check_black_2x2() or not self._check_black_quota():
            return False

        blacks = [(r, c) for r, c in self.cells if self.state[r][c] == 0]
        if not blacks:
            self._last_fail = "no black cells"
            return False
        seen = {blacks[0]}
        q = deque([blacks[0]])
        while q:
            r, c = q.popleft()
            for rr, cc in self.neighbors[r][c]:
                if self.state[rr][cc] == 0 and (rr, cc) not in seen:
                    seen.add((rr, cc))
                    q.append((rr, cc))
        if len(seen) != len(blacks):
            self._last_fail = "black disconnected"
            return False

        visited = set()
        clue_pos_to_iid = {pos: i + 1 for i, (pos, _) in enumerate(self.clues)}
        for r, c in self.cells:
            if self.state[r][c] == 0 or (r, c) in visited:
                continue
            iid = self.state[r][c]
            comp = set([(r, c)])
            q = deque([(r, c)])
            visited.add((r, c))
            while q:
                cr, cc = q.popleft()
                for rr, cc2 in self.neighbors[cr][cc]:
                    if self.state[rr][cc2] == iid and (rr, cc2) not in visited:
                        visited.add((rr, cc2))
                        comp.add((rr, cc2))
                        q.append((rr, cc2))

            clues_here = [p for p in comp if p in clue_pos_to_iid]
            if len(clues_here) != 1:
                self._last_fail = "white component clue count != 1"
                return False
            cid = clue_pos_to_iid[clues_here[0]]
            if len(comp) != self.targets[cid - 1]:
                self._last_fail = "island size mismatch"
                return False

        return True

    def _would_make_2x2_black(self, r: int, c: int) -> bool:
        for dr in (-1, 0):
            for dc in (-1, 0):
                r0, c0 = r + dr, c + dc
                if r0 < 0 or c0 < 0 or r0 + 1 >= self.n or c0 + 1 >= self.n:
                    continue
                blacks = 0
                for rr in (r0, r0 + 1):
                    for cc in (c0, c0 + 1):
                        if rr == r and cc == c:
                            blacks += 1
                        elif self.state[rr][cc] == 0:
                            blacks += 1
                if blacks == 4:
                    return True
        return False

    def _candidate_values(self, r: int, c: int) -> List[Tuple[str, int]]:
        out: List[Tuple[str, int]] = []
        if self.black_count < self.black_target and not self._would_make_2x2_black(r, c):
            out.append(("B", 0))

        adj = self._adjacent_islands(r, c)
        if len(adj) == 1:
            iid = next(iter(adj))
            if len(self.island_cells[iid - 1]) < self.targets[iid - 1]:
                out.append(("I", iid))

        if len(out) == 2:
            iid = out[1][1]
            remain = self.targets[iid - 1] - len(self.island_cells[iid - 1])
            if remain == 1:
                out = [("I", iid), ("B", 0)]
        return out

    def _pick_cell(self):
        best = None
        best_key = None
        fallback = None
        for r, c in self.cells:
            if self.state[r][c] != -1:
                continue
            if fallback is None:
                fallback = (r, c)
            vals = self._candidate_values(r, c)
            if not vals:
                continue
            adj = self._adjacent_islands(r, c)
            key = (len(adj) == 0, len(vals), -len(adj), r, c)
            if best_key is None or key < best_key:
                best_key = key
                best = (r, c)
        return best if best is not None else fallback

    def _value_order(self, r: int, c: int) -> List[Tuple[str, int]]:
        vals = self._candidate_values(r, c)
        if len(vals) != 2:
            return vals

        if vals[0][0] == "B":
            iid = vals[1][1]
            remain = self.targets[iid - 1] - len(self.island_cells[iid - 1])
            if remain <= 2:
                return [vals[1], vals[0]]
        return vals

    def _search(self):
        key = self._state_key()
        if key in self._dead:
            return None

        ok = self._propagate()
        if not ok:
            self._dead.add(key)
            return None
        if self._final_ok():
            return [row[:] for row in self.state]

        pos = self._pick_cell()
        if pos is None:
            self._dead.add(self._state_key())
            return None
        r, c = pos

        vals = self._value_order(r, c)
        if not vals:
            self._dead.add(self._state_key())
            return None

        fail = ""
        for kind, v in vals:
            snap = self._snapshot()
            ok_set = self._set_black(r, c) if kind == "B" else self._set_island(r, c, v)
            if ok_set:
                ans = self._search()
                if ans is not None:
                    return ans
            fail = self._last_fail or "branch failed"
            self._restore(snap)

        self._last_fail = f"all branches failed at ({r},{c})"
        self._dead.add(self._state_key())
        return None


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict) and "original_data" in obs and isinstance(obs["original_data"], dict):
        obs = obs["original_data"]
    if isinstance(obs, dict) and "data" in obs:
        obs = obs["data"]

    if not (isinstance(obs, list) and obs and isinstance(obs[0], list)):
        raise ValueError("nurikabe observation must be 2D grid")

    n = len(obs)
    out = []
    for r in range(n):
        if len(obs[r]) != n:
            raise ValueError("nurikabe grid must be square")
        out.append([None if v is None else int(v) for v in obs[r]])
    return out


def solve(observation, verbose: bool = False, max_logs: int = 10000, log_level: str = "brief"):
    if log_level not in {"brief", "full"}:
        raise ValueError("log_level must be 'brief' or 'full'")

    number_grid = _normalize_observation(observation)
    solver = _NurikabeSolver(number_grid)
    ans = solver._search()
    if ans is None:
        return "No Solution"

    out = [["B" if ans[r][c] == 0 else None for c in range(solver.n)] for r in range(solver.n)]
    return out
