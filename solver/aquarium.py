from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

Pos = Tuple[int, int]
GridAqua = List[List[Optional[str]]]


def _normalize_observation(observation):
    data = observation
    if isinstance(data, dict) and "original_data" in data and isinstance(data["original_data"], dict):
        data = data["original_data"]
    if not isinstance(data, dict):
        raise ValueError("aquarium observation must be a dict")

    region = data.get("region")
    row_counts = data.get("row_water_counts", data.get("L_nums"))
    col_counts = data.get("col_water_counts", data.get("U_nums"))

    if not isinstance(region, list) or not region or not isinstance(region[0], list):
        raise ValueError("region must be a non-empty 2D grid")
    n = len(region)
    if any(len(row) != n for row in region):
        raise ValueError("aquarium grid must be square")
    if not isinstance(row_counts, list) or not isinstance(col_counts, list):
        raise ValueError("missing row/col water counts")
    if len(row_counts) != n or len(col_counts) != n:
        raise ValueError("row/col counts length mismatch")

    return [list(map(int, row)) for row in region], [int(x) for x in row_counts], [int(x) for x in col_counts]


class _RegionOption:
    def __init__(self, water_cells: Set[Pos], row_contrib: List[int], col_contrib: List[int]):
        self.water_cells = water_cells
        self.row_contrib = row_contrib
        self.col_contrib = col_contrib


class _AquariumSolver:
    def __init__(self, region_grid, row_targets, col_targets):
        self.region = region_grid
        self.n = len(region_grid)
        self.row_targets = row_targets
        self.col_targets = col_targets

        self.region_cells: Dict[int, List[Pos]] = {}
        for r in range(self.n):
            for c in range(self.n):
                rid = self.region[r][c]
                self.region_cells.setdefault(rid, []).append((r, c))

        self.region_ids = sorted(self.region_cells.keys())
        self.options: Dict[int, List[_RegionOption]] = {}
        self.domains: Dict[int, Set[int]] = {}

        for rid in self.region_ids:
            cells = self.region_cells[rid]
            seen = set()
            opts: List[_RegionOption] = []
            for t in range(self.n + 1):
                water = {(r, c) for (r, c) in cells if r >= t}
                key = tuple(sorted(water))
                if key in seen:
                    continue
                seen.add(key)
                row_contrib = [0] * self.n
                col_contrib = [0] * self.n
                for r, c in water:
                    row_contrib[r] += 1
                    col_contrib[c] += 1
                opts.append(_RegionOption(water, row_contrib, col_contrib))
            if not opts:
                raise ValueError(f"region {rid} has no options")
            self.options[rid] = opts
            self.domains[rid] = set(range(len(opts)))

    def _snapshot(self):
        return {rid: set(dom) for rid, dom in self.domains.items()}

    def _restore(self, snap):
        self.domains = snap

    def _compute_bounds(self):
        min_row = [0] * self.n
        max_row = [0] * self.n
        min_col = [0] * self.n
        max_col = [0] * self.n

        per_rid_min_row = {}
        per_rid_max_row = {}
        per_rid_min_col = {}
        per_rid_max_col = {}

        for rid in self.region_ids:
            dom = self.domains[rid]
            if not dom:
                return None
            opts = self.options[rid]
            mn_row = [min(opts[oid].row_contrib[r] for oid in dom) for r in range(self.n)]
            mx_row = [max(opts[oid].row_contrib[r] for oid in dom) for r in range(self.n)]
            mn_col = [min(opts[oid].col_contrib[c] for oid in dom) for c in range(self.n)]
            mx_col = [max(opts[oid].col_contrib[c] for oid in dom) for c in range(self.n)]
            per_rid_min_row[rid] = mn_row
            per_rid_max_row[rid] = mx_row
            per_rid_min_col[rid] = mn_col
            per_rid_max_col[rid] = mx_col
            for i in range(self.n):
                min_row[i] += mn_row[i]
                max_row[i] += mx_row[i]
                min_col[i] += mn_col[i]
                max_col[i] += mx_col[i]

        return min_row, max_row, min_col, max_col, per_rid_min_row, per_rid_max_row, per_rid_min_col, per_rid_max_col

    def _prune_once(self):
        info = self._compute_bounds()
        if info is None:
            return False, False

        min_row, max_row, min_col, max_col, pminr, pmaxr, pminc, pmaxc = info

        for r in range(self.n):
            if self.row_targets[r] < min_row[r] or self.row_targets[r] > max_row[r]:
                return False, False
        for c in range(self.n):
            if self.col_targets[c] < min_col[c] or self.col_targets[c] > max_col[c]:
                return False, False

        changed = False
        for rid in self.region_ids:
            dom = self.domains[rid]
            opts = self.options[rid]
            nd = set()

            for oid in dom:
                opt = opts[oid]
                ok = True

                for r in range(self.n):
                    others_min = min_row[r] - pminr[rid][r]
                    others_max = max_row[r] - pmaxr[rid][r]
                    need_other = self.row_targets[r] - opt.row_contrib[r]
                    if need_other < others_min or need_other > others_max:
                        ok = False
                        break
                if not ok:
                    continue

                for c in range(self.n):
                    others_min = min_col[c] - pminc[rid][c]
                    others_max = max_col[c] - pmaxc[rid][c]
                    need_other = self.col_targets[c] - opt.col_contrib[c]
                    if need_other < others_min or need_other > others_max:
                        ok = False
                        break
                if ok:
                    nd.add(oid)

            if not nd:
                return False, False
            if nd != dom:
                self.domains[rid] = nd
                changed = True

        return True, changed

    def _propagate(self) -> bool:
        while True:
            ok, changed = self._prune_once()
            if not ok:
                return False
            if not changed:
                return True

    def _is_complete(self) -> bool:
        return all(len(self.domains[rid]) == 1 for rid in self.region_ids)

    def _build_answer(self) -> GridAqua:
        out: GridAqua = [[None for _ in range(self.n)] for _ in range(self.n)]
        for rid in self.region_ids:
            oid = next(iter(self.domains[rid]))
            water = self.options[rid][oid].water_cells
            for r, c in self.region_cells[rid]:
                out[r][c] = "W" if (r, c) in water else None
        return out

    def _final_valid(self) -> bool:
        ans = self._build_answer()
        for r in range(self.n):
            if sum(1 for c in range(self.n) if ans[r][c] == "W") != self.row_targets[r]:
                return False
        for c in range(self.n):
            if sum(1 for r in range(self.n) if ans[r][c] == "W") != self.col_targets[c]:
                return False
        return True

    def _choose_branch(self):
        best_rid = None
        best_key = None
        for rid in self.region_ids:
            dlen = len(self.domains[rid])
            if dlen <= 1:
                continue
            key = (dlen, -len(self.region_cells[rid]))
            if best_key is None or key < best_key:
                best_key = key
                best_rid = rid
        if best_rid is None:
            return None, []
        return best_rid, sorted(self.domains[best_rid])

    def _search(self):
        if not self._propagate():
            return None
        if self._is_complete():
            return self._build_answer() if self._final_valid() else None

        rid, vals = self._choose_branch()
        if rid is None:
            return None

        for oid in vals:
            snap = self._snapshot()
            self.domains[rid] = {oid}
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
    region, row_targets, col_targets = _normalize_observation(observation)
    solver = _AquariumSolver(region, row_targets, col_targets)
    answer = solver.solve()
    return answer if answer is not None else "No Solution"
