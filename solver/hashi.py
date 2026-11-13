from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Set, Tuple

Island = Tuple[int, int]
Edge = Tuple[Island, Island]


def _norm_edge(a: Island, b: Island) -> Edge:
    return (a, b) if a <= b else (b, a)


def _normalize_observation(observation):
    data = observation
    if isinstance(data, dict):
        if "original_data" in data and isinstance(data["original_data"], dict):
            data = data["original_data"].get("data")
        elif "data" in data and isinstance(data["data"], list):
            data = data["data"]

    if isinstance(data, dict):
        islands = {}
        for k, v in data.items():
            if isinstance(k, tuple) and len(k) == 2:
                r, c = int(k[0]), int(k[1])
            elif isinstance(k, str) and "," in k:
                a, b = k.split(",", 1)
                r, c = int(float(a)), int(float(b))
            else:
                continue
            if v is None:
                continue
            iv = int(v)
            if iv > 0:
                islands[(r, c)] = iv
        return islands

    if isinstance(data, list) and data and isinstance(data[0], list):
        islands = {}
        for r, row in enumerate(data):
            for c, v in enumerate(row):
                if isinstance(v, int) and v > 0:
                    islands[(r, c)] = int(v)
        return islands

    raise ValueError("unsupported observation format for hashi")


