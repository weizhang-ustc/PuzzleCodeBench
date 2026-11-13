import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# Shade cells so that:
# 1. In every region, shaded cells form exactly one tetromino of size 4.
# 2. Allowed tetromino types are `L`, `I`, `T`, `S` (`O` is forbidden because 2x2 shaded blocks are forbidden).
# 3. Two orthogonally adjacent regions cannot use the same tetromino type (rotation/reflection counts as the same type).
# 4. All shaded cells in the whole grid must be orthogonally connected.
# 5. No 2x2 block can be fully shaded.
# 
# **Coordinates & Output:**
# 1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
# 2. `row` increases top-to-bottom, `col` increases left-to-right.
# 3. **Observation:** region ID grid as list of lists.
#    Example: `[[0,0,1],[0,2,2],[3,3,2]]`
# 4. **Answer:** same-sized grid using one of `L/I/T/S` for shaded cells and `None` for non-shaded cells.
# '''

RULES = '''
**Core Rules:**
Shade cells so that:
1. In every region, shaded cells form exactly one tetromino of size 4.
2. Allowed tetromino types are `L`, `I`, `T`, `S` (`O` is forbidden because 2x2 shaded blocks are forbidden).
3. Two orthogonally adjacent regions cannot use the same tetromino type (rotation/reflection counts as the same type).
4. All shaded cells in the whole grid must be orthogonally connected.
5. No 2x2 block can be fully shaded.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has one part:
   - `data`: region ID grid as `N x N` list of lists.
4. **Answer:** same-sized grid using one of `L/I/T/S` for shaded cells and `None` for non-shaded cells.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_EMPTY_ANSWER = '#FFFFFF'
COLOR_GRID_THIN = '#666666'
COLOR_REGION_BORDER = '#000000'
REGION_LINE_WIDTH = 3.6

SHAPE_COLORS = {
    'L': '#99CCFF',
    'I': '#99FF99',
    'T': '#FF9999',
    'S': '#CC99FF',
}

# canonical mini-shape previews (cell coordinates in local mini grid)
PREVIEW_SHAPES = {
    'L': [(0, 0), (1, 0), (2, 0), (2, 1)],
    'I': [(0, 0), (1, 0), (2, 0), (3, 0)],
    'T': [(0, 0), (0, 1), (0, 2), (1, 1)],
    'S': [(0, 1), (0, 2), (1, 0), (1, 1)],
}


def regions_to_region_id_grid(region_groups, n=None):
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
    groups = {}
    for r in range(len(region_grid)):
        for c in range(len(region_grid[r])):
            rid = region_grid[r][c]
            if rid is None:
                continue
            groups.setdefault(rid, []).append((r, c))
    return [groups[rid] for rid in sorted(groups.keys())]


def normalize_region_grid(data, n=None):
    if isinstance(data, dict):
        data = data.get('data', data.get('regions', data))

    if not isinstance(data, list) or not data:
        raise ValueError('Region data must be a non-empty list.')

    # region id grid
    if isinstance(data[0], list) and data[0] and not isinstance(data[0][0], tuple):
        return [row[:] for row in data]

    # region groups
    return regions_to_region_id_grid(data, n=n)


def _draw_cells(ax, n, answer=None):
    for r in range(n):
        for c in range(n):
            value = answer[r][c] if answer is not None else None
            if answer is None:
                face = COLOR_CELL
            else:
                face = SHAPE_COLORS[value] if value in SHAPE_COLORS else COLOR_EMPTY_ANSWER

            rect = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                facecolor=face,
                edgecolor=COLOR_GRID_THIN,
                linewidth=0.8,
                zorder=1,
                alpha=0.88 if value in SHAPE_COLORS else 1.0,
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


def _draw_preview_shape(ax, shape_id, origin_x, origin_y, scale=0.28, transform=None, label_y=None):
    coords = PREVIEW_SHAPES[shape_id]
    color = SHAPE_COLORS[shape_id]
    transform = transform or ax.transData

    for rr, cc in coords:
        rect = patches.Rectangle(
            (origin_x + cc * scale, origin_y + rr * scale),
            scale,
            scale,
            facecolor=color,
            edgecolor='#333333',
            linewidth=0.8,
            zorder=1,
            alpha=0.95,
            transform=transform,
            clip_on=False,
        )
        ax.add_patch(rect)

    # label
    xs = [cc * scale for _, cc in coords]
    cx = origin_x + (min(xs) + max(xs) + scale) / 2.0
    text_y = label_y if label_y is not None else (origin_y - 0.03)
    ax.text(
        cx,
        text_y,
        shape_id,
        ha='center',
        va='center',
        fontsize=8,
        fontweight='bold',
        color='#222222',
        zorder=2,
        transform=transform,
        clip_on=False,
    )


def _draw_shape_legend(ax):
    # small legend centered above top ticks (axes coordinates)
    scale = 0.036
    y = 1.12
    label_y = 1.085
    xs = [0.28, 0.38, 0.45, 0.58]
    for x, sid in zip(xs, ['L', 'I', 'T', 'S']):
        _draw_preview_shape(ax, sid, x, y, scale=scale, transform=ax.transAxes, label_y=label_y)


def draw_lits(region_grid, output_path, answer=None):
    n = len(region_grid)
    fig, ax = plt.subplots(figsize=(n + 1.0, n + 1.2))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_cells(ax, n, answer=answer)
    _draw_region_boundaries(ax, region_grid)
    _draw_shape_legend(ax)

    ticks = list(range(n))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])
    ax.set_yticklabels([str(t) for t in ticks])
    ax.xaxis.tick_top()
    ax.tick_params(axis='x', pad=2)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_clip_on(False)

    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(-0.56, n - 0.5)
    ax.invert_yaxis()
    ax.set_aspect('equal')

    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.subplots_adjust(top=0.82)
    save_square_figure(fig, output_path, vertical_shift_ratio=0.03)
    plt.close()


def format_lits_to_string(region_grid, answer=None):
    n = len(region_grid)
    lines = []
    for r in range(n):
        row_tokens = []
        for c in range(n):
            if answer is not None and answer[r][c] in SHAPE_COLORS:
                row_tokens.append(f"{region_grid[r][c]}{answer[r][c]}")
            else:
                row_tokens.append(str(region_grid[r][c]))
        lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_lits_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'lits'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    region_grid = normalize_region_grid(puzzle_dict['original_data'], n=n)

    fig_name = f"lits_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_lits(region_grid, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"lits_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_lits(region_grid, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'lits'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_lits_to_string(region_grid)
    output_dict['answer_str'] = format_lits_to_string(region_grid, answer=puzzle_dict['answer'])

    return output_dict


def test_observation(observation, gt_observation):
    """Compare only `data` (region ID grid); IDs may be permuted so normalize before ==."""

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
    region_grid = normalize_region_grid(data['original_data'], n=n)
    return {'data': [row[:] for row in region_grid]}


def return_data():
    ref_puzzle_dict = {
        'column/row': 6,
        'level': 'easy',
        'original_data': {
            'data': [
                [0, 0, 0, 0, 1, 1],
                [2, 0, 3, 3, 1, 1],
                [2, 3, 3, 3, 3, 1],
                [2, 3, 4, 1, 1, 1],
                [2, 3, 4, 4, 4, 4],
                [3, 3, 3, 3, 3, 3],
            ],
        },
        'answer': [
            [None, 'L', 'L', 'L', None, 'I'],
            ['I', 'L', None, 'T', None, 'I'],
            ['I', None, 'T', 'T', 'T', 'I'],
            ['I', None, 'L', None, None, 'I'],
            ['I', None, 'L', 'L', 'L', None],
            [None, None, None, None, None, None],
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
                    [0, 0, 0, 0, 1, 1],
                    [0, 0, 0, 1, 1, 2],
                    [3, 3, 3, 2, 2, 2],
                    [3, 2, 2, 2, 2, 4],
                    [5, 2, 5, 2, 2, 4],
                    [5, 5, 5, 4, 4, 4],
                ],
            },
            'answer': [
                ['T', 'T', 'T', None, 'S', 'S'],
                [None, 'T', None, 'S', 'S', None],
                ['L', 'L', 'L', 'T', None, None],
                ['L', None, None, 'T', 'T', 'L'],
                [None, None, 'L', 'T', None, 'L'],
                ['L', 'L', 'L', None, 'L', 'L'],
            ],
            'id': 'example_0',
            'rules': RULES,
        },
        {
            'column/row': 6,
            'level': 'easy',
            'original_data': {
                'data': [
                    [0, 0, 1, 1, 1, 1],
                    [2, 0, 0, 3, 1, 3],
                    [2, 4, 3, 3, 3, 3],
                    [2, 4, 3, 4, 5, 3],
                    [2, 4, 4, 4, 5, 3],
                    [2, 2, 4, 5, 5, 5],
                ],
            },
            'answer': [
                ['S', 'S', None, 'T', 'T', 'T'],
                [None, 'S', 'S', None, 'T', None],
                ['I', None, 'I', 'I', 'I', 'I'],
                ['I', None, None, None, 'L', None],
                ['I', 'T', 'T', 'T', 'L', None],
                ['I', None, 'T', None, 'L', 'L'],
            ],
            'id': 'example_1',
            'rules': RULES,
        },
        {
            'column/row': 8,
            'level': 'hard',
            'original_data': {
                'data': [
                    [0, 1, 1, 1, 1, 2, 2, 2],
                    [0, 0, 3, 3, 3, 3, 3, 2],
                    [0, 4, 4, 3, 5, 5, 5, 2],
                    [0, 4, 4, 3, 6, 6, 5, 2],
                    [4, 4, 3, 3, 6, 6, 5, 5],
                    [4, 4, 4, 3, 3, 6, 6, 5],
                    [4, 7, 4, 4, 4, 4, 4, 4],
                    [7, 7, 7, 8, 8, 8, 8, 4],
                ],
            },
            'answer': [
                [None, 'I', 'I', 'I', 'I', 'L', 'L', 'L'],
                ['L', 'L', None, None, None, None, None, 'L'],
                ['L', None, None, 'I', 'L', 'L', 'L', None],
                ['L', None, None, 'I', None, None, 'L', None],
                ['S', 'S', None, 'I', 'S', 'S', None, None],
                [None, 'S', 'S', 'I', None, 'S', 'S', None],
                [None, 'T', None, None, None, None, None, None],
                ['T', 'T', 'T', 'I', 'I', 'I', 'I', None],
            ],
            'id': 'example_2',
            'rules': RULES,
        }
    ]
    for puzzle in puzzles:
        puzzle['observation'] = get_observation(puzzle)

    return ref_puzzle_dict, puzzles


if __name__ == '__main__':
    ref_puzzle_dict, puzzles = return_data()
    ret = construct_lits_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_lits_data(puzzle)
    print(ret)
