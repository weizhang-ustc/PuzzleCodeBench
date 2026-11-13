import os
from collections import deque
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# Color cells black or white so that:
# 1. A numbered region contains exactly that many black cells.
# 2. Black cells cannot touch orthogonally.
# 3. Any uninterrupted straight white segment (row/column) cannot pass through more than 2 regions.
# 4. All white cells are orthogonally connected.
# 
# **Coordinates & Output:**
# 1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
# 2. `row` increases top-to-bottom, `col` increases left-to-right.
# 3. **Observation** has two parts:
#    - `region`: region ID grid as list of lists.
#    - `data`: dictionary mapping clue coordinate to number.
# 4. **Answer:** same-sized grid using `'B'` for black cells and `None` for white cells.
# '''

RULES = '''
**Core Rules:**
Color cells black or white so that:
1. A numbered region contains exactly that many black cells.
2. Black cells cannot touch orthogonally.
3. Any uninterrupted straight white segment (row/column) cannot pass through more than 2 regions.
4. All white cells are orthogonally connected.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation:** dictionary with:
   - `region`: `N x N` region-ID 2D list
   - `data`: clue 2D list (`int` or `None`)
4. **Answer:** `N x N` 2D list using `'B'` for black cells and `None` for white cells.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_GRID_THIN = '#666666'
COLOR_REGION_BORDER = '#000000'
COLOR_GIVEN_TEXT = '#111111'
COLOR_GIVEN_TEXT_ON_BLACK = '#FFFFFF'
COLOR_BLACK = '#6A6A6A'
REGION_LINE_WIDTH = 3.8


def _is_black(value):
    return value in {'B', '#', 1, True}


def _normalize_clue_grid(data):
    if isinstance(data, dict):
        if not data:
            return [[None]]
        max_r = max(r for r, _ in data.keys())
        max_c = max(c for _, c in data.keys())
        size_r = max_r + 1
        size_c = max_c + 1
        grid = [[None for _ in range(size_c)] for _ in range(size_r)]
        for (r, c), v in data.items():
            grid[r][c] = v
        return grid

    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError('heyawake data must be a dict or 2D list.')

    return [row[:] for row in data]


def _normalize_region_grid(region_data, n=None):
    if not isinstance(region_data, list) or not region_data:
        raise ValueError('region must be a non-empty list of lists.')
    if not isinstance(region_data[0], list):
        raise ValueError('region must be a 2D list.')

    grid = [row[:] for row in region_data]
    if n is not None:
        if len(grid) != n:
            raise ValueError('region size does not match board size.')
        for row in grid:
            if len(row) != n:
                raise ValueError('region must be square and match board size.')
    return grid


def _draw_cells(ax, n):
    for r in range(n):
        for c in range(n):
            rect = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                facecolor=COLOR_CELL,
                edgecolor=COLOR_GRID_THIN,
                linewidth=0.95,
                zorder=1,
            )
            ax.add_patch(rect)


def _draw_region_boundaries(ax, region_grid):
    n = len(region_grid)

    for i in range(n + 1):
        ax.plot([-0.5, n - 0.5], [i - 0.5, i - 0.5], color=COLOR_GRID_THIN, linewidth=1.0, zorder=2)
        ax.plot([i - 0.5, i - 0.5], [-0.5, n - 0.5], color=COLOR_GRID_THIN, linewidth=1.0, zorder=2)

    for r in range(n):
        for c in range(n):
            curr = region_grid[r][c]
            if c + 1 < n and region_grid[r][c + 1] != curr:
                x = c + 0.5
                ax.plot([x, x], [r - 0.5, r + 0.5], color=COLOR_REGION_BORDER, linewidth=REGION_LINE_WIDTH, zorder=3)
            if r + 1 < n and region_grid[r + 1][c] != curr:
                y = r + 0.5
                ax.plot([c - 0.5, c + 0.5], [y, y], color=COLOR_REGION_BORDER, linewidth=REGION_LINE_WIDTH, zorder=3)

    x0, x1 = -0.5, n - 0.5
    y0, y1 = -0.5, n - 0.5
    frame_style = dict(color=COLOR_REGION_BORDER, linewidth=REGION_LINE_WIDTH, zorder=4, clip_on=False, solid_capstyle='butt')
    ax.plot([x0, x1], [y0, y0], **frame_style)
    ax.plot([x0, x1], [y1, y1], **frame_style)
    ax.plot([x0, x0], [y0, y1], **frame_style)
    ax.plot([x1, x1], [y0, y1], **frame_style)


def _draw_clues(ax, data_grid, n, answer=None):
    rows = len(data_grid)
    cols = len(data_grid[0]) if rows else 0

    # Cell-grid clues: n x n
    if rows == n and cols == n:
        for r in range(n):
            for c in range(n):
                val = data_grid[r][c]
                if val is None:
                    continue
                color = COLOR_GIVEN_TEXT
                if answer is not None and _is_black(answer[r][c]):
                    color = COLOR_GIVEN_TEXT_ON_BLACK
                ax.text(c, r, str(val), ha='center', va='center', fontsize=24, fontweight='bold', color=color, zorder=5)
        return

    # Node-grid clues: (n+1) x (n+1)
    if rows == n + 1 and cols == n + 1:
        for r in range(rows):
            for c in range(cols):
                val = data_grid[r][c]
                if val is None:
                    continue
                x = c - 0.5
                y = r - 0.5
                ax.text(x, y, str(val), ha='center', va='center', fontsize=16, fontweight='bold', color=COLOR_GIVEN_TEXT, zorder=5)


def _draw_answer(ax, answer):
    n = len(answer)
    for r in range(n):
        for c in range(n):
            if _is_black(answer[r][c]):
                rect = patches.Rectangle(
                    (c - 0.5, r - 0.5),
                    1,
                    1,
                    facecolor=COLOR_BLACK,
                    edgecolor=COLOR_GRID_THIN,
                    linewidth=0.95,
                    zorder=2.5,
                )
                ax.add_patch(rect)


def draw_heyawake(region_grid, data_grid, output_path, answer=None):
    n = len(region_grid)
    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_cells(ax, n)
    if answer is not None:
        _draw_answer(ax, answer)
    _draw_region_boundaries(ax, region_grid)
    _draw_clues(ax, data_grid, n, answer=answer)

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


def format_heyawake_to_string(region_grid, data_grid, answer=None):
    lines = [f"region={region_grid}", f"data={data_grid}"]
    n = len(region_grid)
    if answer is not None:
        for r in range(n):
            row_tokens = []
            for c in range(n):
                row_tokens.append('B' if _is_black(answer[r][c]) else '.')
            lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_heyawake_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'heyawake'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    original = puzzle_dict['original_data']
    region_grid = _normalize_region_grid(original['region'], n=n)
    data_grid = _normalize_clue_grid(original.get('data', {}))

    fig_name = f"heyawake_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_heyawake(region_grid, data_grid, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"heyawake_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_heyawake(region_grid, data_grid, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'heyawake'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_heyawake_to_string(region_grid, data_grid)
    output_dict['answer_str'] = format_heyawake_to_string(region_grid, data_grid, answer=puzzle_dict['answer'])
    return output_dict


def _cells_by_region(region_grid):
    groups = {}
    n = len(region_grid)
    for r in range(n):
        for c in range(n):
            rid = region_grid[r][c]
            groups.setdefault(rid, []).append((r, c))
    return groups


def _check_no_adjacent_black(answer):
    n = len(answer)
    for r in range(n):
        for c in range(n):
            if not _is_black(answer[r][c]):
                continue
            for dr, dc in ((1, 0), (0, 1)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < n and 0 <= cc < n and _is_black(answer[rr][cc]):
                    return False
    return True


def _check_region_clues(region_grid, data_grid, answer):
    n = len(region_grid)
    rows = len(data_grid)
    cols = len(data_grid[0]) if rows else 0

    # Only enforce clues when they are on the cell grid (n x n).
    if rows != n or cols != n:
        return True

    region_cells = _cells_by_region(region_grid)
    black_count = {}
    for rid, cells in region_cells.items():
        black_count[rid] = sum(1 for r, c in cells if _is_black(answer[r][c]))

    for r in range(n):
        for c in range(n):
            clue = data_grid[r][c]
            if clue is None:
                continue
            if black_count[region_grid[r][c]] != clue:
                return False
    return True


def _check_white_line_region_limit(region_grid, answer):
    n = len(answer)

    for r in range(n):
        c = 0
        while c < n:
            if _is_black(answer[r][c]):
                c += 1
                continue
            regions = []
            while c < n and not _is_black(answer[r][c]):
                rid = region_grid[r][c]
                if not regions or regions[-1] != rid:
                    regions.append(rid)
                c += 1
            if len(regions) > 2:
                return False

    for c in range(n):
        r = 0
        while r < n:
            if _is_black(answer[r][c]):
                r += 1
                continue
            regions = []
            while r < n and not _is_black(answer[r][c]):
                rid = region_grid[r][c]
                if not regions or regions[-1] != rid:
                    regions.append(rid)
                r += 1
            if len(regions) > 2:
                return False

    return True


def _check_white_connected(answer):
    n = len(answer)
    whites = [(r, c) for r in range(n) for c in range(n) if not _is_black(answer[r][c])]
    if not whites:
        return False

    start = whites[0]
    seen = {start}
    q = deque([start])
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < n and 0 <= cc < n and not _is_black(answer[rr][cc]) and (rr, cc) not in seen:
                seen.add((rr, cc))
                q.append((rr, cc))

    return len(seen) == len(whites)


def test_observation(observation, gt_observation):
    """Test if observation matches gt_observation. Region IDs may be permuted (same as aquarium)."""
    if not isinstance(observation, dict):
        return False

    def _normalize_region_grid(region):
        if not isinstance(region, list) or not region:
            return None
        n = len(region)
        regions = {}
        for r in range(n):
            if not isinstance(region[r], list) or len(region[r]) != n:
                return None
            for c in range(n):
                rid = region[r][c]
                regions.setdefault(rid, []).append((r, c))
        sorted_items = sorted(
            regions.items(),
            key=lambda x: (len(x[1]), tuple(sorted(x[1]))),
        )
        rid_to_new = {old_rid: i for i, (old_rid, _) in enumerate(sorted_items)}
        return [[rid_to_new[region[r][c]] for c in range(n)] for r in range(n)]

    for key in gt_observation:
        if key not in observation:
            return False
        if key == 'region':
            norm_obs = _normalize_region_grid(observation['region'])
            norm_gt = _normalize_region_grid(gt_observation['region'])
            if norm_obs is None or norm_gt is None:
                if observation['region'] != gt_observation['region']:
                    return False
            elif norm_obs != norm_gt:
                return False
        else:
            if observation[key] != gt_observation[key]:
                return False
    return True


def test_answer(answer, gt_answer):
    """Test if answer matches gt_answer. Handles 'No Solution' case-insensitively; otherwise ==."""
    if isinstance(gt_answer, str) and gt_answer.strip().lower() == "no solution":
        return isinstance(answer, str) and answer.strip().lower() == "no solution"
    return answer == gt_answer


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

    region_grid = observation.get('region')
    data_grid = observation.get('data')
    if region_grid is None or data_grid is None:
        return False

    n = len(region_grid)
    if len(answer) != n:
        return False
    for row in answer:
        if len(row) != n:
            return False

    if not _check_no_adjacent_black(answer):
        return False
    if not _check_region_clues(region_grid, data_grid, answer):
        return False
    if not _check_white_line_region_limit(region_grid, answer):
        return False
    if not _check_white_connected(answer):
        return False

    if gt_answer is None:
        return True
    return answer == gt_answer


def get_observation(data):
    data = normalize_size_keys(data)
    n = data['column/row']
    original = data['original_data']
    region_grid = _normalize_region_grid(original['region'], n=n)
    return {
        'region': [row[:] for row in region_grid],
        'data': _normalize_clue_grid(original.get('data', {})),
    }


def return_data():
    ref_puzzle_dict = {
        'column/row': 6,
        'level': 'easy',
        'original_data': {
            'region': [
                [0, 1, 1, 1, 2, 2],
                [3, 3, 3, 3, 2, 2],
                [4, 4, 5, 6, 6, 7],
                [8, 8, 8, 6, 6, 7],
                [8, 8, 8, 9, 10, 7],
                [8, 8, 8, 9, 11, 11],
            ],
            # 'data': {
            #     (0, 0): 1,
            #     (0, 4): 1,
            #     (1, 0): 1,
            #     (2, 2): 1,
            #     (2, 5): 1,
            #     (3, 0): 3,
            #     (4, 4): 1,
            # }
            'data': [
                [1, None, None, None, 1, None],
                [1, None, None, None, None, None],
                [None, None, 1, None, None, 1],
                [3, None, None, None, None, None],
                [None, None, None, None, 1, None],
                [None, None, None, None, None, None],
            ]
        },
        'answer': [
            ['B', None, None, 'B', None, 'B'],
            [None, 'B', None, None, None, None],
            [None, None, 'B', None, None, 'B'],
            ['B', None, None, 'B', None, None],
            [None, None, None, None, 'B', None],
            ['B', None, 'B', None, None, None],
        ],
        'id': 'ref',
        'rules': RULES,
    }
    ref_puzzle_dict['observation'] = get_observation(ref_puzzle_dict)

    puzzles = [
        {
            'column/row': 6,
            'level': 'easy',
            'original_data': {
                'region': [
                    [0, 0, 1, 1, 1, 1],
                    [0, 0, 2, 3, 3, 3],
                    [0, 0, 4, 4, 5, 5],
                    [6, 7, 7, 8, 5, 5],
                    [6, 7, 7, 8, 10, 11],
                    [6, 7, 7, 8, 12, 11],
                ],
                # 'data': {
                #     (0, 2): 1,
                #     (1, 3): 1,
                #     (2, 2): 1,
                #     (2, 4): 1,
                #     (3, 1): 1,
                #     (3, 3): 1,
                #     (4, 4): 1,
                #     (4, 5): 0,
                # }
                'data': [
                    [None, None, 1, None, None, None],
                    [None, None, None, 1, None, None],
                    [None, None, 1, None, 1, None],
                    [None, 1, None, 1, None, None],
                    [None, None, None, None, 1, 0],
                    [None, None, None, None, None, None],
                ]
            },
            'answer': [
                [None, None, 'B', None, None, None],
                [None, 'B', None, None, 'B', None],
                [None, None, None, 'B', None, 'B'],
                [None, None, 'B', None, None, None],
                ['B', None, None, None, 'B', None],
                [None, None, None, 'B', None, None],
            ],
            'id': 'example_0',
            'rules': RULES,
        },
        {
            'column/row': 6,
            'level': 'easy',
            'original_data': {
                'region': [
                    [0, 1, 1, 2, 3, 4],
                    [0, 1, 1, 2, 5, 4],
                    [0, 1, 1, 6, 5, 4],
                    [0, 1, 1, 6, 5, 4],
                    [7, 1, 1, 6, 8, 4],
                    [9, 9, 9, 9, 9, 9],
                ],
                # 'data': {
                #     (0, 0): 0,
                #     (0, 1): 3,
                #     (0, 3): 0,
                #     (0, 4): 0,
                #     (1, 4): 1,
                #     (2, 3): 1,
                #     (5, 0): 1,
                # },
                'data': [
                    [0, 3, None, 0, 0, None],
                    [None, None, None, None, 1, None],
                    [None, None, None, 1, None, None],
                    [None, None, None, None, None, None],
                    [None, None, None, None, None, None],
                    [1, None, None, None, None, None],
                ]
            },
            'answer': [
                [None, None, 'B', None, None, 'B'],
                [None, 'B', None, None, 'B', None],
                [None, None, None, 'B', None, None],
                [None, None, 'B', None, None, 'B'],
                ['B', None, None, None, 'B', None],
                [None, None, 'B', None, None, None],
            ],
            'id': 'example_1',
            'rules': RULES,
        }
    ]
    for puzzle in puzzles:
        puzzle['observation'] = get_observation(puzzle)

    return ref_puzzle_dict, puzzles


if __name__ == '__main__':
    ref_puzzle_dict, puzzles = return_data()
    ret = construct_heyawake_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_heyawake_data(puzzle)
    print(ret)
