from __future__ import annotations

import copy
from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import Optional


@dataclass
class Cell:
    i: int
    j: int
    possible: set = field(default_factory=set)
    fill: bool = False
    dtype: str | None = None
    already_update: bool = False

    def selfupdate(self, cell_map, zones, region_grid):
        if self.already_update:
            return True
        if len(self.possible) == 1 and self.fill:
            self.dtype = next(iter(self.possible))
        if self.dtype in {"S", "T", "I", "L"}:
            self.already_update = True
            a = self.dtype
            n = len(cell_map)
            m = len(cell_map[0])
            neighbors = [
                (self.i - 1, self.j),
                (self.i + 1, self.j),
                (self.i, self.j - 1),
                (self.i, self.j + 1),
            ]
            for ni, nj in neighbors:
                if ni < 0 or nj < 0 or ni >= n or nj >= m:
                    continue
                zid = region_grid[ni][nj]
                if zid == region_grid[self.i][self.j]:
                    continue
                if cell_map[ni][nj].dtype == a:
                    return False
                zone = zones[zid]
                new_possible = []
                for p in zone.possible:
                    if p[4] == a and (ni, nj) in p[0:4]:
                        continue
                    new_possible.append(p)
                zone.possible = new_possible
        return True

    def mask(self, cell_map, zones, region_grid):
        if self.dtype in {"S", "T", "I", "L"}:
            return False
        if self.already_update:
            return True
        self.dtype = "x"
        zone = zones[region_grid[self.i][self.j]]
        new_possible = []
        for p in zone.possible:
            if (self.i, self.j) not in p[0:4]:
                new_possible.append(p)
        zone.possible = new_possible
        self.already_update = True
        return True


@dataclass
class Zone:
    zone_id: int
    possible: list = field(default_factory=list)
    z: list = field(default_factory=list)
    dtype: str | None = None

    def selfupdate(self, cell_map, zones, region_grid):
        if not self.possible:
            return False

        for cell in self.z:
            cell.possible = set()

        common = None
        dtype_set = set()
        for p in self.possible:
            coords = set(p[0:4])
            dtype_set.add(p[4])
            for x, y in coords:
                cell_map[x][y].possible.add(p[4])
            if common is None:
                common = coords
            else:
                common &= coords
            if not common:
                break

        covered = set()
        for p in self.possible:
            covered.update(p[0:4])

        for cell in self.z:
            if (cell.i, cell.j) not in covered:
                r = cell.mask(cell_map, zones, region_grid)
                if not r:
                    return False

        if not common:
            return True

        if len(dtype_set) == 1:
            self.dtype = next(iter(dtype_set))

        for cell in self.z:
            if (cell.i, cell.j) in common:
                cell.fill = True
                if len(dtype_set) == 1:
                    cell.dtype = self.dtype
                    cell.possible = {self.dtype}
        return True

    def removep(self, p):
        self.possible = [p1 for p1 in self.possible if p1 != p]


class TetrominoI:
    shapes = [
        [(0, 0), (0, 1), (0, 2), (0, 3)],
        [(0, 0), (1, 0), (2, 0), (3, 0)],
    ]


class TetrominoL:
    shapes = [
        [(0, 0), (1, 0), (2, 0), (2, 1)],
        [(0, 0), (0, 1), (0, 2), (1, 0)],
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(0, 2), (1, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 0)],
        [(0, 0), (1, 0), (1, 1), (1, 2)],
        [(0, 0), (0, 1), (1, 0), (2, 0)],
        [(0, 0), (0, 1), (0, 2), (1, 2)],
    ]


class TetrominoT:
    shapes = [
        [(0, 0), (0, 1), (0, 2), (1, 1)],
        [(0, 1), (1, 1), (2, 1), (1, 0)],
        [(1, 0), (1, 1), (1, 2), (0, 1)],
        [(0, 0), (1, 0), (2, 0), (1, 1)],
    ]