class _HashiSolver:
    def __init__(self, islands: Dict[Island, int]):
        if not islands:
            raise ValueError("hashi needs at least one island")
        self.islands = dict(islands)
        self.nodes = sorted(self.islands.keys())
        self.node_idx = {p: i for i, p in enumerate(self.nodes)}
        self.deg_target = [self.islands[p] for p in self.nodes]

        self.edges: List[Edge] = self._build_edges()

        self.incident: List[List[int]] = [[] for _ in self.nodes]
        for i, (a, b) in enumerate(self.edges):
            ia = self.node_idx[a]
            ib = self.node_idx[b]
            self.incident[ia].append(i)
            self.incident[ib].append(i)

        self.cross_pairs = self._build_crossings()

        self.domains: List[Set[int]] = []
        for a, b in self.edges:
            cap = min(2, self.islands[a], self.islands[b])
            self.domains.append(set(range(cap + 1)))

    def _build_edges(self) -> List[Edge]:
        s = set(self.nodes)
        edges = set()
        max_c = max(x for _, x in self.nodes)
        max_r = max(x for x, _ in self.nodes)
        for r, c in self.nodes:
            cc = c + 1
            while (r, cc) not in s and cc <= max_c:
                cc += 1
            if (r, cc) in s:
                edges.add(_norm_edge((r, c), (r, cc)))

            rr = r + 1
            while (rr, c) not in s and rr <= max_r:
                rr += 1
            if (rr, c) in s:
                edges.add(_norm_edge((r, c), (rr, c)))
        return sorted(edges)

    @staticmethod
    def _is_horizontal(e: Edge) -> bool:
        return e[0][0] == e[1][0]

    @staticmethod
    def _cross(eh: Edge, ev: Edge) -> bool:
        r = eh[0][0]
        c1, c2 = sorted([eh[0][1], eh[1][1]])
        c = ev[0][1]
        r1, r2 = sorted([ev[0][0], ev[1][0]])
        return c1 < c < c2 and r1 < r < r2

    def _build_crossings(self) -> List[Tuple[int, int]]:
        h = []
        v = []
        for i, e in enumerate(self.edges):
            if self._is_horizontal(e):
                h.append((i, e))
            else:
                v.append((i, e))
        out = []
        for ih, eh in h:
            for iv, ev in v:
                if self._cross(eh, ev):
                    out.append((ih, iv))
        return out

    def _snapshot(self):
        return [set(d) for d in self.domains]

    def _restore(self, snap):
        self.domains = snap

    def _prune_degrees(self):
        changed = False
        for ni, need in enumerate(self.deg_target):
            inc = self.incident[ni]
            if not inc:
                if need != 0:
                    return False, False
                continue
            mins = [min(self.domains[e]) for e in inc]
            maxs = [max(self.domains[e]) for e in inc]
            mn = sum(mins)
            mx = sum(maxs)
            if need < mn or need > mx:
                return False, False

            for k, e in enumerate(inc):
                other_min = mn - mins[k]
                other_max = mx - maxs[k]
                nd = {v for v in self.domains[e] if other_min <= need - v <= other_max}
                if not nd:
                    return False, False
                if nd != self.domains[e]:
                    self.domains[e] = nd
                    changed = True
        return True, changed

    def _prune_crossings(self):
        changed = False
        for e1, e2 in self.cross_pairs:
            d1 = self.domains[e1]
            d2 = self.domains[e2]

            nd1 = {v for v in d1 if (v == 0) or (0 in d2)}
            nd2 = {v for v in d2 if (v == 0) or (0 in d1)}

            if not nd1 or not nd2:
                return False, False

            if nd1 != d1:
                self.domains[e1] = nd1
                changed = True
            if nd2 != d2:
                self.domains[e2] = nd2
                changed = True
        return True, changed

    def _connectivity_feasible(self) -> bool:
        if len(self.nodes) <= 1:
            return True

        graph = [[] for _ in self.nodes]
        for i, (a, b) in enumerate(self.edges):
            if max(self.domains[i]) == 0:
                continue
            ia = self.node_idx[a]
            ib = self.node_idx[b]
            graph[ia].append(ib)
            graph[ib].append(ia)

        q = deque([0])
        seen = {0}
        while q:
            u = q.popleft()
            for v in graph[u]:
                if v not in seen:
                    seen.add(v)
                    q.append(v)
        return len(seen) == len(self.nodes)

    def _propagate(self):
        while True:
            changed = False

            ok, ch = self._prune_degrees()
            if not ok:
                return False
            changed = changed or ch

            ok, ch = self._prune_crossings()
            if not ok:
                return False
            changed = changed or ch

            if not self._connectivity_feasible():
                return False

            if not changed:
                return True

    def _is_complete(self) -> bool:
        return all(len(d) == 1 for d in self.domains)

    def _final_valid(self) -> bool:
        vals = [next(iter(d)) for d in self.domains]

        for ni, need in enumerate(self.deg_target):
            if sum(vals[e] for e in self.incident[ni]) != need:
                return False

        for e1, e2 in self.cross_pairs:
            if vals[e1] > 0 and vals[e2] > 0:
                return False

        if len(self.nodes) > 1:
            graph = [[] for _ in self.nodes]
            for i, (a, b) in enumerate(self.edges):
                if vals[i] <= 0:
                    continue
                ia = self.node_idx[a]
                ib = self.node_idx[b]
                graph[ia].append(ib)
                graph[ib].append(ia)
            q = deque([0])
            seen = {0}
            while q:
                u = q.popleft()
                for v in graph[u]:
                    if v not in seen:
                        seen.add(v)
                        q.append(v)
            if len(seen) != len(self.nodes):
                return False

        return True

    def _build_answer(self):
        out = {}
        for i, e in enumerate(self.edges):
            v = next(iter(self.domains[i]))
            if v > 0:
                out[e] = v
        return out

    def _choose_branch(self):
        best = None
        best_vals = []
        best_key = None

        cross_count = [0] * len(self.edges)
        for e1, e2 in self.cross_pairs:
            cross_count[e1] += 1
            cross_count[e2] += 1

        for i, d in enumerate(self.domains):
            if len(d) <= 1:
                continue
            a, b = self.edges[i]
            impact = self.islands[a] + self.islands[b] + cross_count[i]
            key = (len(d), -impact)
            if best_key is None or key < best_key:
                best_key = key
                best = i
                best_vals = sorted(d, reverse=True)

        return best, best_vals

    def _search(self):
        if not self._propagate():
            return None
        if self._is_complete():
            return self._build_answer() if self._final_valid() else None

        ei, vals = self._choose_branch()
        if ei is None:
            return None

        for v in vals:
            snap = self._snapshot()
            self.domains[ei] = {v}
            ans = self._search()
            if ans is not None:
                return ans
            self._restore(snap)

        return None

    def solve(self):
        return self._search()


def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 8000,
    log_level: str = "brief",
):
    del verbose, max_logs, log_level

    islands = _normalize_observation(observation)
    solver = _HashiSolver(islands)
    answer = solver.solve()
    return answer if answer is not None else "No Solution"
