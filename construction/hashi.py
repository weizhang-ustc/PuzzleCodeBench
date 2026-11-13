import os
import re
from collections import deque
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# Connect numbered islands with bridges so that:
# 1. Bridges are straight and orthogonal, connecting two distinct islands.
# 2. Bridges cannot cross other bridges or pass through islands.
# 3. At most two bridges may connect the same pair of islands.
# 4. The number on each island equals the total number of incident bridges.
# 5. All islands must belong to one connected network.
# 
# **Coordinates & Output:**
# 1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
# 2. `row` increases top-to-bottom, `col` increases left-to-right.
# 3. **Observation:** dictionary mapping island coordinate to number.
#    Example: `{(0, 0): 3, (0, 4): 2, ...}`
# 4. **Answer:** dictionary mapping island-pair to bridge count `1` or `2`.
#    Example: `{((0,0),(0,4)): 2, ((0,4),(3,4)): 1, ...}`
# '''

RULES = '''
**Core Rules:**
Connect numbered islands with bridges so that:
1. Bridges are straight and orthogonal, connecting two distinct islands.
2. Bridges cannot cross other bridges or pass through islands.
3. At most two bridges may connect the same pair of islands.
4. The number on each island equals the total number of incident bridges.
5. All islands must belong to one connected network.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has one part:
   - `data`: island layout as `N x N` 2D list (`int` for islands, `None` otherwise).
4. **Answer:** dictionary `{((r1, c1), (r2, c2)): count}` where `count` is `1` or `2`.
'''


COLOR_BG = '#FFFFFF'
COLOR_GRID = '#E0E0E0'
COLOR_BRIDGE = '#111111'
COLOR_ISLAND_FACE = '#F7F7F7'
COLOR_ISLAND_EDGE = '#000000'
COLOR_ISLAND_TEXT = '#000000'


def _normalize_islands(islands):
    out = {}

    if isinstance(islands, dict):
        for (r, c), v in islands.items():
            if v is None:
                continue
            iv = int(v)
            if iv > 0:
                out[(int(r), int(c))] = iv
        return out

    if isinstance(islands, list) and islands and isinstance(islands[0], list):
        for r, row in enumerate(islands):
            for c, v in enumerate(row):
                if v is None:
                    continue
                iv = int(v)
                if iv > 0:
                    out[(int(r), int(c))] = iv
        return out

    raise ValueError('original_data.data must be a dict {(row,col): number} or a 2D grid list.')


def _normalize_bridges(bridges):
    if bridges is None:
        return {}
    if not isinstance(bridges, dict):
        raise ValueError('answer must be a dict of {((r1,c1),(r2,c2)): count}.')

    def _parse_bridge_key(key):
        # Native tuple key: ((r1, c1), (r2, c2))
        if isinstance(key, (tuple, list)) and len(key) == 2:
            a, b = key
            if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)) and len(a) == 2 and len(b) == 2:
                return (int(a[0]), int(a[1])), (int(b[0]), int(b[1]))

        # JSONL string key: "(r1, c1),(r2, c2)"
        if isinstance(key, str):
            nums = re.findall(r'-?\d+', key)
            if len(nums) == 4:
                r1, c1, r2, c2 = (int(x) for x in nums)
                return (r1, c1), (r2, c2)

        raise ValueError(f'invalid bridge key format: {key!r}')

    out = {}
    for key, count in bridges.items():
        (r1, c1), (r2, c2) = _parse_bridge_key(key)
        if (r2, c2) < (r1, c1):
            r1, c1, r2, c2 = r2, c2, r1, c1
        key = ((r1, c1), (r2, c2))
        out[key] = int(count)
    return out


def _draw_background_grid(ax, n):
    # Visible light-gray guidance grid (not a hard board frame).
    for i in range(n):
        ax.plot([-0.35, n - 0.65], [i, i], color=COLOR_GRID, linewidth=1.8, zorder=1)
        ax.plot([i, i], [-0.35, n - 0.65], color=COLOR_GRID, linewidth=1.8, zorder=1)


