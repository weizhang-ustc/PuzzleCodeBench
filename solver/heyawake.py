from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Tuple

Pos = Tuple[int, int]
Grid = List[List[int]]


class _HeyawakeSolver:
    DIR4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

    def __init__(self, region: List[List[int]], clue: List[List[Optional[int]]]):
        self.n = len(region)
        self.region = [row[:] for row in region]
        self.clue = [row[:] for row in clue]
        self.state: Grid = [[-1 for _ in range(self.n)] for _ in range(self.n)]
        self._dead = set()

        self.cells = [(r, c) for r in range(self.n) for c in range(self.n)]
        self.region_cells: Dict[int, List[Pos]] = {}
        for r, c in self.cells:
            self.region_cells.setdefault(self.region[r][c], []).append((r, c))

        self.region_clue: Dict[int, int] = {}
        for r in range(self.n):
            for c in range(self.n):
                v = self.clue[r][c]
                if v is None:
                    continue
                rid = self.region[r][c]
                iv = int(v)
                if rid in self.region_clue and self.region_clue[rid] != iv:
                    raise ValueError(f"inconsistent clues in region {rid}")
                self.region_clue[rid] = iv

        self._all_non_adj_masks = self._build_non_adj_masks(self.n)
        self._row_base_masks = [self._base_line_masks([self.region[r][c] for c in range(self.n)]) for r in range(self.n)]
        self._col_base_masks = [self._base_line_masks([self.region[r][c] for r in range(self.n)]) for c in range(self.n)]
        self._row_live_masks = [masks[:] for masks in self._row_base_masks]
        self._col_live_masks = [masks[:] for masks in self._col_base_masks]
        self._region_cell_support: Dict[Pos, Tuple[int, int]] = {}
        self._region_live_patterns: Dict[int, Tuple[List[Pos], List[Pos], List[int]]] = {}

    def _inb(self, r: int, c: int) -> bool:
        return 0 <= r < self.n and 0 <= c < self.n

    def _snapshot(self):
        return [row[:] for row in self.state]

    def _restore(self, snap):
        self.state = snap

    def _state_key(self):
        return tuple(tuple(row) for row in self.state)

    @staticmethod
    def _build_non_adj_masks(n: int) -> List[int]:
        out = []
        for mask in range(1 << n):
            if mask & (mask << 1):
                continue
            out.append(mask)
        return out

    @staticmethod
    def _line_rule_mask_ok(mask: int, regs: List[int]) -> bool:
        n = len(regs)
        i = 0
        while i < n:
            if (mask >> i) & 1:
                i += 1
                continue
            seen = 0
            last = None
            while i < n and (((mask >> i) & 1) == 0):
                rid = regs[i]
                if rid != last:
                    seen += 1
                    if seen > 2:
                        return False
                    last = rid
                i += 1
        return True

    def _base_line_masks(self, regs: List[int]) -> List[int]:
        return [mask for mask in self._all_non_adj_masks if self._line_rule_mask_ok(mask, regs)]

    def _set(self, r: int, c: int, v: int) -> bool:
        cur = self.state[r][c]
        if cur == v:
            return True
        if cur != -1:
            return False
        self.state[r][c] = v
        return True

    def _adjacent_black_ok(self) -> bool:
        for r in range(self.n):
            for c in range(self.n):
                if self.state[r][c] != 1:
                    continue
                for dr, dc in ((1, 0), (0, 1)):
                    rr, cc = r + dr, c + dc
                    if self._inb(rr, cc) and self.state[rr][cc] == 1:
                        return False
        return True

    def _max_independent_grid_cells(self, cells: List[Pos]) -> int:
        if not cells:
            return 0

        cell_set = set(cells)
        left = []
        right = []
        for rc in cells:
            if (rc[0] + rc[1]) & 1:
                left.append(rc)
            else:
                right.append(rc)

        right_idx = {rc: i for i, rc in enumerate(right)}
        adj = [[] for _ in range(len(left))]
        for i, (r, c) in enumerate(left):
            for dr, dc in self.DIR4:
                rr, cc = r + dr, c + dc
                nb = (rr, cc)
                if nb in cell_set and nb in right_idx:
                    adj[i].append(right_idx[nb])

        match_r = [-1] * len(right)

        def dfs(u: int, seen: List[bool]) -> bool:
            for v in adj[u]:
                if seen[v]:
                    continue
                seen[v] = True
                if match_r[v] == -1 or dfs(match_r[v], seen):
                    match_r[v] = u
                    return True
            return False

        match = 0
        for u in range(len(left)):
            seen = [False] * len(right)
            if dfs(u, seen):
                match += 1

        return len(cells) - match

    def _region_bounds_ok(self) -> bool:
        for rid, k in self.region_clue.items():
            cells = self.region_cells[rid]
            b = sum(1 for r, c in cells if self.state[r][c] == 1)
            if b > k:
                return False

            candidates = []
            for r, c in cells:
                if self.state[r][c] != -1:
                    continue
                blocked = False
                for dr, dc in self.DIR4:
                    rr, cc = r + dr, c + dc
                    if self._inb(rr, cc) and self.state[rr][cc] == 1:
                        blocked = True
                        break
                if not blocked:
                    candidates.append((r, c))

            max_additional = self._max_independent_grid_cells(candidates)
            if b + max_additional < k:
                return False
        return True

    def _white_connectivity_feasible(self) -> bool:
        fixed = [(r, c) for r, c in self.cells if self.state[r][c] == 0]
        if not fixed:
            return True
        start = fixed[0]
        seen = {start}
        q = deque([start])
        while q:
            r, c = q.popleft()
            for dr, dc in self.DIR4:
                rr, cc = r + dr, c + dc
                if not self._inb(rr, cc):
                    continue
                if self.state[rr][cc] == 1 or (rr, cc) in seen:
                    continue
                seen.add((rr, cc))
                q.append((rr, cc))

        for rc in fixed:
            if rc not in seen:
                return False
        return True

    def _propagate_region(self):
        changed = False
        for rid, k in self.region_clue.items():
            cells = self.region_cells[rid]
            black = [(r, c) for r, c in cells if self.state[r][c] == 1]
            unk = [(r, c) for r, c in cells if self.state[r][c] == -1]
            if len(black) == k:
                for r, c in unk:
                    if not self._set(r, c, 0):
                        return None
                    changed = True
            elif len(black) + len(unk) == k:
                for r, c in unk:
                    if not self._set(r, c, 1):
                        return None
                    changed = True
        return changed

    def _propagate_adj(self):
        changed = False
        for r, c in self.cells:
            if self.state[r][c] != 1:
                continue
            for dr, dc in self.DIR4:
                rr, cc = r + dr, c + dc
                if self._inb(rr, cc) and self.state[rr][cc] == -1:
                    if not self._set(rr, cc, 0):
                        return None
                    changed = True
        return changed

    def _propagate_region_patterns(self):
        changed = False
        max_region_cells = 16
        max_patterns = 20000
        branch_store_limit = 128
        region_support: Dict[Pos, Tuple[int, int]] = {}
        region_patterns: Dict[int, Tuple[List[Pos], List[Pos], List[int]]] = {}

        for rid, k in self.region_clue.items():
            cells = self.region_cells[rid]
            if len(cells) > max_region_cells:
                continue

            fixed_black = []
            unknown = []
            for r, c in cells:
                v = self.state[r][c]
                if v == 1:
                    fixed_black.append((r, c))
                elif v == -1:
                    unknown.append((r, c))

            need = k - len(fixed_black)
            if need < 0:
                return None
            if need == 0:
                for r, c in unknown:
                    region_support[(r, c)] = (0, 1)
                continue

            can_black = []
            blocked_unknown = []
            for r, c in unknown:
                blocked = False
                for dr, dc in self.DIR4:
                    rr, cc = r + dr, c + dc
                    if self._inb(rr, cc) and self.state[rr][cc] == 1:
                        blocked = True
                        break
                if blocked:
                    blocked_unknown.append((r, c))
                else:
                    can_black.append((r, c))

            if need > len(can_black):
                return None

            idx = {rc: i for i, rc in enumerate(can_black)}
            adj_bits = [0] * len(can_black)
            for i, (r, c) in enumerate(can_black):
                bits = 0
                for dr, dc in self.DIR4:
                    nb = (r + dr, c + dc)
                    j = idx.get(nb)
                    if j is not None:
                        bits |= 1 << j
                adj_bits[i] = bits

            pattern_count = 0
            pick_count = [0] * len(can_black)
            stored_patterns: List[int] = []
            store_enabled = True

            def dfs(i: int, picked: int, banned: int, mask: int):
                nonlocal pattern_count, store_enabled
                if pattern_count > max_patterns:
                    return
                rem = len(can_black) - i
                if picked > need or picked + rem < need:
                    return
                if i == len(can_black):
                    if picked == need:
                        pattern_count += 1
                        if store_enabled:
                            stored_patterns.append(mask)
                            if len(stored_patterns) > branch_store_limit:
                                store_enabled = False
                                stored_patterns.clear()
                        m = mask
                        bit = 0
                        while m:
                            if m & 1:
                                pick_count[bit] += 1
                            m >>= 1
                            bit += 1
                    return

                dfs(i + 1, picked, banned, mask)
                if ((banned >> i) & 1) == 0:
                    dfs(i + 1, picked + 1, banned | (1 << i) | adj_bits[i], mask | (1 << i))

            dfs(0, 0, 0, 0)

            if pattern_count == 0:
                return None
            if pattern_count > max_patterns:
                continue

            for (r, c) in blocked_unknown:
                region_support[(r, c)] = (0, pattern_count)
                if not self._set(r, c, 0):
                    return None
                changed = True

            for i, (r, c) in enumerate(can_black):
                region_support[(r, c)] = (pick_count[i], pattern_count - pick_count[i])
                if self.state[r][c] != -1:
                    continue
                if pick_count[i] == 0:
                    if not self._set(r, c, 0):
                        return None
                    changed = True
                elif pick_count[i] == pattern_count:
                    if not self._set(r, c, 1):
                        return None
                    changed = True

            if store_enabled and len(stored_patterns) >= 2:
                region_patterns[rid] = (can_black, blocked_unknown, stored_patterns)

        self._region_cell_support = region_support
        self._region_live_patterns = region_patterns
        return changed

    def _propagate_white_cutpoints(self):
        terminals = [(r, c) for r, c in self.cells if self.state[r][c] == 0]
        if len(terminals) <= 1:
            return False

        root = terminals[0]
        passable = {(r, c) for r, c in self.cells if self.state[r][c] != 1}

        changed = False
        for r, c in self.cells:
            if self.state[r][c] != -1:
                continue

            deg = 0
            for dr, dc in self.DIR4:
                rr, cc = r + dr, c + dc
                if (rr, cc) in passable:
                    deg += 1
            if deg <= 1:
                continue

            if root == (r, c):
                continue

            seen = {root}
            q = deque([root])
            while q:
                rr, cc = q.popleft()
                for dr, dc in self.DIR4:
                    nr, nc = rr + dr, cc + dc
                    nxt = (nr, nc)
                    if nxt == (r, c) or nxt not in passable or nxt in seen:
                        continue
                    seen.add(nxt)
                    q.append(nxt)

            for tr in terminals:
                if tr != (r, c) and tr not in seen:
                    if not self._set(r, c, 0):
                        return None
                    changed = True
                    break

        return changed

    def _propagate_line_patterns(self):
        changed = False

        row_domains = []
        for r in range(self.n):
            req_black = 0
            req_white = 0
            for c in range(self.n):
                v = self.state[r][c]
                if v == 1:
                    req_black |= 1 << c
                elif v == 0:
                    req_white |= 1 << c
            masks = [m for m in self._row_base_masks[r] if (m & req_white) == 0 and (m & req_black) == req_black]
            if not masks:
                return None
            row_domains.append(masks)

        col_domains = []
        for c in range(self.n):
            req_black = 0
            req_white = 0
            for r in range(self.n):
                v = self.state[r][c]
                if v == 1:
                    req_black |= 1 << r
                elif v == 0:
                    req_white |= 1 << r
            masks = [m for m in self._col_base_masks[c] if (m & req_white) == 0 and (m & req_black) == req_black]
            if not masks:
                return None
            col_domains.append(masks)

        while True:
            any_domain_change = False

            col_can1 = [[False] * self.n for _ in range(self.n)]
            for c in range(self.n):
                for r in range(self.n):
                    bit = 1 << r
                    col_can1[r][c] = any((m & bit) != 0 for m in col_domains[c])

            for r in range(self.n):
                filtered = []
                for m in row_domains[r]:
                    ok = True
                    for c in range(self.n):
                        bit_is_black = ((m >> c) & 1) == 1
                        if bit_is_black and not col_can1[r][c]:
                            ok = False
                            break
                        if (not bit_is_black) and col_can1[r][c] and all(((cm >> r) & 1) == 1 for cm in col_domains[c]):
                            ok = False
                            break
                    if ok:
                        filtered.append(m)
                if not filtered:
                    return None
                if len(filtered) != len(row_domains[r]):
                    row_domains[r] = filtered
                    any_domain_change = True

            row_can1 = [[False] * self.n for _ in range(self.n)]
            for r in range(self.n):
                for c in range(self.n):
                    bit = 1 << c
                    row_can1[r][c] = any((m & bit) != 0 for m in row_domains[r])

            for c in range(self.n):
                filtered = []
                for m in col_domains[c]:
                    ok = True
                    for r in range(self.n):
                        bit_is_black = ((m >> r) & 1) == 1
                        if bit_is_black and not row_can1[r][c]:
                            ok = False
                            break
                        if (not bit_is_black) and row_can1[r][c] and all(((rm >> c) & 1) == 1 for rm in row_domains[r]):
                            ok = False
                            break
                    if ok:
                        filtered.append(m)
                if not filtered:
                    return None
                if len(filtered) != len(col_domains[c]):
                    col_domains[c] = filtered
                    any_domain_change = True

            if not any_domain_change:
                break

        self._row_live_masks = row_domains
        self._col_live_masks = col_domains

        for r in range(self.n):
            all_black_bits = (1 << self.n) - 1
            all_white_bits = (1 << self.n) - 1
            for m in row_domains[r]:
                all_black_bits &= m
                all_white_bits &= ~m

            for c in range(self.n):
                if self.state[r][c] != -1:
                    continue
                bit = 1 << c
                if all_black_bits & bit:
                    if not self._set(r, c, 1):
                        return None
                    changed = True
                elif all_white_bits & bit:
                    if not self._set(r, c, 0):
                        return None
                    changed = True

        for c in range(self.n):
            all_black_bits = (1 << self.n) - 1
            all_white_bits = (1 << self.n) - 1
            for m in col_domains[c]:
                all_black_bits &= m
                all_white_bits &= ~m

            for r in range(self.n):
                if self.state[r][c] != -1:
                    continue
                bit = 1 << r
                if all_black_bits & bit:
                    if not self._set(r, c, 1):
                        return None
                    changed = True
                elif all_white_bits & bit:
                    if not self._set(r, c, 0):
                        return None
                    changed = True

        return changed

    def _propagate(self):
        while True:
            if not self._adjacent_black_ok() or not self._region_bounds_ok():
                return False
            if not self._white_connectivity_feasible():
                return False

            changed = False

            p1 = self._propagate_region()
            if p1 is None:
                return False
            changed = changed or bool(p1)

            p2 = self._propagate_adj()
            if p2 is None:
                return False
            changed = changed or bool(p2)

            p2b = self._propagate_region_patterns()
            if p2b is None:
                return False
            changed = changed or bool(p2b)

            p3 = self._propagate_line_patterns()
            if p3 is None:
                return False
            changed = changed or bool(p3)

            if not changed:
                p4 = self._propagate_white_cutpoints()
                if p4 is None:
                    return False
                changed = changed or bool(p4)

            if not changed:
                break
        return True

    def _final_ok(self) -> bool:
        if any(self.state[r][c] == -1 for r, c in self.cells):
            return False

        if not self._adjacent_black_ok() or not self._region_bounds_ok():
            return False

        for rid, k in self.region_clue.items():
            b = sum(1 for r, c in self.region_cells[rid] if self.state[r][c] == 1)
            if b != k:
                return False

        for r in range(self.n):
            c = 0
            while c < self.n:
                if self.state[r][c] == 1:
                    c += 1
                    continue
                regs = []
                while c < self.n and self.state[r][c] != 1:
                    rid = self.region[r][c]
                    if not regs or regs[-1] != rid:
                        regs.append(rid)
                    c += 1
                if len(regs) > 2:
                    return False

        for c in range(self.n):
            r = 0
            while r < self.n:
                if self.state[r][c] == 1:
                    r += 1
                    continue
                regs = []
                while r < self.n and self.state[r][c] != 1:
                    rid = self.region[r][c]
                    if not regs or regs[-1] != rid:
                        regs.append(rid)
                    r += 1
                if len(regs) > 2:
                    return False

        whites = [(r, c) for r, c in self.cells if self.state[r][c] == 0]
        if not whites:
            return False
        seen = {whites[0]}
        q = deque([whites[0]])
        while q:
            r, c = q.popleft()
            for dr, dc in self.DIR4:
                rr, cc = r + dr, c + dc
                if self._inb(rr, cc) and self.state[rr][cc] == 0 and (rr, cc) not in seen:
                    seen.add((rr, cc))
                    q.append((rr, cc))
        if len(seen) != len(whites):
            return False
        return True

    def _cell_support(self, r: int, c: int) -> Tuple[int, int]:
        row_black = 0
        row_white = 0
        bit_c = 1 << c
        for m in self._row_live_masks[r]:
            if m & bit_c:
                row_black += 1
            else:
                row_white += 1

        col_black = 0
        col_white = 0
        bit_r = 1 << r
        for m in self._col_live_masks[c]:
            if m & bit_r:
                col_black += 1
            else:
                col_white += 1

        black_support = row_black * col_black
        white_support = row_white * col_white

        reg_support = self._region_cell_support.get((r, c))
        if reg_support is not None:
            rb, rw = reg_support
            black_support *= max(1, rb)
            white_support *= max(1, rw)
            if rb == 0:
                black_support = 0
            if rw == 0:
                white_support = 0

        return black_support, white_support

    def _pick_cell(self):
        best = None
        best_key = None
        for r, c in self.cells:
            if self.state[r][c] != -1:
                continue

            black_support, white_support = self._cell_support(r, c)
            domain = (1 if black_support > 0 else 0) + (1 if white_support > 0 else 0)
            min_support = min(black_support if black_support > 0 else 10 ** 12, white_support if white_support > 0 else 10 ** 12)
            total_support = black_support + white_support

            rid = self.region[r][c]
            clue_bias = 0 if rid in self.region_clue else 1
            deg = sum(1 for dr, dc in self.DIR4 if self._inb(r + dr, c + dc))
            key = (domain, min_support, total_support, clue_bias, -deg, r, c)
            if best_key is None or key < best_key:
                best_key = key
                best = (r, c)
        return best

    def _value_order(self, r: int, c: int) -> List[int]:
        black_support, white_support = self._cell_support(r, c)
        cand = []
        if black_support > 0:
            cand.append((black_support, 0, 1))
        if white_support > 0:
            cand.append((white_support, 1, 0))
        cand.sort()
        return [v for _, _, v in cand]

    def _pick_line_branch(self):
        best = None
        best_size = None
        limit = 10 if self.n >= 18 else 6

        for r, dom in enumerate(self._row_live_masks):
            d = len(dom)
            if 1 < d <= limit and (best_size is None or d < best_size):
                best_size = d
                best = ("row", r, dom)

        for c, dom in enumerate(self._col_live_masks):
            d = len(dom)
            if 1 < d <= limit and (best_size is None or d < best_size):
                best_size = d
                best = ("col", c, dom)

        return best

    def _pick_region_branch(self):
        best = None
        best_size = None
        for rid, (can_black, blocked_unknown, patterns) in self._region_live_patterns.items():
            sz = len(patterns)
            if sz <= 1:
                continue
            if best_size is None or sz < best_size:
                best_size = sz
                best = (rid, can_black, blocked_unknown, patterns)
        return best

    def _apply_region_pattern(self, can_black: List[Pos], blocked_unknown: List[Pos], mask: int) -> bool:
        for r, c in blocked_unknown:
            if self.state[r][c] == -1:
                if not self._set(r, c, 0):
                    return False
        for i, (r, c) in enumerate(can_black):
            if self.state[r][c] != -1:
                continue
            v = 1 if ((mask >> i) & 1) else 0
            if not self._set(r, c, v):
                return False
        return True

    def _apply_row_mask(self, r: int, mask: int) -> bool:
        for c in range(self.n):
            v = 1 if ((mask >> c) & 1) else 0
            if not self._set(r, c, v):
                return False
        return True

    def _apply_col_mask(self, c: int, mask: int) -> bool:
        for r in range(self.n):
            v = 1 if ((mask >> r) & 1) else 0
            if not self._set(r, c, v):
                return False
        return True

    def _search(self):
        key = self._state_key()
        if key in self._dead:
            return None

        if not self._propagate():
            self._dead.add(key)
            return None
        if self._final_ok():
            return [row[:] for row in self.state]

        region_choice = self._pick_region_branch()
        if region_choice is not None:
            _, can_black, blocked_unknown, patterns = region_choice
            for mask in patterns:
                snap = self._snapshot()
                if self._apply_region_pattern(can_black, blocked_unknown, mask):
                    ans = self._search()
                    if ans is not None:
                        return ans
                self._restore(snap)
            self._dead.add(self._state_key())
            return None

        line_choice = self._pick_line_branch()
        if line_choice is not None:
            axis, idx, domain = line_choice
            for mask in domain:
                snap = self._snapshot()
                ok = self._apply_row_mask(idx, mask) if axis == "row" else self._apply_col_mask(idx, mask)
                if ok:
                    ans = self._search()
                    if ans is not None:
                        return ans
                self._restore(snap)
            self._dead.add(self._state_key())
            return None

        pos = self._pick_cell()
        if pos is None:
            self._dead.add(self._state_key())
            return None
        r, c = pos

        values = self._value_order(r, c)
        if not values:
            self._dead.add(self._state_key())
            return None

        for v in values:
            snap = self._snapshot()
            if self._set(r, c, v):
                ans = self._search()
                if ans is not None:
                    return ans
            self._restore(snap)

        self._dead.add(self._state_key())
        return None


