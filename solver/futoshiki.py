from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

Pos = Tuple[int, int]
GridNum = List[List[int]]


def _parse_midpoint_key(k):
    if isinstance(k, tuple) and len(k) == 2:
        return float(k[0]), float(k[1])
    if isinstance(k, str) and "," in k:
        a, b = k.split(",", 1)
        return float(a), float(b)
    raise ValueError(f"invalid inequality key: {k}")


def _normalize_observation(observation):
    if isinstance(observation, dict) and "original_data" in observation and isinstance(observation["original_data"], dict):
        observation = observation["original_data"]

    if isinstance(observation, dict) and "data" in observation:
        data = observation["data"]
        n = len(data)
        if any(len(row) != n for row in data):
            raise ValueError("futoshiki data must be square")
        givens = {}
        for r in range(n):
            for c in range(n):
                v = data[r][c]
                if isinstance(v, int):
                    givens[(r, c)] = int(v)

        relations = []
        h = observation.get("horizontal", {}) or {}
        v = observation.get("vertical", {}) or {}

        for k, sym in h.items():
            r, c = _parse_midpoint_key(k)
            rr = int(round(r))
            left = int(round(c - 0.5))
            right = left + 1
            if not (0 <= rr < n and 0 <= left < n and 0 <= right < n):
                continue
            s = str(sym).strip()
            if s == "<":
                relations.append(((rr, left), (rr, right), "<"))
            elif s == ">":
                relations.append(((rr, right), (rr, left), "<"))

        for k, sym in v.items():
            r, c = _parse_midpoint_key(k)
            cc = int(round(c))
            up = int(round(r - 0.5))
            down = up + 1
            if not (0 <= cc < n and 0 <= up < n and 0 <= down < n):
                continue
            s = str(sym).strip()
            if s == "^":
                relations.append(((up, cc), (down, cc), "<"))
            elif s == "v":
                relations.append(((down, cc), (up, cc), "<"))

        return n, givens, relations

    if isinstance(observation, dict) and "numbers" in observation and "inequalities" in observation:
        givens = {(int(r), int(c)): int(v) for (r, c), v in observation["numbers"].items()}
        all_pos = list(givens.keys())
        for k in observation["inequalities"].keys():
            r, c = _parse_midpoint_key(k)
            if abs(c - round(c)) > 1e-9:
                rr = int(round(r))
                left = int(round(c - 0.5))
                all_pos.extend([(rr, left), (rr, left + 1)])
            else:
                cc = int(round(c))
                up = int(round(r - 0.5))
                all_pos.extend([(up, cc), (up + 1, cc)])
        if not all_pos:
            raise ValueError("cannot infer futoshiki size")
        n = max(max(r for r, _ in all_pos), max(c for _, c in all_pos)) + 1

        relations = []
        for k, sym in observation["inequalities"].items():
            r, c = _parse_midpoint_key(k)
            s = str(sym).strip()
            if abs(c - round(c)) > 1e-9:
                rr = int(round(r))
                left = int(round(c - 0.5))
                right = left + 1
                if s == "<":
                    relations.append(((rr, left), (rr, right), "<"))
                elif s == ">":
                    relations.append(((rr, right), (rr, left), "<"))
            else:
                cc = int(round(c))
                up = int(round(r - 0.5))
                down = up + 1
                if s == "^":
                    relations.append(((up, cc), (down, cc), "<"))
                elif s == "v":
                    relations.append(((down, cc), (up, cc), "<"))
        return n, givens, relations

    raise ValueError("unsupported observation format for futoshiki")


