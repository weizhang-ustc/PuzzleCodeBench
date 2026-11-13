import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules (1-Star):**
# Place stars on the grid so that:
# 1. Each row contains exactly 1 star.
# 2. Each column contains exactly 1 star.
# 3. Each region contains exactly 1 star.
# 4. Stars cannot touch each other, including diagonally.
# 
# **Coordinates & Output:**
# 1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
# 2. `row` increases top-to-bottom, `col` increases left-to-right.
# 3. **Observation:** a list of lists describing region IDs for every cell.
#    Example: `[[0, 0, 1], [0, 2, 2], [3, 3, 2]]`
# 4. **Answer:** same-sized grid using `'S'` for star cells and `None` for non-star cells.
# '''

RULES = '''
**Core Rules (1-Star):**
Place stars on the grid so that:
1. Each row contains exactly 1 star.
2. Each column contains exactly 1 star.
3. Each region contains exactly 1 star.
4. Stars cannot touch each other, including diagonally.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has one part:
   - `data`: region ID grid as `N x N` list of lists.
4. **Answer:** same-sized grid using `'S'` for star cells and `None` for non-star cells.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_GRID_THIN = '#6A6A6A'
COLOR_REGION_BORDER = '#000000'
COLOR_STAR = '#111111'
REGION_LINE_WIDTH = 3.6


def regions_to_region_id_grid(region_groups, n=None):
    """
    Convert region groups -> region ID grid.
    Input: [[(r,c), ...], [(r,c), ...], ...]
    Output: [[rid, rid, ...], ...]
    """
    if n is None:
        max_r = max(r for region in region_groups for r, _ in region)
        max_c = max(c for region in region_groups for _, c in region)
        n = max(max_r, max_c) + 1

    region_grid = [[None for _ in range(n)] for _ in range(n)]
    for rid, cells in enumerate(region_groups):
        for r, c in cells:
            region_grid[r][c] = rid
    return region_grid


def region_id_grid_to_regions(region_grid):
    """
    Convert region ID grid -> region groups.
    Input: [[0,0,1],[2,2,1],...]
    Output: [[(0,0),(0,1)],[(0,2),(1,2)],...]
    """
    groups = {}
    for r in range(len(region_grid)):
        for c in range(len(region_grid[r])):
            rid = region_grid[r][c]
            if rid is None:
                continue
            groups.setdefault(rid, []).append((r, c))

    return [groups[rid] for rid in sorted(groups.keys())]


def normalize_region_grid(data, n=None):
    """
    Accept either:
    - region ID grid: list[list[int]]
    - region groups: list[list[tuple[int,int]]]
    - wrapped dict: {'data': ...} or {'regions': ...}
    """
    if isinstance(data, dict):
        data = data.get('data', data.get('regions', data))

    if not isinstance(data, list) or not data:
        raise ValueError('Region data must be a non-empty list.')

    if isinstance(data[0], list) and data[0] and not isinstance(data[0][0], tuple):
        return [row[:] for row in data]

    return regions_to_region_id_grid(data, n=n)


def _draw_cells(ax, n):
    for r in range(n):
        for c in range(n):
            rect = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                facecolor=COLOR_CELL,
                edgecolor=COLOR_GRID_THIN,
                linewidth=0.8,
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


def _draw_stars(ax, answer):
    n = len(answer)
    xs, ys = [], []
    for r in range(n):
        for c in range(n):
            if answer[r][c] == 'S':
                xs.append(c)
                ys.append(r)

    if xs:
        ax.scatter(xs, ys, marker='*', s=700, c=COLOR_STAR, linewidths=1.2, edgecolors=COLOR_STAR, zorder=5)


def draw_starbattle1(region_grid, output_path, answer=None):
    n = len(region_grid)
    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))
    ax.set_facecolor(COLOR_BG)

    _draw_cells(ax, n)
    _draw_region_boundaries(ax, region_grid)
    if answer is not None:
        _draw_stars(ax, answer)

    ticks = list(range(n))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])
    ax.set_yticklabels([str(t) for t in ticks])
    ax.xaxis.tick_top()

    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(-0.5, n - 0.5)
    ax.invert_yaxis()
    ax.set_aspect('equal')

    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout()
    save_square_figure(fig, output_path)
    plt.close()


def format_starbattle1_to_string(region_grid, answer=None):
    n = len(region_grid)
    lines = []
    for r in range(n):
        row_tokens = []
        for c in range(n):
            if answer is not None and answer[r][c] == 'S':
                row_tokens.append(f"{region_grid[r][c]}*")
            else:
                row_tokens.append(str(region_grid[r][c]))
        lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_starbattle1_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'starbattle1'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    region_grid = normalize_region_grid(puzzle_dict['original_data'], n=n)

    fig_name = f"starbattle1_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_starbattle1(region_grid, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"starbattle1_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_starbattle1(region_grid, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'starbattle1'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_starbattle1_to_string(region_grid)
    output_dict['answer_str'] = format_starbattle1_to_string(region_grid, answer=puzzle_dict['answer'])

    return output_dict


def test_observation(observation, gt_observation):
    """Compare `data` region grids; region IDs may be permuted."""

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

    ro, rg = observation['data'], gt_observation['data']
    norm_obs, norm_gt = _normalize_region_grid(ro), _normalize_region_grid(rg)
    if norm_obs is None or norm_gt is None:
        return ro == rg
    return norm_obs == norm_gt


def test_answer(answer, gt_answer):
    """Exact match, or both 'No Solution' (case-insensitive)."""
    if isinstance(gt_answer, str) and gt_answer.strip().lower() == 'no solution':
        return isinstance(answer, str) and answer.strip().lower() == 'no solution'
    return answer == gt_answer


def test_code(observation, answer, gt_observation, gt_answer):
    '''
    1. Observation
    2. No Solution
    3. Answer
    '''
    return


def get_observation(data):
    data = normalize_size_keys(data)
    n = data['column/row']
    region_grid = normalize_region_grid(data['original_data'], n=n)
    return {'data': [row[:] for row in region_grid]}


def return_data():
    ref_puzzle_dict = {
        'column/row': 5,
        'level': 'easy',
        'original_data': {
            'data': [
                [0, 0, 0, 0, 0],
                [0, 0, 0, 1, 1],
                [2, 3, 3, 1, 4],
                [2, 3, 3, 1, 4],
                [2, 1, 1, 1, 4],
            ],
        },
        'answer': [
            [None, 'S', None, None, None],
            [None, None, None, 'S', None],
            ['S', None, None, None, None],
            [None, None, 'S', None, None],
            [None, None, None, None, 'S'],
        ],
        'id': 'ref',
        'rules': RULES,
    }
    ref_puzzle_dict['observation'] = get_observation(ref_puzzle_dict)

    puzzles = [
        {
            'column/row': 5,
            'level': 'easy',
            'original_data': {
                'data': [
                    [0, 0, 0, 1, 1],
                    [0, 2, 0, 3, 3],
                    [0, 2, 2, 2, 3],
                    [0, 2, 2, 2, 4],
                    [0, 2, 4, 4, 4],
                ],
            },
            'answer': [
                [None, None, None, 'S', None],
                [None, 'S', None, None, None],
                [None, None, None, None, 'S'],
                ['S', None, None, None, None],
                [None, None, 'S', None, None],
            ],
            'id': 'example_0',
            'rules': RULES,
        },
        {
            'column/row': 5,
            'level': 'easy',
            'original_data': {
                'data': [
                    [0, 1, 1, 1, 1],
                    [0, 0, 0, 1, 1],
                    [0, 0, 2, 2, 1],
                    [3, 3, 2, 2, 1],
                    [3, 3, 2, 4, 4],
                ],
            },
            'answer': [
                [None, None, 'S', None, None],
                ['S', None, None, None, None],
                [None, None, None, 'S', None],
                [None, 'S', None, None, None],            
                [None, None, None, None, 'S'],
            ],
            'id': 'example_1',
            'rules': RULES,
        },
        {
            'column/row': 6,
            'level': 'easy',
            'original_data': {
                'data': [
                    [0, 0, 0, 1, 1, 2],
                    [3, 0, 1, 1, 2, 2],
                    [3, 3, 1, 1, 2, 2],
                    [4, 4, 1, 2, 2, 2],
                    [4, 4, 5, 5, 5, 2],
                    [4, 4, 5, 5, 5, 2],
                ],
            },
            'answer': [
                [None, None, 'S', None, None, None],
                ['S', None, None, None, None, None],
                [None, None, None, 'S', None, None],
                [None, None, None, None, None, 'S'],
                [None, 'S', None, None, None, None],
                [None, None, None, None, 'S', None],
            ],
            'id': 'example_2',
            'rules': RULES,
        },
        {
            'column/row': 6,
            'level': 'easy',
            'original_data': {
                'data': [
                    [0, 1, 1, 2, 2, 2],
                    [0, 1, 1, 2, 2, 2],
                    [0, 3, 3, 3, 2, 2],
                    [0, 3, 4, 4, 4, 4],
                    [5, 3, 4, 4, 4, 4],
                    [5, 5, 4, 4, 4, 4],
                ],
            },
            'answer': [
                [None, None, 'S', None, None, None],
                [None, None, None, None, None, 'S'],
                [None, None, None, 'S', None, None],
                ['S', None, None, None, None, None],
                [None, None, None, None, 'S', None],
                [None, 'S', None, None, None, None],
            ],
            'id': 'example_3',
            'rules': RULES,
        },
        {
            'column/row': 8,
            'level': 'hard',
            'original_data': {
                'data': [
                    [0, 0, 1, 1, 1, 2, 2, 2],
                    [3, 0, 1, 1, 1, 1, 1, 2],
                    [3, 3, 1, 1, 1, 1, 2, 2],
                    [3, 4, 4, 4, 4, 2, 2, 2],
                    [3, 3, 3, 3, 4, 2, 5, 5],
                    [3, 4, 3, 4, 4, 2, 6, 5],
                    [3, 4, 4, 4, 2, 2, 6, 5],
                    [3, 3, 3, 7, 7, 7, 7, 7],
                ],
            },
            'answer': [
                [None, None, None, None, None, 'S', None, None],
                [None, 'S', None, None, None, None, None, None],
                [None, None, None, None, 'S', None, None, None],
                [None, None, 'S', None, None, None, None, None],
                [None, None, None, None, None, None, None, 'S'],
                ['S', None, None, None, None, None, None, None],
                [None, None, None, None, None, None, 'S', None],
                [None, None, None, 'S', None, None, None, None],
            ],
            'id': 'example_4',
            'rules': RULES,
        }
    ]
    for puzzle in puzzles:
        puzzle['observation'] = get_observation(puzzle)

    return ref_puzzle_dict, puzzles


if __name__ == '__main__':
    ref_puzzle_dict, puzzles = return_data()
    ret = construct_starbattle1_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_starbattle1_data(puzzle)
    print(ret)
