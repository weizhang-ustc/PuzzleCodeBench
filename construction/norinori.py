import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# Shade some cells so that:
# 1. Each region contains exactly 2 shaded cells.
# 2. Every shaded cell belongs to a domino (two orthogonally adjacent shaded cells).
# 3. Different dominoes cannot touch orthogonally (diagonal touching is allowed).
# 4. Dominoes may cross region borders.
# 
# **Coordinates & Output:**
# 1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
# 2. `row` increases top-to-bottom, `col` increases left-to-right.
# 3. **Observation:** a list of lists describing region IDs for every cell.
#    Example: `[[0, 0, 1], [0, 2, 2], [3, 3, 2]]`
# 4. **Answer:** a same-sized grid, using `'S'` for shaded cells and `None` for unshaded cells.
# '''

RULES = '''
**Core Rules:**
Shade some cells so that:
1. Each region contains exactly 2 shaded cells.
2. Every shaded cell belongs to a domino (two orthogonally adjacent shaded cells).
3. Different dominoes cannot touch orthogonally (diagonal touching is allowed).
4. Dominoes may cross region borders.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has one part:
   - `data`: region ID grid as `N x N` list of lists.
4. **Answer:** a same-sized grid, using `'S'` for shaded cells and `None` for unshaded cells.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_SHADED = '#A9A9A9'
COLOR_SHADED_EDGE = '#7A7A7A'
COLOR_GRID_THIN = '#5A5A5A'
COLOR_REGION_BORDER = '#000000'
REGION_LINE_WIDTH = 3.6


def regions_to_region_id_grid(region_groups, n=None):
    """
    Convert region groups -> region ID grid.

    Input (region_groups):
    [
      [(0,0), (0,1)],
      [(0,2), (1,2)],
      ...
    ]

    Output (region ID grid):
    [
      [0, 0, 1, ...],
      [2, 2, 1, ...],
      ...
    ]
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

    Input (region ID grid):
    [
      [0, 0, 1],
      [2, 2, 1],
      [2, 3, 3],
    ]

    Output (region_groups):
    [
      [(0,0), (0,1)],
      [(0,2), (1,2)],
      [(1,0), (1,1), (2,0)],
      [(2,1), (2,2)],
    ]
    """
    groups = {}
    n = len(region_grid)
    for r in range(n):
        for c in range(len(region_grid[r])):
            rid = region_grid[r][c]
            if rid is None:
                continue
            groups.setdefault(rid, []).append((r, c))

    ordered_ids = sorted(groups.keys())
    return [groups[rid] for rid in ordered_ids]


def normalize_region_grid(data, n=None):
    """
    Accept either:
    - new format: region ID grid (list[list[int]])
    - old format: list of regions, each region is list[(r, c)]
    """
    if isinstance(data, dict):
        data = data.get('data', data.get('regions', data))

    if not isinstance(data, list) or not data:
        raise ValueError('Region data must be a non-empty list.')

    # New format: 2D grid of region ids
    if isinstance(data[0], list) and data[0] and not isinstance(data[0][0], tuple):
        return [row[:] for row in data]

    # Old format: list of coordinate groups
    return regions_to_region_id_grid(data, n=n)


def _draw_cells(ax, n, answer=None):
    for r in range(n):
        for c in range(n):
            is_shaded = answer is not None and answer[r][c] == 'S'
            face = COLOR_SHADED if is_shaded else COLOR_CELL

            rect = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                facecolor=face,
                edgecolor=COLOR_SHADED_EDGE if is_shaded else COLOR_GRID_THIN,
                linewidth=0.8,
                zorder=1,
            )
            ax.add_patch(rect)


def _draw_region_boundaries(ax, region_grid):
    n = len(region_grid)

    # Thin base grid
    for i in range(n + 1):
        ax.plot([-0.5, n - 0.5], [i - 0.5, i - 0.5], color=COLOR_GRID_THIN, linewidth=1.0, zorder=2)
        ax.plot([i - 0.5, i - 0.5], [-0.5, n - 0.5], color=COLOR_GRID_THIN, linewidth=1.0, zorder=2)

    # Thick region boundaries between different IDs
    for r in range(n):
        for c in range(n):
            curr = region_grid[r][c]
            if c + 1 < n and region_grid[r][c + 1] != curr:
                x = c + 0.5
                ax.plot([x, x], [r - 0.5, r + 0.5], color=COLOR_REGION_BORDER, linewidth=REGION_LINE_WIDTH, zorder=3)
            if r + 1 < n and region_grid[r + 1][c] != curr:
                y = r + 0.5
                ax.plot([c - 0.5, c + 0.5], [y, y], color=COLOR_REGION_BORDER, linewidth=REGION_LINE_WIDTH, zorder=3)

    # Outer frame: draw with line segments (same style as region boundaries)
    x0, x1 = -0.5, n - 0.5
    y0, y1 = -0.5, n - 0.5
    frame_style = dict(color=COLOR_REGION_BORDER, linewidth=REGION_LINE_WIDTH, zorder=4, clip_on=False, solid_capstyle='butt')
    ax.plot([x0, x1], [y0, y0], **frame_style)  # top
    ax.plot([x0, x1], [y1, y1], **frame_style)  # bottom
    ax.plot([x0, x0], [y0, y1], **frame_style)  # left
    ax.plot([x1, x1], [y0, y1], **frame_style)  # right


def draw_norinori(region_grid, output_path, answer=None):
    n = len(region_grid)
    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))
    ax.set_facecolor(COLOR_BG)

    _draw_cells(ax, n, answer=answer)
    _draw_region_boundaries(ax, region_grid)

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


def format_norinori_to_string(region_grid, answer=None):
    n = len(region_grid)
    lines = []
    for r in range(n):
        row_tokens = []
        for c in range(n):
            if answer is not None and answer[r][c] == 'S':
                row_tokens.append(f"{region_grid[r][c]}S")
            else:
                row_tokens.append(str(region_grid[r][c]))
        lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_norinori_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'norinori'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    region_grid = normalize_region_grid(puzzle_dict['original_data'], n=n)

    fig_name = f"norinori_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_norinori(region_grid, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"norinori_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_norinori(region_grid, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'norinori'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_norinori_to_string(region_grid)
    output_dict['answer_str'] = format_norinori_to_string(region_grid, answer=puzzle_dict['answer'])

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
    # Recommended original_data format: region ID grid (list of lists)
    ref_puzzle_dict = {
        'column/row': 6,
        'level': 'easy',
        'original_data': {
            'data': [
                [0, 0, 1, 1, 1, 2],
                [0, 0, 0, 3, 3, 2],
                [0, 4, 0, 0, 3, 3],
                [4, 4, 5, 5, 7, 3],
                [4, 5, 5, 6, 7, 3],
                [4, 4, 5, 6, 7, 7],
            ],
        },
        'answer': [
            [None, None, 'S', 'S', None, 'S'],
            [None, None, None, None, None, 'S'],
            ['S', None, 'S', None, 'S', None],
            ['S', None, 'S', None, 'S', None],
            [None, 'S', None, 'S', None, 'S'],
            [None, 'S', None, 'S', None, 'S'],
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
                'data': [
                    [0, 1, 1, 1, 1, 1],
                    [0, 2, 2, 2, 1, 1],
                    [0, 0, 3, 2, 4, 4],
                    [0, 0, 3, 2, 2, 4],
                    [0, 0, 3, 6, 6, 7],
                    [5, 5, 5, 6, 6, 7],
                ],
            },
            'answer': [
                [None, 'S', None, 'S', None, None],
                [None, 'S', None, 'S', None, None],
                ['S', None, 'S', None, 'S', 'S'],
                ['S', None, 'S', None, None, None],
                [None, None, None, 'S', None, 'S'],
                ['S', 'S', None, 'S', None, 'S'],
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
    ret = construct_norinori_data(ref_puzzle_dict)
    # ret = construct_norinori_data(puzzles[0])
    for puzzle in puzzles:
        ret = construct_norinori_data(puzzle)
    print(ret)
