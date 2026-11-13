from __future__ import annotations

import copy
from typing import Dict, List, Optional, Sequence, Tuple

UNKNOWN = 0
BLACK = 1
WHITE = 2

Pos = Tuple[int, int]
Board = List[List[int]]
Grid = List[List[str]]


def _copy_board(board: Board) -> Board:
    return [row[:] for row in board]


def _count_cells(board: Board, value: int) -> int:
    return sum(1 for row in board for cell in row if cell == value)


def _count_filled(board: Board) -> int:
    return sum(1 for row in board for cell in row if cell > 0)


def _token(value: int) -> str:
    return "B" if value == BLACK else "W"


def _to_num(v) -> int:
    if v is None:
        return UNKNOWN
    s = str(v).upper()
    if s == "B":
        return BLACK
    if s == "W":
        return WHITE
    return UNKNOWN


def _to_char(v: int) -> str:
    return "B" if v == BLACK else "W"


def _normalize_observation(observation) -> Dict[str, object]:
    if isinstance(observation, dict) and observation and all(isinstance(k, tuple) and len(k) == 2 for k in observation):
        clues = {(int(r), int(c)): _to_num(v) for (r, c), v in observation.items()}
        if not clues:
            raise ValueError("empty yinyang clues")
        n = max(max(r for r, _ in clues), max(c for _, c in clues)) + 1
        board = [[UNKNOWN for _ in range(n)] for _ in range(n)]
        for (r, c), v in clues.items():
            if v not in (BLACK, WHITE):
                raise ValueError("invalid yinyang clue value")
            board[r][c] = v
        return {"n": n, "board": board}

    data = observation
    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]
        elif isinstance(data.get("original_data"), dict) and "data" in data["original_data"]:
            data = data["original_data"]["data"]

    if not (isinstance(data, list) and data and isinstance(data[0], list)):
        raise ValueError("unsupported yinyang observation")

    n = len(data)
    board: Board = []
    for row in data:
        if len(row) != n:
            raise ValueError("yinyang board must be square")
        board.append([_to_num(v) for v in row])

    return {"n": n, "board": board}


