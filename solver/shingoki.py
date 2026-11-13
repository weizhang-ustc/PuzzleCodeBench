from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set, Tuple

Pos = Tuple[int, int]
Edge = Tuple[Pos, Pos]

DIRS = ("U", "R", "D", "L")
DRDC = {"U": (-1, 0), "R": (0, 1), "D": (1, 0), "L": (0, -1)}
OPP = {"U": "D", "D": "U", "L": "R", "R": "L"}


class _ShingokiSolver:
    def __init__(self, clue_grid: Sequence[Sequence[Optional[str]]]):
        self.grid = [list(row) for row in clue_grid]
        self.n = len(self.grid)
        self._last_fail = ""

        if self.n == 0 or any(len(row) != self.n for row in self.grid):
            raise ValueError("shingoki grid must be non-empty square")

        self.edges: List[Edge] = []
        self.edge_id: Dict[Tuple[Pos, Pos], int] = {}
        self.vertex_edges: Dict[Pos, Dict[str, Optional[int]]] = {}
        self.edge_state: List[int] = []

        self.clues: Dict[Pos, Tuple[str, int]] = {}
        self.clue_domains: Dict[Pos, Set[str]] = {}
        self._dead_cache: Set[Tuple] = set()
        self._cut_edges: List[List[int]] = []

        self._build_graph()
        self._init_cut_edges()
        self._init_clues()

    def _in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.n and 0 <= c < self.n

    def _neighbor(self, pos: Pos, d: str) -> Optional[Pos]:
        r, c = pos
        dr, dc = DRDC[d]
        nr, nc = r + dr, c + dc
        if not self._in_bounds(nr, nc):
            return None
        return (nr, nc)

    def _build_graph(self):
        for r in range(self.n):
            for c in range(self.n):
                self.vertex_edges[(r, c)] = {d: None for d in DIRS}

        def add_edge(a: Pos, b: Pos):
            key = (a, b) if a < b else (b, a)
            if key in self.edge_id:
                return self.edge_id[key]
            eid = len(self.edges)
            self.edges.append(key)
            self.edge_id[key] = eid
            self.edge_state.append(-1)
            return eid

        for r in range(self.n):
            for c in range(self.n):
                a = (r, c)
                if c + 1 < self.n:
                    b = (r, c + 1)
                    eid = add_edge(a, b)
                    self.vertex_edges[a]["R"] = eid
                    self.vertex_edges[b]["L"] = eid
                if r + 1 < self.n:
                    b = (r + 1, c)
                    eid = add_edge(a, b)
                    self.vertex_edges[a]["D"] = eid
                    self.vertex_edges[b]["U"] = eid

    def _init_cut_edges(self):
        cuts: List[List[int]] = []
        for c in range(self.n - 1):
            eids = []
            for r in range(self.n):
                eid = self.vertex_edges[(r, c)]["R"]
                if eid is not None:
                    eids.append(eid)
            cuts.append(eids)
        for r in range(self.n - 1):
            eids = []
            for c in range(self.n):
                eid = self.vertex_edges[(r, c)]["D"]
                if eid is not None:
                    eids.append(eid)
            cuts.append(eids)
        self._cut_edges = cuts

    def _apply_cut_parity_rules(self) -> bool:
        for eids in self._cut_edges:
            on = 0
            unk = []
            for eid in eids:
                st = self.edge_state[eid]
                if st == 1:
                    on += 1
                elif st == -1:
                    unk.append(eid)
            if not unk:
                if on % 2 == 1:
                    self._last_fail = "cut parity violated"
                    return False
                continue
            if len(unk) == 1:
                force = on % 2
                if not self._set_edge(unk[0], force):
                    return False
        return True

    def _parse_clue(self, token) -> Optional[Tuple[str, int]]:
        if token is None or not isinstance(token, str):
            return None
        s = token.strip().upper()
        if len(s) < 2 or s[0] not in {"W", "B"}:
            return None
        try:
            k = int(s[1:])
        except ValueError:
            return None
        return s[0], k

    def _init_clues(self):
        for r in range(self.n):
            for c in range(self.n):
                clue = self._parse_clue(self.grid[r][c])
                if clue is not None:
                    self.clues[(r, c)] = clue
        for pos, (t, _) in self.clues.items():
            if t == "W":
                self.clue_domains[pos] = {"H", "V"}
            else:
                self.clue_domains[pos] = {"UR", "UL", "DR", "DL"}

    def _snapshot(self):
        return (self.edge_state[:], {p: set(d) for p, d in self.clue_domains.items()}, self._last_fail)

    def _restore(self, snap):
        self.edge_state, self.clue_domains, self._last_fail = snap

    def _edge_dirs(self, pos: Pos) -> Dict[str, int]:
        ret = {}
        for d, eid in self.vertex_edges[pos].items():
            if eid is not None:
                ret[d] = self.edge_state[eid]
        return ret

    def _state_key(self) -> Tuple:
        dom_sig = tuple(sorted((p, tuple(sorted(v))) for p, v in self.clue_domains.items()))
        return (tuple(self.edge_state), dom_sig)

    def _set_edge(self, eid: int, val: int) -> bool:
        cur = self.edge_state[eid]
        if cur == val:
            return True
        if cur != -1 and cur != val:
            self._last_fail = f"edge {self.edges[eid]} conflict {cur} vs {val}"
            return False
        self.edge_state[eid] = val
        return True

    def _vertex_degree_rule(self, pos: Pos, force_deg2: bool) -> bool:
        dirs = self._edge_dirs(pos)
        on = [d for d, st in dirs.items() if st == 1]
        unk = [d for d, st in dirs.items() if st == -1]

        if len(on) > 2:
            self._last_fail = f"vertex {pos} has degree >2"
            return False

        if force_deg2:
            if len(on) + len(unk) < 2:
                self._last_fail = f"clue {pos} cannot reach degree 2"
                return False
            if len(on) == 2:
                for d in unk:
                    eid = self.vertex_edges[pos][d]
                    if not self._set_edge(eid, 0):
                        return False
            elif len(on) + len(unk) == 2:
                for d in unk:
                    eid = self.vertex_edges[pos][d]
                    if not self._set_edge(eid, 1):
                        return False
            return True

        if len(on) == 2:
            for d in unk:
                eid = self.vertex_edges[pos][d]
                if not self._set_edge(eid, 0):
                    return False
        if len(on) == 1 and len(unk) == 0:
            self._last_fail = f"vertex {pos} stuck degree 1"
            return False
        if len(on) == 1 and len(unk) == 1:
            eid = self.vertex_edges[pos][unk[0]]
            if not self._set_edge(eid, 1):
                return False
        if len(on) == 0 and len(unk) == 1:
            eid = self.vertex_edges[pos][unk[0]]
            if not self._set_edge(eid, 0):
                return False
        return True

    def _orientation_edges(self, pos: Pos, ori: str) -> Tuple[Set[int], Set[int], Tuple[str, str]]:
        req_on: Set[int] = set()
        req_off: Set[int] = set()
        if ori == "H":
            on_dirs = {"L", "R"}
            dirs_for_len = ("L", "R")
        elif ori == "V":
            on_dirs = {"U", "D"}
            dirs_for_len = ("U", "D")
        else:
            on_dirs = set(ori)
            dirs_for_len = (ori[0], ori[1])
        for d in DIRS:
            eid = self.vertex_edges[pos][d]
            if eid is None:
                continue
            if d in on_dirs:
                req_on.add(eid)
            else:
                req_off.add(eid)
        return req_on, req_off, dirs_for_len

    def _run_length_options(self, start: Pos, d: str) -> Set[int]:
        nb = self._neighbor(start, d)
        if nb is None:
            return set()
        first_eid = self.vertex_edges[start][d]
        if first_eid is None or self.edge_state[first_eid] == 0:
            return set()

        options: Set[int] = set()
        cur = nb
        length = 1
        travel = d
        for _ in range(self.n + 1):
            inc = OPP[travel]
            out = travel
            out_eid = self.vertex_edges[cur][out]
            perp_dirs = [x for x in DIRS if x not in (inc, out)]
            perp_eids = [self.vertex_edges[cur][x] for x in perp_dirs if self.vertex_edges[cur][x] is not None]

            turn_possible = any(self.edge_state[e] != 0 for e in perp_eids) and not (
                out_eid is not None and self.edge_state[out_eid] == 1
            )
            if turn_possible:
                options.add(length)

            continue_possible = (
                out_eid is not None
                and self.edge_state[out_eid] != 0
                and all(self.edge_state[e] != 1 for e in perp_eids)
            )
            if not continue_possible:
                break

            nxt = self._neighbor(cur, out)
            if nxt is None:
                break
            cur = nxt
            length += 1
        return options

    def _ray_edge(self, start: Pos, d: str, step: int) -> Optional[int]:
        cur = start
        for _ in range(step - 1):
            nxt = self._neighbor(cur, d)
            if nxt is None:
                return None
            cur = nxt
        return self.vertex_edges[cur][d]

    def _endpoint_after(self, start: Pos, d: str, length: int) -> Optional[Pos]:
        cur = start
        for _ in range(length):
            cur = self._neighbor(cur, d)
            if cur is None:
                return None
        return cur

    def _feasible_plans(self, pos: Pos, ori: str, k: int, dir_opts: Optional[Dict[str, Set[int]]] = None):
        req_on, req_off, dirs_for_len = self._orientation_edges(pos, ori)
        for eid in req_on:
            if self.edge_state[eid] == 0:
                return []
        for eid in req_off:
            if self.edge_state[eid] == 1:
                return []

        d1, d2 = dirs_for_len
        if dir_opts is None:
            opts1 = self._run_length_options(pos, d1)
            opts2 = self._run_length_options(pos, d2)
        else:
            opts1 = dir_opts[d1]
            opts2 = dir_opts[d2]
        plans = []
        for l1 in opts1:
            l2 = k - l1
            if l2 in opts2:
                plans.append((l1, l2))
        return plans

    def _propagate_clues(self) -> bool:
        for pos, (ctype, k) in self.clues.items():
            dom = self.clue_domains[pos]
            dir_opts = {d: self._run_length_options(pos, d) for d in DIRS}
            ori_to_plans = {ori: self._feasible_plans(pos, ori, k, dir_opts) for ori in dom}
            feasible = {ori for ori, plans in ori_to_plans.items() if plans}
            if not feasible:
                self._last_fail = f"clue {ctype}{k} at {pos} has no feasible orientation"
                return False
            if feasible != dom:
                self.clue_domains[pos] = feasible

            all_on = None
            all_off = None
            for ori in self.clue_domains[pos]:
                req_on, req_off, _ = self._orientation_edges(pos, ori)
                all_on = req_on if all_on is None else (all_on & req_on)
                all_off = req_off if all_off is None else (all_off & req_off)
            all_on = all_on or set()
            all_off = all_off or set()

            clue_plan_on = None
            clue_plan_off = None
            for ori in self.clue_domains[pos]:
                _, _, (d1, d2) = self._orientation_edges(pos, ori)
                plan_reqs = []
                for l1, l2 in ori_to_plans[ori]:
                    req_on_plan = set()
                    req_off_plan = set()
                    for step in range(1, l1 + 1):
                        eid = self._ray_edge(pos, d1, step)
                        if eid is None:
                            req_on_plan = set()
                            break
                        req_on_plan.add(eid)
                    for step in range(1, l2 + 1):
                        eid = self._ray_edge(pos, d2, step)
                        if eid is None:
                            req_on_plan = set()
                            break
                        req_on_plan.add(eid)
                    end1 = self._endpoint_after(pos, d1, l1)
                    end2 = self._endpoint_after(pos, d2, l2)
                    if end1 is not None:
                        eout1 = self.vertex_edges[end1][d1]
                        if eout1 is not None:
                            req_off_plan.add(eout1)
                    if end2 is not None:
                        eout2 = self.vertex_edges[end2][d2]
                        if eout2 is not None:
                            req_off_plan.add(eout2)
                    plan_reqs.append((req_on_plan, req_off_plan))
                if not plan_reqs:
                    continue
                ori_on = set.intersection(*(x[0] for x in plan_reqs))
                ori_off = set.intersection(*(x[1] for x in plan_reqs))
                clue_plan_on = ori_on if clue_plan_on is None else (clue_plan_on & ori_on)
                clue_plan_off = ori_off if clue_plan_off is None else (clue_plan_off & ori_off)

            if clue_plan_on:
                all_on |= clue_plan_on
            if clue_plan_off:
                all_off |= clue_plan_off

            for eid in all_on:
                if not self._set_edge(eid, 1):
                    return False
            for eid in all_off:
                if not self._set_edge(eid, 0):
                    return False
        return True

    def _clues_potentially_connected(self) -> bool:
        if not self.clues:
            return True
        clue_set = set(self.clues.keys())
        start = next(iter(clue_set))
        stack = [start]
        seen = {start}
        while stack:
            cur = stack.pop()
            for eid in self.vertex_edges[cur].values():
                if eid is None or self.edge_state[eid] == 0:
                    continue
                a, b = self.edges[eid]
                nxt = b if a == cur else a
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        if not clue_set.issubset(seen):
            self._last_fail = "clues disconnected in possibility graph"
            return False
        return True

    def _has_forbidden_subloop(self) -> bool:
        adj: Dict[Pos, List[Pos]] = {}
        for eid, st in enumerate(self.edge_state):
            if st != 1:
                continue
            a, b = self.edges[eid]
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        if not adj:
            return False

        seen: Set[Pos] = set()
        clue_set = set(self.clues.keys())
        total_used_vertices = set(adj.keys())

        for start in list(adj.keys()):
            if start in seen:
                continue
            stack = [start]
            comp = {start}
            seen.add(start)
            while stack:
                cur = stack.pop()
                for nxt in adj[cur]:
                    if nxt not in seen:
                        seen.add(nxt)
                        comp.add(nxt)
                        stack.append(nxt)
            closed_cycle = all(len(adj[v]) == 2 for v in comp)
            if not closed_cycle:
                continue
            if not clue_set.issubset(comp):
                return True
            if comp != total_used_vertices:
                return True
        return False

    def _probe_orientation_literal(self, pos: Pos, ori: str) -> bool:
        snap = self._snapshot()
        try:
            if not self._set_orientation(pos, ori):
                return False
            return self._propagate(enable_probing=False)
        finally:
            self._restore(snap)

    def _probe_edge_literal(self, eid: int, val: int) -> bool:
        snap = self._snapshot()
        try:
            if not self._set_edge(eid, val):
                return False
            return self._propagate(enable_probing=False)
        finally:
            self._restore(snap)

    def _probe_failed_literals(self) -> Tuple[bool, bool]:
        changed = False

        unresolved = [pos for pos, dom in self.clue_domains.items() if len(dom) > 1]
        unresolved.sort(key=lambda pos: (len(self.clue_domains[pos]), -self.clues[pos][1], pos))
        clue_probe_limit = 5 if self.n >= 20 else 8
        for pos in unresolved[:clue_probe_limit]:
            dom = sorted(self.clue_domains[pos])
            feasible = [ori for ori in dom if self._probe_orientation_literal(pos, ori)]
            if not feasible:
                ctype, k = self.clues[pos]
                self._last_fail = f"failed-literal: clue {ctype}{k} at {pos} has no feasible orientation"
                return False, changed
            if len(feasible) == 1 and len(dom) > 1:
                if not self._set_orientation(pos, feasible[0]):
                    return False, changed
                changed = True

        edge_probe_limit = 5 if self.n >= 20 else 8
        for eid in self._rank_branch_edges()[:edge_probe_limit]:
            can_on = self._probe_edge_literal(eid, 1)
            can_off = self._probe_edge_literal(eid, 0)
            if not can_on and not can_off:
                self._last_fail = f"failed-literal: edge {self.edges[eid]} both states fail"
                return False, changed
            if can_on ^ can_off:
                if not self._set_edge(eid, 1 if can_on else 0):
                    return False, changed
                changed = True

        return True, changed

    def _propagate(self, enable_probing: bool = True):
        while True:
            changed_before = tuple(self.edge_state), tuple((p, tuple(sorted(v))) for p, v in sorted(self.clue_domains.items()))

            for r in range(self.n):
                for c in range(self.n):
                    pos = (r, c)
                    if not self._vertex_degree_rule(pos, pos in self.clues):
                        return False

            if not self._propagate_clues():
                return False

            if not self._clues_potentially_connected():
                return False

            if self._has_forbidden_subloop():
                self._last_fail = "forbidden closed subloop"
                return False

            if not self._apply_cut_parity_rules():
                return False

            changed_after = tuple(self.edge_state), tuple((p, tuple(sorted(v))) for p, v in sorted(self.clue_domains.items()))
            if changed_after != changed_before:
                continue

            if enable_probing:
                ok_probe, changed = self._probe_failed_literals()
                if not ok_probe:
                    return False
                if changed:
                    continue

            break
        return True

    def _final_valid(self) -> bool:
        for r in range(self.n):
            for c in range(self.n):
                pos = (r, c)
                deg = 0
                for eid in self.vertex_edges[pos].values():
                    if eid is not None and self.edge_state[eid] == 1:
                        deg += 1
                if pos in self.clues:
                    if deg != 2:
                        self._last_fail = f"clue {pos} degree != 2"
                        return False
                else:
                    if deg not in (0, 2):
                        self._last_fail = f"vertex {pos} invalid degree {deg}"
                        return False

        for pos, (ctype, k) in self.clues.items():
            ok = False
            for ori in self.clue_domains[pos]:
                req_on, req_off, dirs_for_len = self._orientation_edges(pos, ori)
                if not (all(self.edge_state[e] == 1 for e in req_on) and all(self.edge_state[e] == 0 for e in req_off)):
                    continue
                opts1 = self._run_length_options(pos, dirs_for_len[0])
                opts2 = self._run_length_options(pos, dirs_for_len[1])
                if any((k - a) in opts2 for a in opts1):
                    ok = True
                    break
            if not ok:
                self._last_fail = f"clue {ctype}{k} at {pos} fails length rule"
                return False

        used = [eid for eid, st in enumerate(self.edge_state) if st == 1]
        if not used:
            self._last_fail = "no loop edges"
            return False
        adj: Dict[Pos, List[Pos]] = {}
        for eid in used:
            a, b = self.edges[eid]
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        for v, nb in adj.items():
            if len(nb) != 2:
                self._last_fail = f"used vertex {v} degree !=2 in final"
                return False
        st = next(iter(adj))
        stack = [st]
        seen = {st}
        while stack:
            cur = stack.pop()
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        if len(seen) != len(adj):
            self._last_fail = "multiple loops/components"
            return False
        return True

    def _build_path(self) -> Optional[List[Pos]]:
        if not self._final_valid():
            return None
        adj: Dict[Pos, List[Pos]] = {}
        for eid, st in enumerate(self.edge_state):
            if st != 1:
                continue
            a, b = self.edges[eid]
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        start = min(adj.keys())
        path = [start]
        prev = None
        cur = start
        while True:
            nbs = adj[cur]
            nxt = nbs[0] if nbs[0] != prev else nbs[1]
            path.append(nxt)
            if nxt == start:
                break
            prev, cur = cur, nxt
            if len(path) > len(adj) + 2:
                return None
        return path

    def _rank_branch_edges(self) -> List[int]:
        ranked = []
        clue_vertices = set(self.clues.keys())
        for eid, st in enumerate(self.edge_state):
            if st != -1:
                continue
            a, b = self.edges[eid]
            w = 0
            if a in clue_vertices:
                w += 5
            if b in clue_vertices:
                w += 5
            for v in (a, b):
                dirs = self._edge_dirs(v)
                on = sum(1 for x in dirs.values() if x == 1)
                unk = sum(1 for x in dirs.values() if x == -1)
                w += (4 - unk) + on
            ranked.append(((-w, eid), eid))
        ranked.sort(key=lambda x: x[0])
        return [eid for _, eid in ranked]

    def _choose_branch_edge(self, depth: int = 0) -> Optional[int]:
        ranked = self._rank_branch_edges()
        if not ranked:
            return None
        if self.n < 20 or depth > 4:
            return ranked[0]

        best = ranked[0]
        best_key = (-1, 10**9)
        for eid in ranked[:10]:
            fail_count = 0
            for v in (1, 0):
                snap = self._snapshot()
                ok_set = self._set_edge(eid, v)
                ok_prop = False
                if ok_set:
                    ok_prop = self._propagate(enable_probing=False)
                self._restore(snap)
                if not (ok_set and ok_prop):
                    fail_count += 1
            key = (fail_count, -eid)
            if key > best_key:
                best_key = key
                best = eid
            if fail_count == 2:
                return eid
        return best

    def _choose_branch_clue(self) -> Optional[Pos]:
        unresolved = [pos for pos, dom in self.clue_domains.items() if len(dom) > 1]
        if not unresolved:
            return None

        if len(unresolved) <= 10:
            best = None
            best_key = None
            for pos in unresolved:
                _, k = self.clues[pos]
                dom = self.clue_domains[pos]
                dir_opts = {d: self._run_length_options(pos, d) for d in DIRS}
                plan_count = 0
                for ori in dom:
                    plan_count += len(self._feasible_plans(pos, ori, k, dir_opts))
                impact = 0
                near = {pos}
                for d in DIRS:
                    nb = self._neighbor(pos, d)
                    if nb is not None:
                        near.add(nb)
                for v in near:
                    for eid in self.vertex_edges[v].values():
                        if eid is not None and self.edge_state[eid] == -1:
                            impact += 1
                key = (plan_count, len(dom), -impact, -k, pos[0], pos[1])
                if best_key is None or key < best_key:
                    best_key = key
                    best = pos
            return best

        best = None
        best_key = None
        for pos in unresolved:
            _, k = self.clues[pos]
            impact = 0
            near = {pos}
            for d in DIRS:
                nb = self._neighbor(pos, d)
                if nb is not None:
                    near.add(nb)
            for v in near:
                for eid in self.vertex_edges[v].values():
                    if eid is not None and self.edge_state[eid] == -1:
                        impact += 1
            key = (len(self.clue_domains[pos]), -impact, -k, pos[0], pos[1])
            if best_key is None or key < best_key:
                best_key = key
                best = pos
        return best

    def _set_orientation(self, pos: Pos, ori: str) -> bool:
        req_on, req_off, _ = self._orientation_edges(pos, ori)
        for eid in req_on:
            if not self._set_edge(eid, 1):
                return False
        for eid in req_off:
            if not self._set_edge(eid, 0):
                return False
        self.clue_domains[pos] = {ori}
        return True

    def _search_one(self, depth: int, depth_limit: Optional[int]):
        if depth_limit is None:
            sk = self._state_key()
            if sk in self._dead_cache:
                return None

        if not self._propagate():
            return None

        if depth_limit is None:
            sk = self._state_key()
            if sk in self._dead_cache:
                return None

        if all(st != -1 for st in self.edge_state):
            path = self._build_path()
            if path is not None:
                return path
            if depth_limit is None:
                self._dead_cache.add(sk)
            return None

        if depth_limit is not None and depth >= depth_limit:
            self._last_fail = "depth cap reached"
            return None

        cpos = self._choose_branch_clue()
        if cpos is not None:
            _, k = self.clues[cpos]
            dir_opts = {d: self._run_length_options(cpos, d) for d in DIRS}
            dom = sorted(
                self.clue_domains[cpos],
                key=lambda ori: (
                    len(self._feasible_plans(cpos, ori, k, dir_opts)),
                    -sum(
                        1
                        for e in (self._orientation_edges(cpos, ori)[0] | self._orientation_edges(cpos, ori)[1])
                        if self.edge_state[e] == -1
                    ),
                    ori,
                ),
            )
            for ori in dom:
                snap = self._snapshot()
                if self._set_orientation(cpos, ori):
                    ans = self._search_one(depth + 1, depth_limit)
                    if ans is not None:
                        return ans
                self._restore(snap)
            if depth_limit is None:
                self._dead_cache.add(self._state_key())
            return None

        eid = self._choose_branch_edge(depth)
        if eid is None:
            return None
        for v in (1, 0):
            snap = self._snapshot()
            if self._set_edge(eid, v):
                ans = self._search_one(depth + 1, depth_limit)
                if ans is not None:
                    return ans
            self._restore(snap)
        if depth_limit is None:
            self._dead_cache.add(self._state_key())
        return None

    def solve_staged(self):
        if not self._propagate():
            return None
        if all(st != -1 for st in self.edge_state):
            path = self._build_path()
            if path is not None:
                return path

        if self.n <= 12:
            for cap in (2, 4, 6, 8):
                snap = self._snapshot()
                ans = self._search_one(0, cap)
                if ans is not None:
                    return ans
                self._restore(snap)
        return self._search_one(0, None)


def _normalize_observation(observation):
    data = observation
    if isinstance(data, dict):
        data = data.get("data", data)
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError("observation must be a non-empty 2D list")
    n = len(data)
    if any(len(row) != n for row in data):
        raise ValueError("shingoki grid must be square")
    return [row[:] for row in data]


def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 14000,
    log_level: str = "brief",
):
    if log_level not in {"brief", "full"}:
        raise ValueError("log_level must be 'brief' or 'full'")
    grid = _normalize_observation(observation)
    solver = _ShingokiSolver(grid)
    answer = solver.solve_staged()
    if answer is None:
        return "No Solution"
    return [tuple(p) for p in answer]