def _normalize_observation(observation):
    obs = observation
    if isinstance(obs, dict) and "original_data" in obs and isinstance(obs["original_data"], dict):
        obs = obs["original_data"]
    if not isinstance(obs, dict):
        raise ValueError("heyawake observation must be dict")

    region = obs.get("region")
    data = obs.get("data")
    if not (isinstance(region, list) and region and isinstance(region[0], list)):
        raise ValueError("heyawake region must be 2D list")
    n = len(region)
    if any(len(row) != n for row in region):
        raise ValueError("heyawake region must be square")

    if isinstance(data, dict):
        clue = [[None for _ in range(n)] for _ in range(n)]
        for (r, c), v in data.items():
            clue[int(r)][int(c)] = None if v is None else int(v)
    elif isinstance(data, list) and data and isinstance(data[0], list):
        if len(data) != n or any(len(row) != n for row in data):
            raise ValueError("heyawake data size mismatch")
        clue = [[None if v is None else int(v) for v in row] for row in data]
    else:
        raise ValueError("heyawake data must be dict or 2D list")

    return [row[:] for row in region], clue


def solve(observation, verbose: bool = False, max_logs: int = 8000, log_level: str = "brief"):
    del verbose, max_logs, log_level

    region, clue = _normalize_observation(observation)
    solver = _HeyawakeSolver(region, clue)
    ans = solver._search()
    if ans is None:
        return "No Solution"

    return [["B" if ans[r][c] == 1 else None for c in range(solver.n)] for r in range(solver.n)]