class TetrominoS:
    shapes = [
        [(0, 1), (0, 2), (1, 0), (1, 1)],
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(0, 0), (0, 1), (1, 1), (1, 2)],
        [(0, 1), (1, 0), (1, 1), (2, 0)],
    ]



def _normalize_shape(cells):
    min_r = min(r for r, _ in cells)
    min_c = min(c for _, c in cells)
    return tuple(sorted((r - min_r, c - min_c) for r, c in cells))


def _transforms(cells):
    pts = list(cells)
    out = set()
    for rf in (1, -1):
        for cf in (1, -1):
            for swap in (False, True):
                arr = []
                for r, c in pts:
                    rr, cc = (c, r) if swap else (r, c)
                    arr.append((rf * rr, cf * cc))
                out.add(_normalize_shape(arr))
    return out


_SHAPE_CATALOG = {
    "L": _transforms([(0, 0), (1, 0), (2, 0), (2, 1)]),
    "I": _transforms([(0, 0), (1, 0), (2, 0), (3, 0)]),
    "T": _transforms([(0, 0), (0, 1), (0, 2), (1, 1)]),
    "S": _transforms([(0, 1), (0, 2), (1, 0), (1, 1)]),
}


def _classify_tetromino(cells):
    norm = _normalize_shape(cells)
    for k, forms in _SHAPE_CATALOG.items():
        if norm in forms:
            return k
    return None


def _validate_final_solution(cell_map, region_grid):
    rows = len(region_grid)
    cols = len(region_grid[0])
    shaded = {
        (r, c)
        for r in range(rows)
        for c in range(cols)
        if cell_map[r][c].fill and cell_map[r][c].dtype in {"S", "T", "I", "L"}
    }
    if not shaded:
        return False

    for r in range(rows - 1):
        for c in range(cols - 1):
            block = {(r, c), (r + 1, c), (r, c + 1), (r + 1, c + 1)}
            if block.issubset(shaded):
                return False

    start = next(iter(shaded))
    q = deque([start])
    seen = {start}
    while q:
        r, c = q.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            p = (r + dr, c + dc)
            if p in shaded and p not in seen:
                seen.add(p)
                q.append(p)
    if len(seen) != len(shaded):
        return False

    regions = defaultdict(list)
    for r in range(rows):
        for c in range(cols):
            regions[region_grid[r][c]].append((r, c))

    region_shape = {}
    for rid, cells in regions.items():
        s = [p for p in cells if p in shaded]
        if len(s) != 4:
            return False

        sq = deque([s[0]])
        ss = {s[0]}
        sset = set(s)
        while sq:
            r, c = sq.popleft()
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                p = (r + dr, c + dc)
                if p in sset and p not in ss:
                    ss.add(p)
                    sq.append(p)
        if len(ss) != 4:
            return False

        t = _classify_tetromino(s)
        if t is None:
            return False
        region_shape[rid] = t

        for r, c in s:
            if cell_map[r][c].dtype != t:
                return False

    for r in range(rows):
        for c in range(cols):
            rid = region_grid[r][c]
            for dr, dc in ((1, 0), (0, 1)):
                nr, nc = r + dr, c + dc
                if nr >= rows or nc >= cols:
                    continue
                rid2 = region_grid[nr][nc]
                if rid2 == rid:
                    continue
                if (r, c) in shaded and (nr, nc) in shaded:
                    if region_shape[rid] == region_shape[rid2]:
                        return False

    return True
def build_cell_map(rows: int, cols: int):
    return [[Cell(i, j, dtype="N") for j in range(cols)] for i in range(rows)]


def build_zones(region_grid, cell_map):
    zones = {}
    rows = len(region_grid)
    cols = len(region_grid[0])
    for i in range(rows):
        for j in range(cols):
            zid = int(region_grid[i][j])
            if zid not in zones:
                zones[zid] = Zone(zid)
            zones[zid].z.append(cell_map[i][j])
    return zones