class _FutoshikiSolver:
    def __init__(self, n: int, givens: Dict[Pos, int], relations):
        self.n = n
        self.givens = givens
        self.relations = relations

        base = set(range(1, n + 1))
        self.domains: List[List[Set[int]]] = [[set(base) for _ in range(n)] for _ in range(n)]
        for (r, c), v in givens.items():
            self.domains[r][c] = {v}

    def _snapshot(self):
        return [[set(s) for s in row] for row in self.domains]

    def _restore(self, snap):
        self.domains = snap

    def _remove_from_domain(self, r: int, c: int, forbidden: Set[int]):
        d = self.domains[r][c]
        nd = d - forbidden
        if not nd:
            return False, False
        if nd != d:
            self.domains[r][c] = nd
            return True, True
        return True, False

    def _row_col_eliminate(self):
        changed = False
        for r in range(self.n):
            fixed = {next(iter(self.domains[r][c])) for c in range(self.n) if len(self.domains[r][c]) == 1}
            if len(fixed) != sum(1 for c in range(self.n) if len(self.domains[r][c]) == 1):
                return False, False
            for c in range(self.n):
                if len(self.domains[r][c]) > 1:
                    ok, ch = self._remove_from_domain(r, c, fixed)
                    if not ok:
                        return False, False
                    changed = changed or ch

        for c in range(self.n):
            fixed = {next(iter(self.domains[r][c])) for r in range(self.n) if len(self.domains[r][c]) == 1}
            if len(fixed) != sum(1 for r in range(self.n) if len(self.domains[r][c]) == 1):
                return False, False
            for r in range(self.n):
                if len(self.domains[r][c]) > 1:
                    ok, ch = self._remove_from_domain(r, c, fixed)
                    if not ok:
                        return False, False
                    changed = changed or ch
        return True, changed

    def _hidden_singles(self):
        changed = False
        values = range(1, self.n + 1)

        for r in range(self.n):
            for v in values:
                spots = [c for c in range(self.n) if v in self.domains[r][c]]
                if not spots:
                    return False, False
                if len(spots) == 1 and len(self.domains[r][spots[0]]) > 1:
                    self.domains[r][spots[0]] = {v}
                    changed = True

        for c in range(self.n):
            for v in values:
                spots = [r for r in range(self.n) if v in self.domains[r][c]]
                if not spots:
                    return False, False
                if len(spots) == 1 and len(self.domains[spots[0]][c]) > 1:
                    self.domains[spots[0]][c] = {v}
                    changed = True

        return True, changed

    def _apply_inequalities(self):
        changed = False
        for (ra, ca), (rb, cb), _ in self.relations:
            da = self.domains[ra][ca]
            db = self.domains[rb][cb]

            nda = {a for a in da if any(a < b for b in db)}
            if not nda:
                return False, False
            ndb = {b for b in db if any(a < b for a in da)}
            if not ndb:
                return False, False

            if nda != da:
                self.domains[ra][ca] = nda
                changed = True
            if ndb != db:
                self.domains[rb][cb] = ndb
                changed = True

        return True, changed

    def _propagate(self):
        while True:
            changed = False

            ok, ch = self._row_col_eliminate()
            if not ok:
                return False
            changed = changed or ch

            ok, ch = self._hidden_singles()
            if not ok:
                return False
            changed = changed or ch

            ok, ch = self._apply_inequalities()
            if not ok:
                return False
            changed = changed or ch

            if not changed:
                return True

    def _is_complete(self) -> bool:
        return all(len(self.domains[r][c]) == 1 for r in range(self.n) for c in range(self.n))

    def _build_answer(self) -> GridNum:
        return [[next(iter(self.domains[r][c])) for c in range(self.n)] for r in range(self.n)]

    def _choose_branch(self) -> Tuple[Optional[Pos], List[int]]:
        best = None
        best_vals: List[int] = []
        best_key = None
        for r in range(self.n):
            for c in range(self.n):
                if len(self.domains[r][c]) <= 1:
                    continue
                vals = sorted(self.domains[r][c])
                key = (len(vals), r, c)
                if best_key is None or key < best_key:
                    best_key = key
                    best = (r, c)
                    best_vals = vals
        return best, best_vals

    def _search(self):
        if not self._propagate():
            return None
        if self._is_complete():
            return self._build_answer()

        pos, vals = self._choose_branch()
        if pos is None:
            return None
        r, c = pos

        for v in vals:
            snap = self._snapshot()
            self.domains[r][c] = {v}
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

    n, givens, relations = _normalize_observation(observation)

    solver = _FutoshikiSolver(n, givens, relations)
    answer = solver.solve()
    return answer if answer is not None else "No Solution"
