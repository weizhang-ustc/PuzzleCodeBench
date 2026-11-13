from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set, Tuple

Pos = Tuple[int, int]


class _NorinoriSolver:
    DIR4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

    def __init__(self, region_grid: List[List[int]]):
        self.n = len(region_grid)
        self.m = len(region_grid[0])
        self.region = [[int(region_grid[r][c]) for c in range(self.m)] for r in range(self.n)]
        self._last_fail = ""
        self._dead = set()

        self.cells: List[Pos] = [(r, c) for r in range(self.n) for c in range(self.m)]
        self.cell_id: Dict[Pos, int] = {p: i for i, p in enumerate(self.cells)}

        self.region_cells: Dict[int, List[int]] = defaultdict(list)
        for i, (r, c) in enumerate(self.cells):
            self.region_cells[self.region[r][c]].append(i)
        self.region_ids = sorted(self.region_cells.keys())
        self.target_dominoes = len(self.region_ids)

        self.cell_adj: List[Set[int]] = [set() for _ in self.cells]
        for i, (r, c) in enumerate(self.cells):
            for dr, dc in self.DIR4:
                rr, cc = r + dr, c + dc
                if 0 <= rr < self.n and 0 <= cc < self.m:
                    self.cell_adj[i].add(self.cell_id[(rr, cc)])

        self.edges: List[Tuple[int, int]] = []
        self.incident: List[List[int]] = [[] for _ in self.cells]
        seen = set()
        for i in range(len(self.cells)):
            for j in self.cell_adj[i]:
                a, b = (i, j) if i < j else (j, i)
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                eid = len(self.edges)
                self.edges.append((a, b))
                self.incident[a].append(eid)
                self.incident[b].append(eid)

        self.conflict: List[Set[int]] = [set() for _ in self.edges]
        e_count = len(self.edges)
        for e in range(e_count):
            a, b = self.edges[e]
            for f in range(e + 1, e_count):
                c, d = self.edges[f]
                if len({a, b, c, d}) < 4:
                    self.conflict[e].add(f)
                    self.conflict[f].add(e)
                    continue
                bad = False
                for x in (a, b):
                    if c in self.cell_adj[x] or d in self.cell_adj[x]:
                        bad = True
                        break
                if bad:
                    self.conflict[e].add(f)
                    self.conflict[f].add(e)

        self.estate: List[int] = [-1] * len(self.edges)

    def _snapshot(self):
        return self.estate[:], self._last_fail

    def _restore(self, snap):
        self.estate, self._last_fail = snap

    def _state_key(self):
        return tuple(self.estate)

    def _set_edge(self, eid: int, val: int) -> bool:
        cur = self.estate[eid]
        if cur == val:
            return True
        if cur != -1:
            self._last_fail = f"edge conflict {eid}"
            return False
        self.estate[eid] = val
        return True

    def _set_cell_white(self, cid: int) -> bool:
        for eid in self.incident[cid]:
            if self.estate[eid] == -1:
                if not self._set_edge(eid, 0):
                    return False
        return True

    def _cell_deg(self, cid: int) -> Tuple[int, List[int]]:
        s = 0
        u = []
        for eid in self.incident[cid]:
            st = self.estate[eid]
            if st == 1:
                s += 1
            elif st == -1:
                u.append(eid)
        return s, u

    def _region_bounds(self, rid: int):
        lower = 0
        undecidable = []
        for cid in self.region_cells[rid]:
            s, u = self._cell_deg(cid)
            if s > 0:
                lower += 1
            elif len(u) > 0:
                undecidable.append(cid)
        upper = lower + len(undecidable)
        return lower, upper, undecidable

    def _propagate_conflicts(self) -> bool:
        changed = False
        for eid, st in enumerate(self.estate):
            if st != 1:
                continue
            for fid in self.conflict[eid]:
                fst = self.estate[fid]
                if fst == 1:
                    self._last_fail = f"conflicting selected edges {eid} and {fid}"
                    return False
                if fst == -1:
                    if not self._set_edge(fid, 0):
                        return False
                    changed = True
        return changed

    def _propagate_degree(self) -> bool:
        changed = False
        for cid in range(len(self.cells)):
            s, u = self._cell_deg(cid)
            if s > 1:
                self._last_fail = f"cell {self.cells[cid]} has degree>1"
                return False
            if s == 1:
                for eid in u:
                    if not self._set_edge(eid, 0):
                        return False
                    changed = True
        return changed

    def _propagate_regions(self) -> bool:
        changed = False
        for rid in self.region_ids:
            lower, upper, undecidable = self._region_bounds(rid)
            if lower > 2 or upper < 2:
                self._last_fail = f"region {rid} impossible (lower={lower}, upper={upper})"
                return False

            if lower == 2:
                for cid in self.region_cells[rid]:
                    s, u = self._cell_deg(cid)
                    if s == 0 and len(u) > 0:
                        if not self._set_cell_white(cid):
                            return False
                        changed = True

            if upper == 2:
                for cid in undecidable:
                    s, u = self._cell_deg(cid)
                    if s == 0:
                        if len(u) == 0:
                            self._last_fail = f"region {rid} needs {self.cells[cid]} shaded but no edge"
                            return False
                        if len(u) == 1:
                            if not self._set_edge(u[0], 1):
                                return False
                            changed = True

        return changed

    def _propagate_global_count(self) -> bool:
        changed = False
        sel = sum(1 for st in self.estate if st == 1)
        undec = [i for i, st in enumerate(self.estate) if st == -1]
        if sel > self.target_dominoes or sel + len(undec) < self.target_dominoes:
            self._last_fail = "global domino count impossible"
            return False

        if sel == self.target_dominoes:
            for eid in undec:
                if not self._set_edge(eid, 0):
                    return False
                changed = True
        elif sel + len(undec) == self.target_dominoes:
            for eid in undec:
                if not self._set_edge(eid, 1):
                    return False
                changed = True

        return changed

    def _propagate(self):
        self._last_fail = ""
        while True:
            changed = False
            for fn in (
                self._propagate_conflicts,
                self._propagate_degree,
                self._propagate_regions,
                self._propagate_global_count,
            ):
                res = fn()
                if res is False and self._last_fail:
                    return False
                changed = changed or bool(res)
            if not changed:
                break
        return True

    def _final_ok(self) -> bool:
        if any(st == -1 for st in self.estate):
            return False

        deg = [0] * len(self.cells)
        for eid, st in enumerate(self.estate):
            if st != 1:
                continue
            for fid in self.conflict[eid]:
                if self.estate[fid] == 1:
                    return False
            a, b = self.edges[eid]
            deg[a] += 1
            deg[b] += 1
            if deg[a] > 1 or deg[b] > 1:
                return False

        for rid in self.region_ids:
            shaded = sum(1 for cid in self.region_cells[rid] if deg[cid] == 1)
            if shaded != 2:
                return False

        return sum(1 for st in self.estate if st == 1) == self.target_dominoes

    def _pick_branch(self):
        best_rid = None
        best_key = None
        best_info = None
        for rid in self.region_ids:
            lower, upper, cand = self._region_bounds(rid)
            if lower >= 2:
                continue
            need = 2 - lower
            if need <= 0:
                continue
            key = (len(cand), need, rid)
            if best_key is None or key < best_key:
                best_key = key
                best_rid = rid
                best_info = (lower, cand)

        if best_rid is not None and best_info is not None:
            lower, cand = best_info
            if cand:
                cid = min(cand, key=lambda x: len(self._cell_deg(x)[1]))
                _, u = self._cell_deg(cid)
                actions = []

                if lower + (len(cand) - 1) >= 2:
                    actions.append(("W", cid, -1))

                for eid in u:
                    actions.append(("E", cid, eid))

                return actions

        best_e = None
        best_e_key = None
        for eid, st in enumerate(self.estate):
            if st != -1:
                continue
            a, b = self.edges[eid]
            _, ua = self._cell_deg(a)
            _, ub = self._cell_deg(b)
            key = (len(ua) + len(ub), eid)
            if best_e_key is None or key < best_e_key:
                best_e_key = key
                best_e = eid
        if best_e is None:
            return []
        return [("E", -1, best_e), ("X", -1, best_e)]

    def _order_actions(self, actions):
        scored = []
        for kind, cid, eid in actions:
            snap = self._snapshot()
            ok = True
            if kind == "W":
                ok = self._set_cell_white(cid)
            elif kind == "E":
                ok = self._set_edge(eid, 1)
            else:
                ok = self._set_edge(eid, 0)

            if ok:
                ok = self._propagate()
            remain = sum(1 for st in self.estate if st == -1) if ok else 10**9
            self._restore(snap)
            if ok:
                scored.append((remain, (kind, cid, eid)))
        scored.sort()
        return [act for _, act in scored]

    def _search(self):
        key = self._state_key()
        if key in self._dead:
            return None

        ok = self._propagate()
        if not ok:
            self._dead.add(key)
            return None
        if self._final_ok():
            return self.estate[:]

        actions = self._pick_branch()
        if not actions:
            self._dead.add(self._state_key())
            return None

        ordered = self._order_actions(actions)
        if not ordered:
            self._dead.add(self._state_key())
            return None

        fail = ""
        for kind, cid, eid in ordered:
            snap = self._snapshot()
            ok_set = True
            if kind == "W":
                ok_set = self._set_cell_white(cid)
            elif kind == "E":
                ok_set = self._set_edge(eid, 1)
            else:
                ok_set = self._set_edge(eid, 0)

            if ok_set:
                ans = self._search()
                if ans is not None:
                    return ans

            fail = self._last_fail or "branch failed"
            self._restore(snap)

        self._last_fail = "all actions failed"
        self._dead.add(self._state_key())
        return None


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict):
        if "data" in obs and isinstance(obs["data"], list):
            obs = obs["data"]
        elif "original_data" in obs and isinstance(obs["original_data"], dict) and "data" in obs["original_data"]:
            obs = obs["original_data"]["data"]

    if not (isinstance(obs, list) and obs and isinstance(obs[0], list)):
        raise ValueError("norinori observation must be 2D region grid")

    n = len(obs)
    m = len(obs[0])
    out = []
    for r in range(n):
        if len(obs[r]) != m:
            raise ValueError("norinori region grid must be rectangular")
        out.append([int(x) for x in obs[r]])
    return out


def solve(observation, verbose: bool = False, max_logs: int = 10000, log_level: str = "brief"):
    region_grid = _normalize_observation(observation)
    solver = _NorinoriSolver(region_grid)
    estate = solver._search()
    if estate is None:
        return "No Solution"

    deg = [0] * len(solver.cells)
    for eid, st in enumerate(estate):
        if st == 1:
            a, b = solver.edges[eid]
            deg[a] += 1
            deg[b] += 1

    out = [[None for _ in range(solver.m)] for _ in range(solver.n)]
    for cid, d in enumerate(deg):
        if d == 1:
            r, c = solver.cells[cid]
            out[r][c] = "S"

    return out