def _add_shapes_to_zones(region_grid, zones, cell_map, shapes, dtype):
    rows = len(region_grid)
    cols = len(region_grid[0])
    for shape in shapes:
        for i in range(rows):
            for j in range(cols):
                coords = [(i + di, j + dj) for di, dj in shape]
                if any(x < 0 or x >= rows or y < 0 or y >= cols for x, y in coords):
                    continue
                zid = int(region_grid[coords[0][0]][coords[0][1]])
                if all(int(region_grid[x][y]) == zid for x, y in coords):
                    zones[zid].possible.append((coords[0], coords[1], coords[2], coords[3], dtype))
                    for x, y in coords:
                        cell_map[x][y].possible.add(dtype)


def add_all_shapes_to_zones(region_grid, zones, cell_map):
    _add_shapes_to_zones(region_grid, zones, cell_map, TetrominoL.shapes, "L")
    _add_shapes_to_zones(region_grid, zones, cell_map, TetrominoI.shapes, "I")
    _add_shapes_to_zones(region_grid, zones, cell_map, TetrominoT.shapes, "T")
    _add_shapes_to_zones(region_grid, zones, cell_map, TetrominoS.shapes, "S")


def mask_if_three_filled(cell_map, zones, region_grid):
    rows = len(cell_map)
    cols = len(cell_map[0])
    for i in range(rows - 1):
        for j in range(cols - 1):
            cells = [
                cell_map[i][j],
                cell_map[i + 1][j],
                cell_map[i][j + 1],
                cell_map[i + 1][j + 1],
            ]
            filled = [c for c in cells if c.fill]
            unfilled = [c for c in cells if not c.fill]

            if len(filled) == 4:
                return False
            if len(filled) == 3:
                for c in cells:
                    if not c.fill:
                        r = c.mask(cell_map, zones, region_grid)
                        if not r:
                            return False
                        break
            if len(filled) == 2:
                z1 = region_grid[unfilled[0].i][unfilled[0].j]
                z2 = region_grid[unfilled[1].i][unfilled[1].j]
                if z1 == z2:
                    zone = zones[z1]
                    new_possible = []
                    for p in zone.possible:
                        if (unfilled[0].i, unfilled[0].j) in p and (unfilled[1].i, unfilled[1].j) in p:
                            continue
                        new_possible.append(p)
                    zone.possible = new_possible
            if len(filled) == 1:
                z1 = region_grid[unfilled[0].i][unfilled[0].j]
                z2 = region_grid[unfilled[1].i][unfilled[1].j]
                z3 = region_grid[unfilled[2].i][unfilled[2].j]
                if z1 == z2 and z2 == z3:
                    zone = zones[z1]
                    new_possible = []
                    for p in zone.possible:
                        if (
                            (unfilled[0].i, unfilled[0].j) in p
                            and (unfilled[1].i, unfilled[1].j) in p
                            and (unfilled[2].i, unfilled[2].j) in p
                        ):
                            continue
                        new_possible.append(p)
                    zone.possible = new_possible
    return True


def get_num_cell(cell_map):
    rows = len(cell_map)
    cols = len(cell_map[0])
    s = 0
    for i in range(rows):
        for j in range(cols):
            if cell_map[i][j].dtype != "N":
                s += 1
    return s


def get_num_fill(zones):
    s = 0
    for z in zones.values():
        s += len(z.possible)
    return s


def inference(cell_map, zones, region_grid):
    pre = -1
    s = get_num_fill(zones)
    while s != pre:
        pre = s
        for zone in zones.values():
            r = zone.selfupdate(cell_map, zones, region_grid)
            if not r:
                return False
        rows = len(cell_map)
        cols = len(cell_map[0])
        for i in range(rows):
            for j in range(cols):
                if not cell_map[i][j].selfupdate(cell_map, zones, region_grid):
                    return False
        r = mask_if_three_filled(cell_map, zones, region_grid)
        if not r:
            return False
        s = get_num_fill(zones)
    return True