def _draw_bridges(ax, bridges):
    off = 0.08
    for ((r1, c1), (r2, c2)), cnt in bridges.items():
        if r1 == r2:  # horizontal
            if cnt == 1:
                ax.plot([c1, c2], [r1, r1], color=COLOR_BRIDGE, linewidth=3.4, solid_capstyle='round', zorder=3)
            else:
                ax.plot([c1, c2], [r1 - off, r1 - off], color=COLOR_BRIDGE, linewidth=3.0, solid_capstyle='round', zorder=3)
                ax.plot([c1, c2], [r1 + off, r1 + off], color=COLOR_BRIDGE, linewidth=3.0, solid_capstyle='round', zorder=3)
        else:  # vertical
            if cnt == 1:
                ax.plot([c1, c1], [r1, r2], color=COLOR_BRIDGE, linewidth=3.4, solid_capstyle='round', zorder=3)
            else:
                ax.plot([c1 - off, c1 - off], [r1, r2], color=COLOR_BRIDGE, linewidth=3.0, solid_capstyle='round', zorder=3)
                ax.plot([c1 + off, c1 + off], [r1, r2], color=COLOR_BRIDGE, linewidth=3.0, solid_capstyle='round', zorder=3)


def _draw_islands(ax, islands):
    for (r, c), v in islands.items():
        circ = patches.Circle((c, r), radius=0.47, facecolor=COLOR_ISLAND_FACE, edgecolor=COLOR_ISLAND_EDGE, linewidth=2.2, zorder=4)
        ax.add_patch(circ)
        ax.text(c, r, str(v), ha='center', va='center', fontsize=30, fontweight='bold', color=COLOR_ISLAND_TEXT, zorder=5)


def draw_hashi(islands, n, output_path, bridges=None):
    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_background_grid(ax, n)
    if bridges is not None:
        _draw_bridges(ax, bridges)
    _draw_islands(ax, islands)

    ticks = list(range(n))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])
    ax.set_yticklabels([str(t) for t in ticks])
    ax.xaxis.tick_top()
    ax.tick_params(axis='x', pad=2)
    ax.tick_params(axis='y', pad=2)

    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(-0.5, n - 0.5)
    ax.invert_yaxis()
    ax.set_aspect('equal')

    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout()
    save_square_figure(fig, output_path)
    plt.close()


def format_hashi_to_string(islands, bridges=None):
    lines = [f"data={dict(sorted(islands.items()))}"]
    if bridges is not None:
        lines.append(f"bridges={dict(sorted(bridges.items()))}")
    return '\n'.join(lines)


