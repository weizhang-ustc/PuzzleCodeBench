import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# Fill the grid with numbers `1..N` so that:
# 1. Each row contains each number exactly once.
# 2. Each column contains each number exactly once.
# 3. Each irregular region contains each number exactly once.
# 
# **Coordinates & Output:**
# 1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
# 2. `row` increases top-to-bottom, `col` increases left-to-right.
# 3. **Observation** has two parts:
#    - `regions`: region ID grid as list of lists.
#    - `givens`: dictionary mapping coordinate to given number.
# 4. **Answer:** full solved `N x N` number grid.
# '''

RULES = '''
**Core Rules:**
Fill the grid with numbers `1..N` so that:
1. Each row contains each number exactly once.
2. Each column contains each number exactly once.
3. Each irregular region contains each number exactly once.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation:** dictionary with:
   - `region`: `N x N` region-ID 2D list
   - `data`: `N x N` givens 2D list (`int` or `None`)
4. **Answer:** full solved `N x N` 2D list of numbers.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_GRID_THIN = '#666666'
COLOR_REGION_BORDER = '#000000'
COLOR_GIVEN_TEXT = '#111111'
COLOR_FILL_TEXT = '#1E73BE'
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


def _normalize_givens_grid(data, n=None):
    if isinstance(data, dict):
        if n is None:
            max_r = max((r for r, _ in data.keys()), default=-1)
            max_c = max((c for _, c in data.keys()), default=-1)
            n = max(max_r, max_c) + 1
        grid = [[None for _ in range(n)] for _ in range(n)]
        for (r, c), v in data.items():
            grid[r][c] = v
        return grid

    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError('givens must be a dict or 2D list.')

    grid = [row[:] for row in data]
    if n is not None and (len(grid) != n or any(len(row) != n for row in grid)):
        raise ValueError('givens grid must be n x n.')
    return grid


def _givens_grid_to_dict(givens_grid):
    ret = {}
    for r, row in enumerate(givens_grid):
        for c, v in enumerate(row):
            if v is not None:
                ret[(r, c)] = v
    return ret


def normalize_region_grid(data, n=None):
    """
    Accept either:
    - region ID grid: list[list[int]]
    - region groups: list[list[tuple[int,int]]]
    - wrapped dict: {'region': ...} / {'data': ...} / {'regions': ...}
    """
    if isinstance(data, dict):
        data = data.get('region', data.get('data', data.get('regions', data)))

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
                linewidth=0.9,
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


def _draw_numbers(ax, n, givens_grid, answer=None):
    if answer is None:
        # puzzle image: givens only in black
        for r in range(n):
            for c in range(n):
                val = givens_grid[r][c]
                if val is not None:
                    ax.text(c, r, str(val), ha='center', va='center', fontsize=39 if n <= 5 else 26, fontweight='bold', color=COLOR_GIVEN_TEXT, zorder=5)
        return

    # answer image: givens black, filled cells blue
    for r in range(n):
        for c in range(n):
            val = answer[r][c]
            color = COLOR_GIVEN_TEXT if givens_grid[r][c] is not None else COLOR_FILL_TEXT
            ax.text(c, r, str(val), ha='center', va='center', fontsize=39 if n <= 5 else 26, fontweight='bold', color=color, zorder=5)


def draw_jigsawsudoku(region_grid, givens_grid, output_path, answer=None):
    n = len(region_grid)
    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))
    ax.set_facecolor(COLOR_BG)

    _draw_cells(ax, n)
    _draw_region_boundaries(ax, region_grid)
    _draw_numbers(ax, n, givens_grid, answer=answer)

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


def format_jigsawsudoku_to_string(region_grid, givens_grid, answer=None):
    givens_grid = _normalize_givens_grid(givens_grid, n=len(region_grid))
    lines = [f"regions={region_grid}", f"givens={_givens_grid_to_dict(givens_grid)}"]
    n = len(region_grid)
    if answer is None:
        for r in range(n):
            row_tokens = []
            for c in range(n):
                row_tokens.append(str(givens_grid[r][c]) if givens_grid[r][c] is not None else '.')
            lines.append(' '.join(row_tokens))
    else:
        for row in answer:
            lines.append(' '.join(str(v) for v in row))
    return '\n'.join(lines)


def construct_jigsawsudoku_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'jigsawsudoku'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    original = puzzle_dict['original_data']
    region_grid = normalize_region_grid(original.get('region', original), n=n)
    givens_grid = _normalize_givens_grid(original.get('data', {}), n=n)

    fig_name = f"jigsawsudoku_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_jigsawsudoku(region_grid, givens_grid, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"jigsawsudoku_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_jigsawsudoku(region_grid, givens_grid, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'jigsawsudoku'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_jigsawsudoku_to_string(region_grid, givens_grid)
    output_dict['answer_str'] = format_jigsawsudoku_to_string(region_grid, givens_grid, answer=puzzle_dict['answer'])

    return output_dict


def test_observation(observation, gt_observation):
    """Test if observation matches gt_observation. Region IDs may be permuted; data must match exactly."""
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
    return


def get_observation(data):
    data = normalize_size_keys(data)
    n = data['column/row']
    original = data['original_data']
    region_grid = normalize_region_grid(original.get('region', original), n=n)
    givens_grid = _normalize_givens_grid(original.get('data', {}), n=n)
    return {
        'region': [row[:] for row in region_grid],
        'data': [row[:] for row in givens_grid],
    }


def return_data():
    ref_puzzle_dict = {
        'column/row': 5,
        'level': 'easy',
        'original_data': {
            'region': [
                [0, 1, 1, 2, 2],
                [0, 1, 1, 2, 2],
                [0, 3, 1, 4, 2],
                [0, 3, 4, 4, 4],
                [0, 3, 3, 3, 4],
            ],
            # 'data': {
            #     (0, 1): 4,
            #     (1, 2): 5,
            #     (2, 0): 2,
            #     (2, 2): 1,
            #     (2, 4): 5,
            #     (3, 2): 2,
            #     (4, 3): 2,
            # },
            'data': [
                [None, 4, None, None, None],
                [None, None, 5, None, None],
                [2, None, 1, None, 5],
                [None, None, 2, None, None],
                [None, None, None, 2, None],
            ]
        },
        'answer': [
            [5, 4, 3, 1, 2],
            [1, 2, 5, 3, 4],
            [2, 3, 1, 4, 5],
            [4, 1, 2, 5, 3],
            [3, 5, 4, 2, 1],
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
                'region': [
                    [0, 0, 1, 1, 1],
                    [0, 0, 0, 1, 1],
                    [2, 2, 3, 3, 3],
                    [2, 2, 2, 3, 3],
                    [4, 4, 4, 4, 4],
                ],
                # 'data': {
                #     (0, 4): 2,
                #     (1, 1): 2,
                #     (1, 2): 4,
                #     (1, 3): 1,
                #     (3, 1): 1,
                #     (3, 2): 3,
                #     (3, 3): 5,
                #     (4, 0): 3,
                # },
                'data': [
                    [None, None, None, None, 2],
                    [None, 2, 4, 1, None],
                    [None, None, None, None, None],
                    [None, 1, 3, 5, None],
                    [3, None, None, None, None],
                ]
            },
            'answer': [
                [1, 3, 5, 4, 2],
                [5, 2, 4, 1, 3],
                [4, 5, 2, 3, 1],
                [2, 1, 3, 5, 4],
                [3, 4, 1, 2, 5],
            ],
            'id': 'example_0',
            'rules': RULES,
        }
    ]
    for puzzle in puzzles:
        puzzle['observation'] = get_observation(puzzle)

    return ref_puzzle_dict, puzzles


if __name__ == '__main__':
    ref_puzzle_dict, puzzles = return_data()
    ret = construct_jigsawsudoku_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_jigsawsudoku_data(puzzle)
    print(ret)