def back(cell_map0, zones0):
    zones = copy.deepcopy(zones0)
    cell_map = copy.deepcopy(cell_map0)
    for zz in zones:
        zones[zz].z = [cell_map[q.i][q.j] for q in zones[zz].z]
    return cell_map, zones


def solve_core(cell_map, zones, region_grid, onestep=False, deepth=0, max_deepth=0):
    cell_map = cell_map.copy()
    zones = zones.copy()
    pre = -1
    s = get_num_fill(zones)

    while pre != s:
        pre = s
        if not inference(cell_map, zones, region_grid):
            return 0, cell_map, zones

        rows = len(cell_map)
        cols = len(cell_map[0])
        if get_num_cell(cell_map) == rows * cols:
            if _validate_final_solution(cell_map, region_grid):
                return 1, cell_map, zones
            return 0, cell_map, zones

        if onestep:
            return -1, cell_map, zones

        zones0 = copy.deepcopy(zones)
        cell_map0 = copy.deepcopy(cell_map)
        r = -2
        for z in list(zones.keys()):
            if r == 0:
                break
            zone = zones[z]
            if len(zone.possible) == 1:
                continue
            for p in zone.possible[:]:
                if r == 0:
                    break
                a = p[4]
                for i, j in p[:4]:
                    cell_map[i][j].possible = {a}
                zone.possible = [p]
                r, child_cell_map, child_zones = solve_core(
                    cell_map,
                    zones,
                    region_grid,
                    onestep=(deepth >= max_deepth),
                    max_deepth=max_deepth,
                    deepth=deepth + 1,
                )
                if r == 1:
                    return 1, child_cell_map, child_zones

                cell_map, zones = back(cell_map0, zones0)
                zone = zones[z]
                if r == 0:
                    zone.removep(p)
                    zones0 = copy.deepcopy(zones)
                    cell_map0 = copy.deepcopy(cell_map)
                    if not inference(cell_map, zones, region_grid):
                        cell_map, zones = back(cell_map0, zones0)
                        return 0, cell_map, zones

        s = get_num_fill(zones)

    return -1, cell_map, zones


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict):
        if "data" in obs and isinstance(obs["data"], list):
            obs = obs["data"]
        elif "original_data" in obs and isinstance(obs["original_data"], dict):
            od = obs["original_data"]
            if "data" in od:
                obs = od["data"]

    if not (isinstance(obs, list) and obs and isinstance(obs[0], list)):
        raise ValueError("lits observation must be a 2D region-id grid")

    rows = len(obs)
    cols = len(obs[0])
    grid = [[0 for _ in range(cols)] for _ in range(rows)]
    for r in range(rows):
        if len(obs[r]) != cols:
            raise ValueError("lits region grid must be rectangular")
        for c in range(cols):
            grid[r][c] = int(obs[r][c])
    return grid


def _to_answer_grid(cell_map):
    rows = len(cell_map)
    cols = len(cell_map[0])
    ans = [[None for _ in range(cols)] for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            if cell_map[i][j].fill and cell_map[i][j].dtype in {"S", "T", "I", "L"}:
                ans[i][j] = cell_map[i][j].dtype
    return ans


def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 15000,
    log_level: str = "brief",
):
    region_grid = _normalize_observation(observation)
    rows = len(region_grid)
    cols = len(region_grid[0])

    cell_map = build_cell_map(rows, cols)
    zones = build_zones(region_grid, cell_map)
    add_all_shapes_to_zones(region_grid, zones, cell_map)

    r = solve_core(cell_map, zones, region_grid, deepth=0)
    if r[0] != 1:
        r = solve_core(r[1], r[2], region_grid, deepth=0, max_deepth=10)

    if r[0] != 1:
        return "No Solution"

    return _to_answer_grid(r[1])