def construct_hashi_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'hashi'))
    os.makedirs(output_dir, exist_ok=True)

    n = int(puzzle_dict['column/row'])
    islands = _normalize_islands(puzzle_dict['original_data']['data'])
    bridges = _normalize_bridges(puzzle_dict['answer'])

    fig_name = f"hashi_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_hashi(islands, n, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"hashi_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_hashi(islands, n, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), bridges=bridges)

    output_dict = {'puzzle': 'hashi'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_hashi_to_string(islands)
    output_dict['answer_str'] = format_hashi_to_string(islands, bridges=bridges)
    return output_dict


def _bridge_crosses(a1, a2, b1, b2):
    # a horizontal, b vertical
    ra, ca1 = a1
    _, ca2 = a2
    rb1, cb = b1
    rb2, _ = b2
    c_lo, c_hi = sorted((ca1, ca2))
    r_lo, r_hi = sorted((rb1, rb2))
    return c_lo < cb < c_hi and r_lo < ra < r_hi


def _validate_bridges(islands, bridges):
    if not islands:
        return False

    degree = {k: 0 for k in islands}
    horiz = []
    vert = []

    for (a, b), cnt in bridges.items():
        if cnt not in (1, 2):
            return False
        if a == b:
            return False
        if a not in islands or b not in islands:
            return False
        r1, c1 = a
        r2, c2 = b
        if r1 != r2 and c1 != c2:
            return False

        # No island strictly between endpoints.
        if r1 == r2:
            c_lo, c_hi = sorted((c1, c2))
            for cc in range(c_lo + 1, c_hi):
                if (r1, cc) in islands:
                    return False
            horiz.append((a, b))
        else:
            r_lo, r_hi = sorted((r1, r2))
            for rr in range(r_lo + 1, r_hi):
                if (rr, c1) in islands:
                    return False
            vert.append((a, b))

        degree[a] += cnt
        degree[b] += cnt

    # No crossing bridges.
    for ha, hb in horiz:
        ha1, ha2 = ha, hb
        # normalize horizontal order by col
        if ha2[1] < ha1[1]:
            ha1, ha2 = ha2, ha1
        for va, vb in vert:
            vb1, vb2 = va, vb
            if vb2[0] < vb1[0]:
                vb1, vb2 = vb2, vb1
            if _bridge_crosses(ha1, ha2, vb1, vb2):
                return False

    # Degree match island numbers.
    for k, required in islands.items():
        if degree[k] != required:
            return False

    # Connectivity of island graph.
    start = next(iter(islands))
    q = deque([start])
    seen = {start}
    graph = {k: set() for k in islands}
    for (a, b), cnt in bridges.items():
        if cnt > 0:
            graph[a].add(b)
            graph[b].add(a)
    while q:
        cur = q.popleft()
        for nxt in graph[cur]:
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return len(seen) == len(islands)


def test_observation(observation, gt_observation):
    """Test if observation matches gt_observation."""
    return observation == gt_observation


def test_answer(answer, gt_answer):
    """Test if answer matches gt_answer. No Solution (case-insensitive); bridges only 1/2; canonical keys; no duplicates."""

    if isinstance(gt_answer, str) and gt_answer.strip().lower() == "no solution":
        return isinstance(answer, str) and answer.strip().lower() == "no solution"

    if not isinstance(answer, dict) or not isinstance(gt_answer, dict):
        return answer == gt_answer

    def _canonical(bridges):
        def _parse_key(key):
            if isinstance(key, (tuple, list)) and len(key) == 2:
                a, b = key
                if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)) and len(a) == 2 and len(b) == 2:
                    return (int(a[0]), int(a[1])), (int(b[0]), int(b[1]))
            if isinstance(key, str):
                nums = re.findall(r'-?\d+', key)
                if len(nums) == 4:
                    r1, c1, r2, c2 = (int(x) for x in nums)
                    return (r1, c1), (r2, c2)
            raise ValueError('invalid bridge key')

        out = {}
        for key, count in bridges.items():
            try:
                iv = int(count)
            except (TypeError, ValueError):
                return None
            if iv not in (1, 2):
                return None
            try:
                (r1, c1), (r2, c2) = _parse_key(key)
            except (ValueError, TypeError):
                return None
            if (r2, c2) < (r1, c1):
                r1, c1, r2, c2 = r2, c2, r1, c1
            canon = ((r1, c1), (r2, c2))
            if canon in out:
                return None
            out[canon] = iv
        return out

    ca = _canonical(answer)
    cg = _canonical(gt_answer)
    if ca is None or cg is None:
        return False
    return ca == cg


def test_code(observation, answer, gt_observation, gt_answer):
    '''
    1. Observation
    2. No Solution
    3. Answer
    '''
    if observation != gt_observation:
        return False
    if answer is None:
        return False

    obs_data = observation.get('data') if isinstance(observation, dict) else observation
    islands = _normalize_islands(obs_data)
    bridges = _normalize_bridges(answer)
    if not _validate_bridges(islands, bridges):
        return False
    if gt_answer is None:
        return True
    return bridges == _normalize_bridges(gt_answer)


def get_observation(data):
    data = normalize_size_keys(data)
    n = data['column/row']
    raw = data['original_data']['data']
    if isinstance(raw, list):
        grid = [row[:] for row in raw]
    else:
        islands = _normalize_islands(raw)
        grid = [[None for _ in range(n)] for _ in range(n)]
        for (r, c), v in islands.items():
            grid[r][c] = v
    return {'data': grid}


