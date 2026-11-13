from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

Pos = Tuple[int, int]
Edge = Tuple[Pos, Pos]


@dataclass(frozen=True)
class _Candidate:
    a: Pos
    b: Pos
    pair_id: int


class _StitchesSolver:
    def __init__(
        self,
        region_grid: Sequence[Sequence[int]],
        row_target: Sequence[int],
        col_target: Sequence[int],
    ):
        self.region = [list(row) for row in region_grid]
        self.n = len(self.region)
        self.row_target = list(row_target)
        self.col_target = list(col_target)
        self._last_fail = ""

        if any(len(row) != self.n for row in self.region):
            raise ValueError("region grid must be square")
        if len(self.row_target) != self.n or len(self.col_target) != self.n:
            raise ValueError("row/col stitch counts must have length N")

        self.cands: List[_Candidate] = []
        self.pairs: List[Tuple[int, int]] = []
        self.pair_domains: List[Set[int]] = []
        self.pair_assigned: List[Optional[int]] = []

        # hole -> candidate ids incident to it
        self.hole_incident: Dict[Pos, List[int]] = {(r, c): [] for r in range(self.n) for c in range(self.n)}

        # row/col -> holes in that row/col
        self.row_holes: List[List[Pos]] = [[(r, c) for c in range(self.n)] for r in range(self.n)]
        self.col_holes: List[List[Pos]] = [[(r, c) for r in range(self.n)] for c in range(self.n)]

        self.edge_state: List[int] = []  # -1 unknown, 0 no stitch, 1 stitch
        self.hole_used_by: Dict[Pos, Optional[int]] = {(r, c): None for r in range(self.n) for c in range(self.n)}
        self.row_used = [0] * self.n
        self.col_used = [0] * self.n

        self._build_candidates()

    def _msg(self, brief: str, full: str) -> str:
        return brief

    def _build_candidates(self):
        pair_to_idx: Dict[Tuple[int, int], int] = {}

        def reg_pair(a: int, b: int) -> Tuple[int, int]:
            return (a, b) if a < b else (b, a)

        for r in range(self.n):
            for c in range(self.n):
                if c + 1 < self.n and self.region[r][c] != self.region[r][c + 1]:
                    p = reg_pair(self.region[r][c], self.region[r][c + 1])
                    if p not in pair_to_idx:
                        pair_to_idx[p] = len(self.pairs)
                        self.pairs.append(p)
                        self.pair_domains.append(set())
                        self.pair_assigned.append(None)
                    pid = pair_to_idx[p]
                    cid = len(self.cands)
                    cand = _Candidate((r, c), (r, c + 1), pid)
                    self.cands.append(cand)
                    self.pair_domains[pid].add(cid)
                    self.hole_incident[cand.a].append(cid)
                    self.hole_incident[cand.b].append(cid)

                if r + 1 < self.n and self.region[r][c] != self.region[r + 1][c]:
                    p = reg_pair(self.region[r][c], self.region[r + 1][c])
                    if p not in pair_to_idx:
                        pair_to_idx[p] = len(self.pairs)
                        self.pairs.append(p)
                        self.pair_domains.append(set())
                        self.pair_assigned.append(None)
                    pid = pair_to_idx[p]
                    cid = len(self.cands)
                    cand = _Candidate((r, c), (r + 1, c), pid)
                    self.cands.append(cand)
                    self.pair_domains[pid].add(cid)
                    self.hole_incident[cand.a].append(cid)
                    self.hole_incident[cand.b].append(cid)

        self.edge_state = [-1] * len(self.cands)

    def _snapshot(self):
        return (
            self.edge_state[:],
            [d.copy() for d in self.pair_domains],
            self.pair_assigned[:],
            dict(self.hole_used_by),
            self.row_used[:],
            self.col_used[:],
            self._last_fail,
        )

    def _restore(self, snap):
        (
            self.edge_state,
            self.pair_domains,
            self.pair_assigned,
            self.hole_used_by,
            self.row_used,
            self.col_used,
            self._last_fail,
        ) = snap

    def _remove_from_domain(self, pid: int, cid: int, logs, why: str) -> bool:
        if cid not in self.pair_domains[pid]:
            return True
        if self.edge_state[cid] == 1:
            self._last_fail = f"pair {self.pairs[pid]} already fixed to candidate {cid}, cannot remove it"
            return False
        self.pair_domains[pid].remove(cid)
        return self._set_edge(cid, 0, why, logs)

    def _set_edge(self, cid: int, val: int, why: str, logs) -> bool:
        cur = self.edge_state[cid]
        if cur == val:
            return True
        if cur != -1 and cur != val:
            self._last_fail = f"edge {self.cands[cid].a}-{self.cands[cid].b} conflict {cur} vs {val}"
            return False

        cand = self.cands[cid]
        pid = cand.pair_id
        pair_name = self.pairs[pid]

        if val == 0:
            self.edge_state[cid] = 0
            token = "X"
            pos = (cand.a, cand.b)
            logs.append((token, pos, why))
            return True

        # val == 1
        if self.pair_assigned[pid] is not None and self.pair_assigned[pid] != cid:
            self._last_fail = f"region pair {pair_name} already assigned to different stitch"
            return False

        a, b = cand.a, cand.b
        if self.hole_used_by[a] is not None and self.hole_used_by[a] != cid:
            self._last_fail = f"hole {a} already used by another stitch"
            return False
        if self.hole_used_by[b] is not None and self.hole_used_by[b] != cid:
            self._last_fail = f"hole {b} already used by another stitch"
            return False

        self.edge_state[cid] = 1
        self.pair_assigned[pid] = cid
        self.hole_used_by[a] = cid
        self.hole_used_by[b] = cid
        self.row_used[a[0]] += 1
        self.col_used[a[1]] += 1
        self.row_used[b[0]] += 1
        self.col_used[b[1]] += 1

        # Pair exact-one: all others become 0.
        for other in list(self.pair_domains[pid]):
            if other != cid:
                why2 = self._msg(
                    f"pair {pair_name} already stitched at {cand.a}-{cand.b}",
                    f"region pair {pair_name} must use exactly one stitch; with {cand.a}-{cand.b} selected, candidate {self.cands[other].a}-{self.cands[other].b} is forbidden.",
                )
                if not self._set_edge(other, 0, why2, logs):
                    return False
        self.pair_domains[pid] = {cid}

        # Hole conflict: no other stitch may touch used holes.
        for hole in (a, b):
            for other in self.hole_incident[hole]:
                if other == cid:
                    continue
                opid = self.cands[other].pair_id
                if other in self.pair_domains[opid]:
                    why2 = self._msg(
                        f"hole {hole} already used",
                        f"hole {hole} is already occupied by stitch {cand.a}-{cand.b}; candidate {self.cands[other].a}-{self.cands[other].b} must be removed.",
                    )
                    if not self._remove_from_domain(opid, other, logs, why2):
                        return False

        token = "S"
        pos = (cand.a, cand.b)
        logs.append((token, pos, why))
        return True

    def _row_col_possible_holes(self):
        row_possible: List[Set[Pos]] = [set() for _ in range(self.n)]
        col_possible: List[Set[Pos]] = [set() for _ in range(self.n)]

        for pid, dom in enumerate(self.pair_domains):
            if self.pair_assigned[pid] is not None:
                continue
            for cid in dom:
                if self.edge_state[cid] == 0:
                    continue
                a, b = self.cands[cid].a, self.cands[cid].b
                if self.hole_used_by[a] is None:
                    row_possible[a[0]].add(a)
                    col_possible[a[1]].add(a)
                if self.hole_used_by[b] is None:
                    row_possible[b[0]].add(b)
                    col_possible[b[1]].add(b)
        return row_possible, col_possible

    def _validate_counts_bounds(self) -> bool:
        row_possible, col_possible = self._row_col_possible_holes()
        for r in range(self.n):
            low = self.row_used[r]
            high = low + len(row_possible[r])
            tgt = self.row_target[r]
            if not (low <= tgt <= high):
                self._last_fail = f"row {r} target {tgt} outside feasible range [{low},{high}]"
                return False
        for c in range(self.n):
            low = self.col_used[c]
            high = low + len(col_possible[c])
            tgt = self.col_target[c]
            if not (low <= tgt <= high):
                self._last_fail = f"col {c} target {tgt} outside feasible range [{low},{high}]"
                return False
        return True

    def _propagate_row_col_full(self, logs) -> bool:
        row_possible, col_possible = self._row_col_possible_holes()

        for r in range(self.n):
            if self.row_used[r] == self.row_target[r]:
                for hole in row_possible[r]:
                    for cid in self.hole_incident[hole]:
                        pid = self.cands[cid].pair_id
                        if cid in self.pair_domains[pid]:
                            why = self._msg(
                                f"row {r} count reached target",
                                f"row {r} already has required {self.row_target[r]} used holes, so candidate {self.cands[cid].a}-{self.cands[cid].b} cannot use hole {hole}.",
                            )
                            if not self._remove_from_domain(pid, cid, logs, why):
                                return False

        for c in range(self.n):
            if self.col_used[c] == self.col_target[c]:
                for hole in col_possible[c]:
                    for cid in self.hole_incident[hole]:
                        pid = self.cands[cid].pair_id
                        if cid in self.pair_domains[pid]:
                            why = self._msg(
                                f"col {c} count reached target",
                                f"column {c} already has required {self.col_target[c]} used holes, so candidate {self.cands[cid].a}-{self.cands[cid].b} cannot use hole {hole}.",
                            )
                            if not self._remove_from_domain(pid, cid, logs, why):
                                return False
        return True

    def _propagate(self):
        logs = []
        while True:
            start_len = len(logs)

            for pid, dom in enumerate(self.pair_domains):
                if not dom:
                    self._last_fail = f"region pair {self.pairs[pid]} has no candidate stitch left"
                    return False, logs
                if self.pair_assigned[pid] is None and len(dom) == 1:
                    cid = next(iter(dom))
                    why = self._msg(
                        f"pair {self.pairs[pid]} single candidate",
                        f"region pair {self.pairs[pid]} has only one remaining candidate {self.cands[cid].a}-{self.cands[cid].b}, so it must be selected.",
                    )
                    if not self._set_edge(cid, 1, why, logs):
                        return False, logs

            if not self._validate_counts_bounds():
                return False, logs

            if not self._propagate_row_col_full(logs):
                return False, logs

            if len(logs) == start_len:
                break
        return True, logs

    def _is_complete(self) -> bool:
        return all(a is not None for a in self.pair_assigned)

    def _build_answer(self):
        ret: List[Edge] = []
        for cid, st in enumerate(self.edge_state):
            if st == 1:
                c = self.cands[cid]
                ret.append((c.a, c.b))
        ret.sort()
        return ret

    def _final_check(self) -> bool:
        if not self._is_complete():
            return False
        if self.row_used != self.row_target:
            self._last_fail = f"row counts mismatch used={self.row_used} target={self.row_target}"
            return False
        if self.col_used != self.col_target:
            self._last_fail = f"col counts mismatch used={self.col_used} target={self.col_target}"
            return False
        return True

    def _choose_pair(self) -> Optional[int]:
        best_pid = None
        best_key = None
        for pid, dom in enumerate(self.pair_domains):
            if self.pair_assigned[pid] is not None:
                continue
            if not dom:
                return pid
            # Prefer smallest domain, then highest hole pressure.
            pressure = 0
            for cid in dom:
                a, b = self.cands[cid].a, self.cands[cid].b
                pressure += len(self.hole_incident[a]) + len(self.hole_incident[b])
            key = (len(dom), -pressure)
            if best_key is None or key < best_key:
                best_key = key
                best_pid = pid
        return best_pid

    def _search_one(self, depth: int, depth_limit: Optional[int], stage: str):
        ok, base_logs = self._propagate()
        if not ok:
            return None, base_logs

        if self._is_complete():
            if self._final_check():
                return self._build_answer(), base_logs
            return None, base_logs

        if depth_limit is not None and depth >= depth_limit:
            self._last_fail = f"depth cap reached at stage {stage}"
            return None, base_logs

        pid = self._choose_pair()
        if pid is None:
            return None, base_logs

        dom = sorted(self.pair_domains[pid])
        for cid in dom:
            snap = self._snapshot()
            branch_logs = []
            why = self._msg(
                f"branch pair {self.pairs[pid]} try {self.cands[cid].a}-{self.cands[cid].b}",
                f"backtracking ({stage}, depth {depth}): choose candidate {self.cands[cid].a}-{self.cands[cid].b} for region pair {self.pairs[pid]}.",
            )
            if self._set_edge(cid, 1, why, branch_logs):
                ans, deeper = self._search_one(depth + 1, depth_limit, stage)
                if ans is not None:
                    return ans, base_logs + branch_logs + deeper

            self._restore(snap)

        return None, base_logs

    def solve_staged(self):
        ok0, logs0 = self._propagate()
        if not ok0:
            return None, logs0
        if self._is_complete() and self._final_check():
            return self._build_answer(), logs0

        # Short depth first for fast puzzles, then full search.
        for cap in (4, 8, 12):
            snap = self._snapshot()
            ans, logs = self._search_one(0, cap, f"short-depth({cap})")
            if ans is not None:
                return ans, logs
            self._restore(snap)

        return self._search_one(0, None, "full-search")



def _normalize_observation(observation):
    if not isinstance(observation, dict):
        raise ValueError("observation must be a dict")
    region = observation.get("region")
    row = observation.get("row_stitch_counts", observation.get("L_nums"))
    col = observation.get("col_stitch_counts", observation.get("U_nums"))
    if region is None or row is None or col is None:
        raise ValueError("observation must include region/row_stitch_counts/col_stitch_counts")
    return region, row, col


def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 10000,
    log_level: str = "brief",
):
    region, row_target, col_target = _normalize_observation(observation)
    solver = _StitchesSolver(region, row_target, col_target)
    answer, _ = solver.solve_staged()
    if answer is None:
        return "No Solution"
    return [[tuple(a), tuple(b)] for (a, b) in answer]
