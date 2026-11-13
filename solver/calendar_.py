from __future__ import annotations

from typing import List, Optional, Set, Tuple

Coord = Tuple[int, int]

ROWS = 7
COLS = 7

GRID_CONTENT = [
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", None],
    ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", None],
    ["1", "2", "3", "4", "5", "6", "7"],
    ["8", "9", "10", "11", "12", "13", "14"],
    ["15", "16", "17", "18", "19", "20", "21"],
    ["22", "23", "24", "25", "26", "27", "28"],
    ["29", "30", "31", None, None, None, None],
]

INVALID_CELLS: Set[Coord] = {(0, 6), (1, 6), (6, 3), (6, 4), (6, 5), (6, 6)}

SHAPES = {
    "A": [(0, 1), (1, 1), (0, 0), (1, 0), (2, 0)],
    "B": [(0, 1), (1, 1), (1, 0), (2, 0), (3, 0)],
    "C": [(0, 1), (0, 0), (1, 0), (2, 0), (3, 0)],
    "D": [(0, 0), (0, 1), (1, 1), (2, 1), (2, 2)],
    "E": [(0, 1), (2, 1), (0, 0), (1, 0), (2, 0)],
    "F": [(0, 1), (1, 1), (2, 1), (0, 0), (1, 0), (2, 0)],
    "G": [(1, 1), (0, 0), (1, 0), (2, 0), (3, 0)],
    "H": [(2, 0), (2, 1), (2, 2), (1, 2), (0, 2)],
}


class _Logger:
    def __init__(self, verbose: bool, max_logs: int):
        self.verbose = verbose
        self.max_logs = max_logs
        self.count = 0

    def mark(self, token: str, r: int, c: int, reason: str):
        if not self.verbose:
            return
        if self.count < self.max_logs:
            print(f"{token} ({r}, {c}) | {reason}")
            self.count += 1
        elif self.count == self.max_logs:
            print(f"[verbose] log limit reached ({self.max_logs}), suppressing remaining logs")
            self.count += 1


def _normalize(coords: List[Coord]):
    min_r = min(r for r, _ in coords)
    min_c = min(c for _, c in coords)
    return tuple(sorted((r - min_r, c - min_c) for r, c in coords))


def _rotate(coords: List[Coord]) -> List[Coord]:
    return [(c, -r) for r, c in coords]


def _flip(coords: List[Coord]) -> List[Coord]:
    return [(r, -c) for r, c in coords]


def _variations(base: List[Coord]):
    out = set()
    cur = base[:]
    for _ in range(2):
        for _ in range(4):
            out.add(_normalize(cur))
            cur = _rotate(cur)
        cur = _flip(base)
    return sorted(out)


PIECE_VARIANTS = {name: _variations(coords) for name, coords in SHAPES.items()}


class _CalendarSolver:
    def __init__(self, target_month: Coord, target_day: Coord, verbose: bool, max_logs: int):
        self.target_month = target_month
        self.target_day = target_day
        self.target_set = {target_month, target_day}
        self.logger = _Logger(verbose, max_logs)

        for t in self.target_set:
            if not self._in_bounds(*t):
                raise ValueError(f"target cell out of board: {t}")
            if t in INVALID_CELLS:
                raise ValueError(f"target cannot be invalid cell: {t}")

        self.board = [["." for _ in range(COLS)] for _ in range(ROWS)]
        for r, c in INVALID_CELLS:
            self.board[r][c] = "#"
        for r, c in self.target_set:
            self.board[r][c] = "T"

        self.pieces = sorted(SHAPES.keys())
        self._last_fail = ""

    def _in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < ROWS and 0 <= c < COLS

    def _first_empty(self) -> Optional[Coord]:
        for r in range(ROWS):
            for c in range(COLS):
                if self.board[r][c] == ".":
                    return (r, c)
        return None

    def _can_place(self, cells: List[Coord]) -> bool:
        for r, c in cells:
            if not self._in_bounds(r, c):
                return False
            if self.board[r][c] != ".":
                return False
        return True

    def _search(self, remaining: List[str]) -> bool:
        empty = self._first_empty()
        if empty is None:
            return len(remaining) == 0

        er, ec = empty
        failed = []

        for p in remaining:
            for variant in PIECE_VARIANTS[p]:
                for vr, vc in variant:
                    origin_r = er - vr
                    origin_c = ec - vc
                    cells = [(origin_r + rr, origin_c + cc) for rr, cc in variant]

                    if not self._can_place(cells):
                        continue

                    for r, c in cells:
                        self.board[r][c] = p

                    nxt = [x for x in remaining if x != p]
                    if self._search(nxt):
                        why = "confirmed by recursive consistency"
                        if failed:
                            why += "; alternatives pruned -> " + "; ".join(failed)
                        for r, c in cells:
                            self.logger.mark(p, r, c, why)
                        return True

                    for r, c in cells:
                        self.board[r][c] = "."
                    failed.append(f"piece {p} at anchor ({origin_r},{origin_c}) rejected: {self._last_fail or 'deeper contradiction'}")

        self._last_fail = f"no valid placement for first empty cell ({er},{ec})"
        return False

    def solve(self):
        if not self._search(self.pieces):
            return "No Solution"

        out = [[None for _ in range(COLS)] for _ in range(ROWS)]
        for r in range(ROWS):
            for c in range(COLS):
                if (r, c) in INVALID_CELLS:
                    out[r][c] = -1
                elif (r, c) == self.target_month or (r, c) == self.target_day:
                    out[r][c] = GRID_CONTENT[r][c]
                else:
                    out[r][c] = self.board[r][c]
        return out


def solve(observation, verbose: bool = False, max_logs: int = 2000):
    """
    Input (compatible):
      - {'target': {'month': (r,c), 'day': (r,c)}}
      - {'target_month': 'Aug', 'target_day': '12', ...}
      - {'original_data': {...above...}}
    Output:
      7x7 answer grid using A-H / target labels / -1 for invalid, or 'No Solution'.
    """
    def find_label(label: str):
        s = str(label)
        for r in range(ROWS):
            for c in range(COLS):
                if GRID_CONTENT[r][c] is not None and str(GRID_CONTENT[r][c]) == s:
                    return (r, c)
        raise ValueError(f"label not found on calendar board: {label}")

    obs = observation
    if isinstance(obs, dict) and "original_data" in obs and isinstance(obs["original_data"], dict):
        obs = obs["original_data"]

    if not isinstance(obs, dict):
        raise ValueError("unsupported observation format for calendar")

    if "target" in obs:
        target = obs["target"]
        month = tuple(target["month"])
        day = tuple(target["day"])
        month_coord = (int(month[0]), int(month[1]))
        day_coord = (int(day[0]), int(day[1]))
    elif "target_month" in obs and "target_day" in obs:
        month_coord = find_label(obs["target_month"])
        day_coord = find_label(obs["target_day"])
    else:
        raise ValueError("calendar observation must provide 'target' or ('target_month','target_day')")

    return _CalendarSolver(month_coord, day_coord, verbose, max_logs).solve()