def return_data():
    ref_puzzle_dict = {
        'column/row': 7,
        'level': 'easy',
        'original_data': {
            # 'data': {
            #     (0, 0): 4,
            #     (0, 4): 3,
            #     (0, 6): 2,
            #     (1, 2): 1,
            #     (1, 5): 3,
            #     (2, 6): 3,
            #     (3, 0): 6,
            #     (3, 5): 5,
            #     (4, 6): 2,
            #     (5, 2): 1,
            #     (5, 5): 2,
            #     (6, 0): 4,
            #     (6, 6): 2
            # }
            'data': [
                [4, None, None, None, 3, None, 2],
                [None, None, 1, None, None, 3, None],
                [None, None, None, None, None, None, 3],
                [6, None, None, None, None, 5, None],
                [None, None, None, None, None, None, 2],
                [None, None, 1, None, None, 2, None],
                [4, None, None, None, None, None, 2],
            ]
        },
        'answer': {
            ((0, 0), (0, 4)): 2,
            ((0, 0), (3, 0)): 2,
            ((0, 4), (0, 6)): 1,
            ((1, 2), (1, 5)): 1,
            ((0, 6), (2, 6)): 1,
            ((2, 6), (4, 6)): 2,
            ((1, 5), (3, 5)): 2,
            ((3, 0), (3, 5)): 2,
            ((3, 0), (6, 0)): 2,
            ((3, 5), (5, 5)): 1,
            ((5, 2), (5, 5)): 1,
            ((6, 0), (6, 6)): 2,
        },
        'id': 'ref',
        'rules': RULES,
    }
    ref_puzzle_dict['observation'] = get_observation(ref_puzzle_dict)

    puzzles = [
        {
            'column/row': 10,
            'level': 'easy',
            'original_data': {
                # 'data': {
                #     (0, 0): 3, (0, 2): 6, (0, 4): 3, (0, 9): 3,
                #     (1, 1): 2, (1, 3): 2, (1, 8): 3,
                #     (2, 2): 2,
                #     (3, 5): 1, (3, 8): 3,
                #     (4, 1): 4, (4, 3): 3,
                #     (5, 0): 3, (5, 2): 2, (5, 5): 6, (5, 8): 5,
                #     (6, 1): 2, (6, 4): 4, (6, 9): 2,
                #     (7, 5): 4, (7, 7): 2,
                #     (8, 0): 2, (8, 2): 1,
                #     (9, 4): 4, (9, 8): 4
                # }
                'data': [
                    [3, None, 6, None, 3, None, None, None, None, 3],
                    [None, 2, None, 2, None, None, None, None, 3, None],
                    [None, None, 2, None, None, None, None, None, None, None],
                    [None, None, None, None, None, 1, None, None, 3, None],
                    [None, 4, None, 3, None, None, None, None, None, None],
                    [3, None, 2, None, None, 6, None, None, 5, None],
                    [None, 2, None, None, 4, None, None, None, None, 2],
                    [None, None, None, None, None, 4, None, 2, None, None],
                    [2, None, 1, None, None, None, None, None, None, None],
                    [None, None, None, None, 4, None, None, None, 4, None],
                ]
            },
            'answer': {
                ((0, 0), (0, 2)): 2,
                ((0, 2), (0, 4)): 2,
                ((0, 4), (0, 9)): 1,
                ((0, 0), (5, 0)): 1,
                ((0, 2), (2, 2)): 2,
                ((1, 1), (4, 1)): 2,
                ((4, 1), (4, 3)): 2,
                ((1, 3), (4, 3)): 1,
                ((1, 3), (1, 8)): 1,
                ((1, 8), (3, 8)): 2,
                ((3, 8), (5, 8)): 1,
                ((3, 5), (5, 5)): 1,
                ((5, 0), (5, 2)): 1,
                ((5, 2), (5, 5)): 1,
                ((5, 5), (7, 5)): 2,
                ((7, 5), (7, 7)): 2,
                ((5, 5), (5, 8)): 2,
                ((0, 9), (6, 9)): 2,
                ((5, 0), (8, 0)): 1,
                ((8, 0), (8, 2)): 1,
                ((6, 1), (6, 4)): 2,
                ((6, 4), (9, 4)): 2,
                ((9, 4), (9, 8)): 2,
                ((5, 8), (9, 8)): 2,
            },
            'id': 'example_0',
            'rules': RULES,
        }
    ]
    for puzzle in puzzles:
        puzzle['observation'] = get_observation(puzzle)

    return ref_puzzle_dict, puzzles


if __name__ == '__main__':
    ref_puzzle_dict, puzzles = return_data()
    ret = construct_hashi_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_hashi_data(puzzle)
    print(ret)
