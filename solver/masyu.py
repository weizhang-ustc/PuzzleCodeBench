from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set, Tuple

Pos = Tuple[int, int]
Edge = Tuple[Pos, Pos]

DIRS = ("U", "R", "D", "L")
DRDC = {"U": (-1, 0), "R": (0, 1), "D": (1, 0), "L": (0, -1)}
OPP = {"U": "D", "D": "U", "L": "R", "R": "L"}


class _MasyuSolver:
    def __init__(
        self,
        clue_grid: Sequence[Sequence[Optional[str]]],
    ):
        self.grid = [list(row) for row in clue_grid]
        self.n = len(self.grid)
        self._last_fail = ""

        if self.n == 0 or any(len(row) != self.n for row in self.grid):
            raise ValueError("masyu grid must be a non-empty square")

        self.edges: List[Edge] = []
        self.edge_id: Dict[Tuple[Pos, Pos], int] = {}
        self.vertex_edges: Dict[Pos, Dict[str, Optional[int]]] = {}
        self.edge_state: List[int] = []  # -1 unknown, 0 off, 1 on
        self.clues: Dict[Pos, str] = {}
        self.clue_domains: Dict[Pos, Set[str]] = {}
        self._dead_cache: Set[Tuple] = set()

        self._build_graph()
        self._init_clues()

    def _msg(self, brief: str, full: str) -> str:
        return brief

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

    def _parse_clue(self, token) -> Optional[str]:
        if token is None:
            return None
        if not isinstance(token, str):
            return None
        s = token.strip().upper()
        if not s:
            return None
        if s[0] not in {"W", "B"}:
            return None
        return s[0]

    def _init_clues(self):
        for r in range(self.n):
            for c in range(self.n):
                t = self._parse_clue(self.grid[r][c])
                if t is not None:
                    self.clues[(r, c)] = t
        for pos, t in self.clues.items():
            if t == "W":
                self.clue_domains[pos] = {"H", "V"}
            else:
                self.clue_domains[pos] = {"UR", "UL", "DR", "DL"}

    def _snapshot(self):
        return (
            self.edge_state[:],
            {p: set(d) for p, d in self.clue_domains.items()},
            self._last_fail,
        )

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

    def _set_edge(self, eid: int, val: int, why: str, logs) -> bool:
        cur = self.edge_state[eid]
        if cur == val:
            return True
        if cur != -1 and cur != val:
            self._last_fail = f"edge {self.edges[eid]} conflict {cur} vs {val}"
            return False
        self.edge_state[eid] = val
        return True

    def _vertex_degree_rule(self, pos: Pos, force_deg2: bool, logs) -> bool:
        dirs = self._edge_dirs(pos)
        on = [d for d, st in dirs.items() if st == 1]
        off = [d for d, st in dirs.items() if st == 0]
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
                    why = self._msg(
                        f"clue {pos} already has degree 2",
                        f"clue at {pos} must have degree 2; with two incident lines fixed, edge {self.edges[eid]} is forced empty.",
                    )
                    if not self._set_edge(eid, 0, why, logs):
                        return False
            elif len(on) + len(unk) == 2:
                for d in unk:
                    eid = self.vertex_edges[pos][d]
                    why = self._msg(
                        f"clue {pos} needs degree 2",
                        f"clue at {pos} must be on loop and only two incident edges remain available, so {self.edges[eid]} is forced line.",
                    )
                    if not self._set_edge(eid, 1, why, logs):
                        return False
            return True

        # non-clue: degree must be 0 or 2
        if len(on) == 2:
            for d in unk:
                eid = self.vertex_edges[pos][d]
                why = self._msg(
                    f"vertex {pos} already degree 2",
                    f"vertex {pos} cannot have degree >2; with two lines already chosen, edge {self.edges[eid]} is forced empty.",
                )
                if not self._set_edge(eid, 0, why, logs):
                    return False
        if len(on) == 1 and len(unk) == 0:
            self._last_fail = f"vertex {pos} stuck at degree 1"
            return False
        if len(on) == 1 and len(unk) == 1:
            eid = self.vertex_edges[pos][unk[0]]
            why = self._msg(
                f"vertex {pos} avoids degree 1",
                f"vertex {pos} cannot end with odd degree; one incident line already exists and only one edge remains, so {self.edges[eid]} must be line.",
            )
            if not self._set_edge(eid, 1, why, logs):
                return False
        if len(on) == 0 and len(unk) == 1:
            eid = self.vertex_edges[pos][unk[0]]
            why = self._msg(
                f"vertex {pos} cannot make degree 1",
                f"vertex {pos} is currently isolated and only edge {self.edges[eid]} is undecided; setting it line would create degree 1, so it is forced empty.",
            )
            if not self._set_edge(eid, 0, why, logs):
                return False
        return True

    def _can_neighbor_straight(self, nb: Pos, incoming_from: str) -> bool:
        # incoming_from is direction at nb pointing back to clue.
        inc_eid = self.vertex_edges[nb][incoming_from]
        if inc_eid is None or self.edge_state[inc_eid] == 0:
            return False
        out_dir = OPP[incoming_from]
        out_eid = self.vertex_edges[nb][out_dir]
        if out_eid is None or self.edge_state[out_eid] == 0:
            return False
        for d in DIRS:
            if d in (incoming_from, out_dir):
                continue
            eid = self.vertex_edges[nb][d]
            if eid is not None and self.edge_state[eid] == 1:
                return False
        return True

    def _can_neighbor_turn(self, nb: Pos, incoming_from: str) -> bool:
        inc_eid = self.vertex_edges[nb][incoming_from]
        if inc_eid is None or self.edge_state[inc_eid] == 0:
            return False
        out_dir = OPP[incoming_from]
        out_eid = self.vertex_edges[nb][out_dir]
        if out_eid is not None and self.edge_state[out_eid] == 1:
            return False
        turn_ok = False
        for d in DIRS:
            if d in (incoming_from, out_dir):
                continue
            eid = self.vertex_edges[nb][d]
            if eid is not None and self.edge_state[eid] != 0:
                turn_ok = True
        return turn_ok

    def _force_neighbor_turn(self, nb: Pos, incoming_from: str, logs, why_ctx: str) -> bool:
        inc_eid = self.vertex_edges[nb][incoming_from]
        if inc_eid is None:
            self._last_fail = f"turn forcing at {nb} has no incoming edge"
            return False
        if not self._set_edge(inc_eid, 1, why_ctx, logs):
            return False

        out = OPP[incoming_from]
        out_eid = self.vertex_edges[nb][out]
        if out_eid is not None:
            why = self._msg(
                f"{why_ctx}; {nb} must turn",
                f"{why_ctx}. To force a turn at {nb}, straight-continuation edge {self.edges[out_eid]} must be empty.",
            )
            if not self._set_edge(out_eid, 0, why, logs):
                return False

        perp = []
        for d in DIRS:
            if d in (incoming_from, out):
                continue
            eid = self.vertex_edges[nb][d]
            if eid is not None:
                perp.append(eid)
        if not perp:
            self._last_fail = f"turn forcing at {nb} has no perpendicular exits"
            return False

        on = [eid for eid in perp if self.edge_state[eid] == 1]
        unk = [eid for eid in perp if self.edge_state[eid] == -1]
        if len(on) > 1:
            self._last_fail = f"turn forcing at {nb} has >1 perpendicular lines"
            return False
        if len(on) == 0 and len(unk) == 0:
            self._last_fail = f"turn forcing at {nb} has no available perpendicular exit"
            return False
        if len(on) == 1:
            for eid in unk:
                why = self._msg(
                    f"{why_ctx}; {nb} turn completed",
                    f"{why_ctx}. Vertex {nb} already uses one perpendicular turn edge, so remaining perpendicular edge {self.edges[eid]} is empty.",
                )
                if not self._set_edge(eid, 0, why, logs):
                    return False
        elif len(unk) == 1:
            eid = unk[0]
            why = self._msg(
                f"{why_ctx}; {nb} needs perpendicular edge",
                f"{why_ctx}. With straight blocked at {nb}, the only remaining perpendicular edge {self.edges[eid]} is forced line.",
            )
            if not self._set_edge(eid, 1, why, logs):
                return False
        return True

    def _orientation_edges(self, pos: Pos, ori: str) -> Tuple[Set[int], Set[int]]:
        req_on: Set[int] = set()
        req_off: Set[int] = set()
        if ori == "H":
            on_dirs = {"L", "R"}
        elif ori == "V":
            on_dirs = {"U", "D"}
        else:
            on_dirs = set(ori)
        for d in DIRS:
            eid = self.vertex_edges[pos][d]
            if eid is None:
                continue
            if d in on_dirs:
                req_on.add(eid)
            else:
                req_off.add(eid)
        return req_on, req_off

    def _orientation_feasible(self, pos: Pos, ori: str) -> bool:
        req_on, req_off = self._orientation_edges(pos, ori)
        for eid in req_on:
            if self.edge_state[eid] == 0:
                return False
        for eid in req_off:
            if self.edge_state[eid] == 1:
                return False

        clue_type = self.clues[pos]
        if clue_type == "B":
            # Black pearl: neighbors in both outgoing directions must be straight.
            for d in ori:
                nb = self._neighbor(pos, d)
                if nb is None:
                    return False
                if not self._can_neighbor_straight(nb, OPP[d]):
                    return False
        else:
            # White pearl: straight here and at least one adjacent vertex (along path) turns.
            if ori == "H":
                dirs = ("L", "R")
            else:
                dirs = ("U", "D")
            turn_possible = False
            for d in dirs:
                nb = self._neighbor(pos, d)
                if nb is None:
                    return False
                if self._can_neighbor_turn(nb, OPP[d]):
                    turn_possible = True
            if not turn_possible:
                return False
        return True

    def _propagate_clues(self, logs) -> bool:
        for pos in self.clues:
            dom = self.clue_domains[pos]
            feasible = {ori for ori in dom if self._orientation_feasible(pos, ori)}
            if not feasible:
                self._last_fail = f"clue {pos} has no feasible orientation"
                return False
            if feasible != dom:
                self.clue_domains[pos] = feasible

            # Common implied edge decisions among all feasible orientations.
            all_on = None
            all_off = None
            for ori in self.clue_domains[pos]:
                req_on, req_off = self._orientation_edges(pos, ori)
                all_on = req_on if all_on is None else (all_on & req_on)
                all_off = req_off if all_off is None else (all_off & req_off)
            all_on = all_on or set()
            all_off = all_off or set()

            for eid in all_on:
                why = self._msg(
                    f"clue {pos} orientation forcing",
                    f"all feasible orientations for clue {pos} require edge {self.edges[eid]} to be line.",
                )
                if not self._set_edge(eid, 1, why, logs):
                    return False
            for eid in all_off:
                why = self._msg(
                    f"clue {pos} orientation forcing",
                    f"all feasible orientations for clue {pos} forbid edge {self.edges[eid]}, so it is forced empty.",
                )
                if not self._set_edge(eid, 0, why, logs):
                    return False

            # If singleton orientation, apply black-neighbor straight implications directly.
            if len(self.clue_domains[pos]) == 1 and self.clues[pos] == "B":
                ori = next(iter(self.clue_domains[pos]))
                for d in ori:
                    nb = self._neighbor(pos, d)
                    if nb is None:
                        self._last_fail = f"black clue {pos} points outside board"
                        return False
                    inc = OPP[d]
                    out = d
                    eid_out = self.vertex_edges[nb][out]
                    if eid_out is None:
                        self._last_fail = f"black clue {pos} requires straight through boundary at {nb}"
                        return False
                    why = self._msg(
                        f"black clue {pos} enforces straight at {nb}",
                        f"black clue at {pos} turns, so the neighboring vertex {nb} must go straight away from clue; edge {self.edges[eid_out]} is forced line.",
                    )
                    if not self._set_edge(eid_out, 1, why, logs):
                        return False
                    for td in DIRS:
                        if td in (inc, out):
                            continue
                        teid = self.vertex_edges[nb][td]
                        if teid is not None:
                            why2 = self._msg(
                                f"black clue {pos} enforces straight at {nb}",
                                f"to keep {nb} straight relative to black clue {pos}, perpendicular edge {self.edges[teid]} is forced empty.",
                            )
                            if not self._set_edge(teid, 0, why2, logs):
                                return False
            # White singleton: if one side cannot turn, the other side must turn.
            if len(self.clue_domains[pos]) == 1 and self.clues[pos] == "W":
                ori = next(iter(self.clue_domains[pos]))
                dirs = ("L", "R") if ori == "H" else ("U", "D")
                side_info = []
                for d in dirs:
                    nb = self._neighbor(pos, d)
                    if nb is None:
                        self._last_fail = f"white clue {pos} points outside board"
                        return False
                    inc = OPP[d]
                    can_turn = self._can_neighbor_turn(nb, inc)
                    side_info.append((d, nb, inc, can_turn))
                if not side_info[0][3] and not side_info[1][3]:
                    self._last_fail = f"white clue {pos} has no possible adjacent turn"
                    return False
                if side_info[0][3] ^ side_info[1][3]:
                    forced = side_info[0] if side_info[0][3] else side_info[1]
                    _, nb, inc, _ = forced
                    why = self._msg(
                        f"white clue {pos} requires adjacent turn at {nb}",
                        f"white clue at {pos} must have at least one adjacent turn; only vertex {nb} can still turn, so it is forced to turn.",
                    )
                    if not self._force_neighbor_turn(nb, inc, logs, why):
                        return False
        return True

    def _prevent_premature_cycle(self, logs) -> bool:
        adj: Dict[Pos, List[Pos]] = {}
        for eid, st in enumerate(self.edge_state):
            if st != 1:
                continue
            a, b = self.edges[eid]
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        if not adj:
            return True

        comp_of: Dict[Pos, int] = {}
        comps: List[Set[Pos]] = []
        for start in adj:
            if start in comp_of:
                continue
            cid = len(comps)
            stack = [start]
            comp = set([start])
            comp_of[start] = cid
            while stack:
                cur = stack.pop()
                for nxt in adj[cur]:
                    if nxt not in comp_of:
                        comp_of[nxt] = cid
                        comp.add(nxt)
                        stack.append(nxt)
            comps.append(comp)

        clue_set = set(self.clues.keys())
        comp_count = len(comps)

        for eid, st in enumerate(self.edge_state):
            if st != -1:
                continue
            a, b = self.edges[eid]
            if a not in comp_of or b not in comp_of:
                continue
            ca = comp_of[a]
            cb = comp_of[b]
            if ca != cb:
                continue
            # Only a path-endpoint join can close a component into a cycle.
            if len(adj[a]) != 1 or len(adj[b]) != 1:
                continue
            comp = comps[ca]
            if clue_set.issubset(comp) and comp_count == 1:
                continue
            why = self._msg(
                f"prevent premature cycle on {self.edges[eid]}",
                f"setting edge {self.edges[eid]} to line would close a subloop before all clues/components can join, so it is forced empty.",
            )
            if not self._set_edge(eid, 0, why, logs):
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
            comp = set([start])
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
            # A closed cycle is only allowed if it already contains all mandatory clue vertices
            # and there are no other used vertices outside it.
            if not clue_set.issubset(comp):
                return True
            if comp != total_used_vertices:
                return True
        return False

    def _propagate(self):
        logs = []
        while True:
            start_len = len(logs)

            for r in range(self.n):
                for c in range(self.n):
                    pos = (r, c)
                    if not self._vertex_degree_rule(pos, pos in self.clues, logs):
                        return False, logs

            if not self._propagate_clues(logs):
                return False, logs

            for pos in self.clues:
                if len(self.clue_domains[pos]) == 0:
                    self._last_fail = f"clue {pos} has empty domain"
                    return False, logs

            if not self._prevent_premature_cycle(logs):
                return False, logs

            if not self._clues_potentially_connected():
                return False, logs

            if self._has_forbidden_subloop():
                self._last_fail = "forbidden closed subloop"
                return False, logs

            if len(logs) == start_len:
                break
        return True, logs

    def _final_valid(self) -> bool:
        # Degrees
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
                        self._last_fail = f"vertex {pos} has invalid degree {deg}"
                        return False

        # clue orientation and special rules
        for pos in self.clues:
            ok = False
            for ori in self.clue_domains[pos]:
                req_on, req_off = self._orientation_edges(pos, ori)
                if all(self.edge_state[e] == 1 for e in req_on) and all(self.edge_state[e] == 0 for e in req_off):
                    if self._orientation_feasible(pos, ori):
                        ok = True
                        break
            if not ok:
                self._last_fail = f"clue {pos} final orientation invalid"
                return False

        # Single loop check.
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
                self._last_fail = f"used vertex {v} not degree 2 in final loop"
                return False
        start = next(iter(adj))
        stack = [start]
        seen = {start}
        while stack:
            cur = stack.pop()
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        if len(seen) != len(adj):
            self._last_fail = "multiple disjoint loops/components"
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
                w += 4
            if b in clue_vertices:
                w += 4
            for v in (a, b):
                dirs = self._edge_dirs(v)
                on = sum(1 for x in dirs.values() if x == 1)
                unk = sum(1 for x in dirs.values() if x == -1)
                w += (3 - unk) + on
            ranked.append(((-w, eid), eid))
        ranked.sort(key=lambda x: x[0])
        return [eid for _, eid in ranked]

    def _choose_branch_edge(self, depth: int = 0) -> Optional[int]:
        ranked = self._rank_branch_edges()
        if not ranked:
            return None
        if self.n < 20 or depth > 4:
            return ranked[0]

        # Shallow lookahead: choose edge with strongest immediate contradiction signal.
        best = ranked[0]
        best_key = (-1, 10**9)
        probe_list = ranked[:10]
        for eid in probe_list:
            fail_count = 0
            for v in (1, 0):
                snap = self._snapshot()
                ok_set = self._set_edge(eid, v, "edge-lookahead", [])
                ok_prop = False
                if ok_set:
                    ok_prop, _ = self._propagate()
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
        best = None
        best_key = None
        for pos, dom in self.clue_domains.items():
            if len(dom) <= 1:
                continue
            t = self.clues[pos]
            key = (len(dom), 0 if t == "B" else 1, pos[0], pos[1])
            if best_key is None or key < best_key:
                best_key = key
                best = pos
        return best

    def _set_orientation(self, pos: Pos, ori: str, logs, stage: str, depth: int) -> bool:
        req_on, req_off = self._orientation_edges(pos, ori)
        clue_type = self.clues[pos]
        for eid in req_on:
            why = self._msg(
                f"branch clue {clue_type}@{pos} choose {ori}",
                f"backtracking ({stage}, depth {depth}): choose orientation {ori} for clue {clue_type}@{pos}, so edge {self.edges[eid]} is forced line.",
            )
            if not self._set_edge(eid, 1, why, logs):
                return False
        for eid in req_off:
            why = self._msg(
                f"branch clue {clue_type}@{pos} choose {ori}",
                f"backtracking ({stage}, depth {depth}): choose orientation {ori} for clue {clue_type}@{pos}, so edge {self.edges[eid]} is forced empty.",
            )
            if not self._set_edge(eid, 0, why, logs):
                return False
        self.clue_domains[pos] = {ori}
        return True

    def _search_one(self, depth: int, depth_limit: Optional[int], stage: str):
        if depth_limit is None:
            sk = self._state_key()
            if sk in self._dead_cache:
                return None, []

        ok, base_logs = self._propagate()
        if not ok:
            return None, base_logs

        if depth_limit is None:
            sk = self._state_key()
            if sk in self._dead_cache:
                return None, base_logs

        if all(st != -1 for st in self.edge_state):
            path = self._build_path()
            if path is not None:
                return path, base_logs
            if depth_limit is None:
                self._dead_cache.add(sk)
            return None, base_logs

        if depth_limit is not None and depth >= depth_limit:
            self._last_fail = f"depth cap reached at stage {stage}"
            return None, base_logs

        cpos = self._choose_branch_clue()
        if cpos is not None:
            dom = sorted(self.clue_domains[cpos])
            for ori in dom:
                snap = self._snapshot()
                branch_logs = []
                if self._set_orientation(cpos, ori, branch_logs, stage, depth):
                    ans, deeper = self._search_one(depth + 1, depth_limit, stage)
                    if ans is not None:
                        return ans, base_logs + branch_logs + deeper
                self._restore(snap)
            if depth_limit is None:
                self._dead_cache.add(self._state_key())
            return None, base_logs

        eid = self._choose_branch_edge(depth)
        if eid is None:
            return None, base_logs

        # Try line first near clues.
        for v in (1, 0):
            snap = self._snapshot()
            branch_logs = []
            why = self._msg(
                f"branch try edge {self.edges[eid]}={'line' if v == 1 else 'empty'}",
                f"backtracking ({stage}, depth {depth}): assume edge {self.edges[eid]} is {'line' if v == 1 else 'empty'}.",
            )
            if self._set_edge(eid, v, why, branch_logs):
                ans, deeper = self._search_one(depth + 1, depth_limit, stage)
                if ans is not None:
                    return ans, base_logs + branch_logs + deeper
            self._restore(snap)

        if depth_limit is None:
            self._dead_cache.add(self._state_key())
        return None, base_logs

    def solve_staged(self):
        ok0, logs0 = self._propagate()
        if not ok0:
            return None, logs0
        if all(st != -1 for st in self.edge_state):
            path = self._build_path()
            if path is not None:
                return path, logs0

        if self.n <= 12:
            for cap in (2, 4, 6, 8):
                snap = self._snapshot()
                ans, logs = self._search_one(0, cap, f"short-depth({cap})")
                if ans is not None:
                    return ans, logs
                self._restore(snap)
        return self._search_one(0, None, "full-search")


def _normalize_observation(observation):
    data = observation
    if isinstance(data, dict):
        data = data.get("data", data)
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError("observation must be a non-empty 2D list")
    n = len(data)
    if any(len(row) != n for row in data):
        raise ValueError("masyu grid must be square")
    return [row[:] for row in data]



def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 12000,
    log_level: str = "brief",
):
    grid = _normalize_observation(observation)
    solver = _MasyuSolver(grid)
    answer, _ = solver.solve_staged()
    if answer is None:
        return "No Solution"
    return [tuple(p) for p in answer]