class _YinYangSolver:
    def __init__(self, board: Board):
        self.board = _copy_board(board)
        self.n = len(board)
        self._last_fail = ""

    def _msg(self, brief: str, full: str) -> str:
        return brief

    def _inb(self, i: int, j: int) -> bool:
        return 0 <= i < self.n and 0 <= j < self.n

    def _neighbors(self, i: int, j: int) -> List[Pos]:
        out: List[Pos] = []
        for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
            if self._inb(a, b):
                out.append((a, b))
        return out

    def _snapshot(self, board: Board):
        return _copy_board(board), self._last_fail

    def _restore(self, snap):
        board, last_fail = snap
        self._last_fail = last_fail
        return board

    def _set(self, board: Board, i: int, j: int, value: int, why: str) -> bool:
        cur = board[i][j]
        if cur == value:
            return True
        if cur != UNKNOWN:
            self._last_fail = f"conflict at ({i},{j})"
            return False
        board[i][j] = value
        return True

    def _dfs_component(self, board: Board, i: int, j: int, visit: List[List[int]], parent: Pos):
        visit[i][j] = 1
        cycle_flags: List[int] = []
        child_open_flags: List[int] = []
        open_to_unknown = 0
        node_count = 1

        for a, b in self._neighbors(i, j):
            if board[i][j] == board[a][b]:
                if visit[a][b]:
                    if parent != (a, b):
                        return 1, 1, 0
                else:
                    v, o, num = self._dfs_component(board, a, b, visit, (i, j))
                    cycle_flags.append(v)
                    child_open_flags.append(o)
                    node_count += num
            if board[a][b] == UNKNOWN:
                open_to_unknown = 1

        if any(child_open_flags):
            open_to_unknown = 1

        return int(any(cycle_flags)), open_to_unknown, node_count

    def _detect_quan(self, board: Board):
        visit = [[0] * self.n for _ in range(self.n)]
        tree_num = []

        for i in range(self.n):
            for j in range(self.n):
                if board[i][j] > 0 and visit[i][j] == 0:
                    tree_num.append((i, j))
                    v, o, num = self._dfs_component(board, i, j, visit, (-1, -1))
                    color_count = _count_cells(board, board[i][j])
                    if v or (num < color_count and not o):
                        self._last_fail = f"closed cycle/region at ({i},{j})"
                        return True, (i, j)

        return False, tree_num

    def _valid(self, board: Optional[Board]) -> int:
        if board is None:
            self._last_fail = "board is None"
            return 0

        unknown_count = _count_cells(board, UNKNOWN)

        for i in range(self.n):
            for j in range(self.n):
                if i > 0 and j > 0:
                    z = [board[i - 1][j - 1], board[i - 1][j], board[i][j - 1], board[i][j]]
                    if z[0] == z[1] == z[2] == z[3] and z[0] > 0:
                        self._last_fail = f"monochrome 2x2 at ({i-1},{j-1})"
                        return 0
                    if z[0] == z[3] and z[1] == z[2] and z[0] > 0 and z[1] > 0 and z[0] != z[1]:
                        self._last_fail = f"checkerboard 2x2 at ({i-1},{j-1})"
                        return 0

                if board[i][j] > 0:
                    if not any(board[a][b] in (board[i][j], UNKNOWN) for a, b in self._neighbors(i, j)):
                        self._last_fail = f"isolated cell at ({i},{j})"
                        return 0

        has_quan, tree_num = self._detect_quan(board)
        if has_quan:
            return 0

        if unknown_count == 0:
            if len(tree_num) == 2:
                return 1
            self._last_fail = f"final component count is {len(tree_num)}"
            return 0

        return -1

    def _rule_neighbor_agree(self, board: Board, change: List[Pos]) -> Tuple[bool, List[Pos]]:
        changed: List[Pos] = []
        targets: List[Pos] = []
        if not change:
            for i in range(self.n):
                for j in range(self.n):
                    targets.append((i, j))
        else:
            s = set()
            for i, j in change:
                for p in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                    if self._inb(p[0], p[1]):
                        s.add(p)
            targets = list(s)

        for i, j in targets:
            if board[i][j] != UNKNOWN:
                continue
            z = [board[a][b] for a, b in self._neighbors(i, j)]
            if not z or z[0] == UNKNOWN:
                continue
            if all(v == z[0] for v in z):
                why = self._msg(
                    "neighbor-consistency",
                    f"All neighbors of ({i},{j}) are {_token(z[0])}; assigning ({i},{j})={_token(z[0])} keeps local connectivity.",
                )
                if not self._set(board, i, j, z[0], why):
                    return False, changed
                changed.append((i, j))
        return True, changed

    def _rule_2x2(self, board: Board, change: List[Pos]) -> Tuple[bool, List[Pos]]:
        changed: List[Pos] = []
        targets: List[Pos] = []
        if not change:
            for i in range(self.n):
                for j in range(self.n):
                    targets.append((i, j))
        else:
            s = set()
            for i, j in change:
                s.update([(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)])
            targets = [p for p in s if self._inb(p[0], p[1])]

        for i, j in targets:
            if i == 0 or j == 0:
                continue
            idx = [(i - 1, j - 1), (i - 1, j), (i, j - 1), (i, j)]
            z = [board[a][b] for a, b in idx]
            for target in range(4):
                if z[target] > 0:
                    continue
                z1 = z[(target + 1) % 4]
                z2 = z[(target + 2) % 4]
                z3 = z[(target + 3) % 4]
                v = 0
                if z2 > 0 and ((target % 2 == 0 and z1 == z2 and z3 > 0) or (target % 2 == 1 and z2 == z3 and z1 > 0)):
                    v = (3 - z3) if (target % 2 == 0) else (3 - z1)
                if v > 0 and board[idx[target][0]][idx[target][1]] == UNKNOWN:
                    a, b = idx[target]
                    why = self._msg(
                        "2x2-forcing",
                        f"In 2x2 block with corners {idx}, placing {_token(v)} at ({a},{b}) avoids forbidden 2x2 pattern.",
                    )
                    if not self._set(board, a, b, v, why):
                        return False, changed
                    changed.append((a, b))
        return True, changed

    def _rule_2x3_3x2(self, board: Board, change: List[Pos]) -> Tuple[bool, List[Pos]]:
        changed: List[Pos] = []

        targets23: List[Pos] = []
        targets32: List[Pos] = []
        if not change:
            for i in range(self.n):
                for j in range(self.n):
                    targets23.append((i, j))
                    targets32.append((i, j))
        else:
            s23 = set()
            s32 = set()
            for i, j in change:
                s23.update([(i, j), (i, j + 1), (i, j + 2), (i + 1, j), (i + 1, j + 1), (i + 1, j + 2)])
                s32.update([(i, j), (i, j + 1), (i + 1, j), (i + 1, j + 1), (i + 2, j), (i + 2, j + 1)])
            targets23 = [p for p in s23 if self._inb(p[0], p[1])]
            targets32 = [p for p in s32 if self._inb(p[0], p[1])]

        for i, j in targets23:
            if i < 1 or j < 2:
                continue
            idx = [(i - 1, j - 2), (i - 1, j - 1), (i - 1, j), (i, j - 2), (i, j - 1), (i, j)]
            z = [board[a][b] for a, b in idx]
            vec = [0, 2, 3, 5]
            for target in range(4):
                zt = z[vec[(target + 0) % 4]]
                z1 = z[vec[(target + 1) % 4]]
                z2 = z[vec[(target + 2) % 4]]
                z3 = z[vec[(target + 3) % 4]]
                if zt > 0 and z1 > 0 and z1 == z2 == z3 and z1 != zt:
                    pos = vec[target] + 1 if vec[target] % 3 == 0 else vec[target] - 1
                    a, b = idx[pos]
                    if board[a][b] == UNKNOWN:
                        why = self._msg(
                            "2x3-pattern",
                            f"2x3 pattern around {idx} forces ({a},{b})={_token(zt)} to avoid separating color regions.",
                        )
                        if not self._set(board, a, b, zt, why):
                            return False, changed
                        changed.append((a, b))

        for i, j in targets32:
            if i < 2 or j < 1:
                continue
            idx = [(i - 2, j - 1), (i - 2, j), (i - 1, j - 1), (i - 1, j), (i, j - 1), (i, j)]
            z = [board[a][b] for a, b in idx]
            vec = [0, 1, 4, 5]
            for target in range(4):
                zt = z[vec[(target + 0) % 4]]
                z1 = z[vec[(target + 1) % 4]]
                z2 = z[vec[(target + 2) % 4]]
                z3 = z[vec[(target + 3) % 4]]
                if zt > 0 and z1 > 0 and z1 == z2 == z3 and z1 != zt:
                    pos = vec[target] + 2 if vec[target] // 2 == 0 else vec[target] - 2
                    a, b = idx[pos]
                    if board[a][b] == UNKNOWN:
                        why = self._msg(
                            "3x2-pattern",
                            f"3x2 pattern around {idx} forces ({a},{b})={_token(zt)} by local region continuity.",
                        )
                        if not self._set(board, a, b, zt, why):
                            return False, changed
                        changed.append((a, b))

        return True, changed

    def _rule_border_arc(self, board: Board, color: int) -> Tuple[bool, List[Pos]]:
        changed: List[Pos] = []
        edge = (
            [(0, i) for i in range(self.n - 1)]
            + [(i, self.n - 1) for i in range(self.n - 1)]
            + [(self.n - 1, self.n - 1 - i) for i in range(self.n - 1)]
            + [(self.n - 1 - i, 0) for i in range(self.n - 1)]
        )
        m = 4 * self.n - 4
        opp = WHITE if color == BLACK else BLACK

        for idx, (i, j) in enumerate(edge):
            if board[i][j] != color:
                continue
            idx2 = (idx + 1) % m
            idx3 = (idx - 1) % m
            while idx2 != idx and board[edge[idx2][0]][edge[idx2][1]] != opp:
                idx2 = (idx2 + 1) % m
            while idx3 != idx and board[edge[idx3][0]][edge[idx3][1]] != opp:
                idx3 = (idx3 - 1 + m) % m

            if idx2 != idx3:
                idx4 = (idx2 + 1) % m
                while idx4 != idx3:
                    a, b = edge[idx4]
                    if board[a][b] == color:
                        self._last_fail = f"border arc contradiction for {_token(color)}"
                        return False, changed
                    if board[a][b] == UNKNOWN:
                        why = self._msg(
                            "border-arc",
                            f"On border ring, {_token(color)} at ({i},{j}) is separated by opposite color, so ({a},{b}) must be {_token(opp)}.",
                        )
                        if not self._set(board, a, b, opp, why):
                            return False, changed
                        changed.append((a, b))
                    idx4 = (idx4 + 1) % m
            break

        return True, changed

    def _inference(self, board: Board, change: List[Pos]) -> int:
        pre = 0
        local_change = list(change)

        while _count_filled(board) > pre:
            pre = _count_filled(board)
            merged_change: List[Pos] = []

            ok, ch = self._rule_neighbor_agree(board, local_change)
            if not ok:
                return 0
            merged_change.extend(ch)

            ok, ch = self._rule_2x2(board, local_change)
            if not ok:
                return 0
            merged_change.extend(ch)

            ok, ch = self._rule_2x3_3x2(board, local_change)
            if not ok:
                return 0
            merged_change.extend(ch)

            ok, ch = self._rule_border_arc(board, BLACK)
            if not ok:
                return 0
            merged_change.extend(ch)

            ok, ch = self._rule_border_arc(board, WHITE)
            if not ok:
                return 0
            merged_change.extend(ch)

            local_change = merged_change

        return self._valid(board)

    def _pick_cell(self, board: Board) -> Optional[Pos]:
        scores = []
        for i in range(self.n):
            for j in range(self.n):
                if board[i][j] != UNKNOWN:
                    continue
                known_neighbor = sum(1 for a, b in self._neighbors(i, j) if board[a][b] > 0)
                scores.append((i, j, -known_neighbor))
        if not scores:
            return None
        i, j, _ = sorted(scores, key=lambda t: t[2])[0]
        return i, j

    def _search(self, board: Board, depth: int = 0) -> Optional[Board]:
        pos = self._pick_cell(board)
        if pos is None:
            return board if self._valid(board) == 1 else None

        i, j = pos
        for v in (BLACK, WHITE):
            trial = _copy_board(board)
            why = self._msg(
                "branch",
                f"Depth {depth}: branch try ({i},{j})={_token(v)} as a short-depth hypothesis.",
            )
            if not self._set(trial, i, j, v, why):
                continue
            ret = self._solve(trial, depth=depth, change=[(i, j)])
            if ret is not None:
                return ret

        self._last_fail = f"all branches failed at ({i},{j})"
        return None

    def _solve(self, board: Board, depth: int = 0, change: Optional[List[Pos]] = None) -> Optional[Board]:
        if change is None:
            change = []

        pre = 0
        while _count_filled(board) > pre:
            pre = _count_filled(board)
            val = self._inference(board, change)
            if val == 0:
                return None
            if val == 1:
                return board

            forced = False
            for i in range(self.n):
                if forced:
                    break
                for j in range(self.n):
                    if board[i][j] > 0:
                        continue
                    for v in (BLACK, WHITE):
                        trial = _copy_board(board)
                        trial[i][j] = v
                        snap_fail = self._last_fail
                        val_try = self._inference(trial, [(i, j)])
                        fail_reason = self._last_fail
                        self._last_fail = snap_fail
                        if val_try == 1:
                            why = self._msg(
                                "trial-complete",
                                f"Trying ({i},{j})={_token(v)} immediately completes a valid board.",
                            )
                            if self._set(board, i, j, v, why):
                                return _copy_board(trial)
                        if val_try == 0:
                            opposite = 3 - v
                            why = self._msg(
                                "contradiction-force",
                                f"Assume ({i},{j})={_token(v)} leads to contradiction ({fail_reason}); therefore ({i},{j})={_token(opposite)}.",
                            )
                            if not self._set(board, i, j, opposite, why):
                                return None
                            change = [(i, j)]
                            forced = True
                            break
                    if forced:
                        break

        if self._valid(board) == 1:
            return board

        return self._search(board, depth=depth + 1)

    def solve(self) -> Optional[Board]:
        self._last_fail = ""
        ans = self._solve(_copy_board(self.board))
        return ans


def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 8000,
    log_level: str = "brief",
):
    normalized = _normalize_observation(observation)
    board = _copy_board(normalized["board"])

    solver = _YinYangSolver(board)
    ans = solver.solve()
    if ans is None:
        return "No Solution"
    return [[_to_char(v) for v in row] for row in ans]


