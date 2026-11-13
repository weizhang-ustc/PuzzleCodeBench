import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


RULES = '''
**Core Rules:**
Fill some cells as water so that:
1. Each region is either empty or filled up to one consistent water level.
2. If a cell in a region is water, then all cells of that region below it are also water.
3. Row clues indicate exactly how many water cells are in each row.
4. Column clues indicate exactly how many water cells are in each column.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has three parts:
   - `region`: region ID grid as list of lists.
   - `row_water_counts`: list from top row to bottom row.
   - `col_water_counts`: list from left column to right column.
4. **Answer:** same-sized grid using `'W'` for water cells and `None` for non-water cells.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_GRID = '#6A6A6A'
COLOR_FRAME = '#000000'
COLOR_REGION_BORDER = '#000000'
COLOR_WATER = '#86B3DE'
COLOR_CLUE = '#000000'
REGION_LINE_WIDTH = 3.6


def _is_water(value):
    return value in {'W', 'w', 'B', '#', 1, True}


def _normalize_counts(original_data):
    row_counts = original_data.get('row_water_counts')
    col_counts = original_data.get('col_water_counts')
    if row_counts is None:
        row_counts = original_data.get('L_nums')
    if col_counts is None:
        col_counts = original_data.get('U_nums')
    if row_counts is None or col_counts is None:
        raise ValueError("original_data must include row_water_counts and col_water_counts.")
    return list(row_counts), list(col_counts)


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
                edgecolor=COLOR_GRID,
                linewidth=0.8,
                zorder=1,
            )
            ax.add_patch(rect)


def _draw_region_boundaries(ax, region_grid):
    n = len(region_grid)
    for i in range(n + 1):
        ax.plot([-0.5, n - 0.5], [i - 0.5, i - 0.5], color=COLOR_GRID, linewidth=1.0, zorder=2)
        ax.plot([i - 0.5, i - 0.5], [-0.5, n - 0.5], color=COLOR_GRID, linewidth=1.0, zorder=2)

    for r in range(n):
        for c in range(n):
            rid = region_grid[r][c]
            if c + 1 < n and region_grid[r][c + 1] != rid:
                x = c + 0.5
                ax.plot([x, x], [r - 0.5, r + 0.5], color=COLOR_REGION_BORDER, linewidth=REGION_LINE_WIDTH, zorder=4)
            if r + 1 < n and region_grid[r + 1][c] != rid:
                y = r + 0.5
                ax.plot([c - 0.5, c + 0.5], [y, y], color=COLOR_REGION_BORDER, linewidth=REGION_LINE_WIDTH, zorder=4)

    x0, x1 = -0.5, n - 0.5
    y0, y1 = -0.5, n - 0.5
    frame_style = dict(color=COLOR_FRAME, linewidth=REGION_LINE_WIDTH, zorder=5, clip_on=False, solid_capstyle='butt')
    ax.plot([x0, x1], [y0, y0], **frame_style)
    ax.plot([x0, x1], [y1, y1], **frame_style)
    ax.plot([x0, x0], [y0, y1], **frame_style)
    ax.plot([x1, x1], [y0, y1], **frame_style)


def _draw_water(ax, answer_grid):
    n = len(answer_grid)
    for r in range(n):
        for c in range(n):
            if _is_water(answer_grid[r][c]):
                rect = patches.Rectangle(
                    (c - 0.5, r - 0.5),
                    1,
                    1,
                    facecolor=COLOR_WATER,
                    edgecolor=COLOR_GRID,
                    linewidth=1.1,
                    zorder=2.5,
                )
                ax.add_patch(rect)


def _draw_side_clues(ax, row_counts, col_counts):
    for r, val in enumerate(row_counts):
        ax.text(
            -1.08,
            r,
            str(val),
            ha='center',
            va='center',
            fontsize=26,
            fontweight='bold',
            color=COLOR_CLUE,
            zorder=8,
            clip_on=False,
        )
    for c, val in enumerate(col_counts):
        ax.text(
            c,
            -1.08,
            str(val),
            ha='center',
            va='center',
            fontsize=26,
            fontweight='bold',
            color=COLOR_CLUE,
            zorder=8,
            clip_on=False,
        )


def draw_aquarium(region_grid, row_counts, col_counts, output_path, answer=None):
    n = len(region_grid)
    fig, ax = plt.subplots(figsize=(n + 1.8, n + 1.8))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_cells(ax, n)
    if answer is not None:
        _draw_water(ax, answer)
    _draw_region_boundaries(ax, region_grid)
    _draw_side_clues(ax, row_counts, col_counts)

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


def format_aquarium_to_string(region_grid, row_counts, col_counts, answer=None):
    lines = [
        f"region={region_grid}",
        f"row_water_counts={row_counts}",
        f"col_water_counts={col_counts}",
    ]
    n = len(region_grid)
    if answer is not None:
        for r in range(n):
            row_tokens = []
            for c in range(n):
                row_tokens.append('W' if _is_water(answer[r][c]) else '.')
            lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_aquarium_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'aquarium'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    original = puzzle_dict['original_data']
    region_grid = _normalize_region_grid(original['region'], n=n)
    row_counts, col_counts = _normalize_counts(original)

    fig_name = f"aquarium_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_aquarium(region_grid, row_counts, col_counts, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"aquarium_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_aquarium(
        region_grid,
        row_counts,
        col_counts,
        output_path=os.path.join(output_dir, f'{answer_fig_name}.png'),
        answer=puzzle_dict['answer'],
    )

    output_dict = {'puzzle': 'aquarium'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_aquarium_to_string(region_grid, row_counts, col_counts)
    output_dict['answer_str'] = format_aquarium_to_string(region_grid, row_counts, col_counts, answer=puzzle_dict['answer'])
    return output_dict


def _check_counts(answer, row_counts, col_counts):
    n = len(answer)
    for r in range(n):
        if sum(1 for c in range(n) if _is_water(answer[r][c])) != row_counts[r]:
            return False
    for c in range(n):
        if sum(1 for r in range(n) if _is_water(answer[r][c])) != col_counts[c]:
            return False
    return True


def _check_region_levels(region_grid, answer):
    n = len(region_grid)
    region_cells = {}
    for r in range(n):
        for c in range(n):
            rid = region_grid[r][c]
            region_cells.setdefault(rid, []).append((r, c))

    for rid, cells in region_cells.items():
        water_rows = [r for r, c in cells if _is_water(answer[r][c])]
        if not water_rows:
            continue
        level = min(water_rows)
        for r, c in cells:
            if r >= level and not _is_water(answer[r][c]):
                return False
            if r < level and _is_water(answer[r][c]):
                return False
    return True


def test_observation(observation, gt_observation):
    """Test if observation matches groundtruth. Region IDs may be permuted (0<->1 etc)."""
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
    """Test if answer matches gt_answer."""
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
    row_counts = observation.get('row_water_counts')
    col_counts = observation.get('col_water_counts')
    if region_grid is None or row_counts is None or col_counts is None:
        return False

    n = len(region_grid)
    if len(answer) != n or len(row_counts) != n or len(col_counts) != n:
        return False
    for row in answer:
        if len(row) != n:
            return False

    if not _check_counts(answer, row_counts, col_counts):
        return False
    if not _check_region_levels(region_grid, answer):
        return False

    if gt_answer is None:
        return True
    return answer == gt_answer


def get_observation(data):
    data = normalize_size_keys(data)
    n = data['column/row']
    original = data['original_data']
    region_grid = _normalize_region_grid(original['region'], n=n)
    row_counts, col_counts = _normalize_counts(original)
    return {
        'region': region_grid,
        'row_water_counts': row_counts,
        'col_water_counts': col_counts,
    }


def return_data():
    ref_puzzle_dict = {
        'column/row': 6,
        'level': 'easy',
        'original_data': {
            'region': [
                [0, 0, 0, 1, 1, 1],
                [0, 2, 2, 3, 3, 1],
                [0, 0, 2, 2, 3, 1],
                [4, 0, 0, 3, 3, 3],
                [4, 5, 5, 5, 5, 3],
                [4, 4, 5, 5, 5, 5],
            ],
            'row_water_counts': [3, 1, 5, 2, 1, 4],
            'col_water_counts': [1, 2, 3, 3, 2, 5],
        },
        'answer': [
            [None, None, None, 'W', 'W', 'W'],
            [None, None, None, None, None, 'W'],
            ['W', 'W', 'W', 'W', None, 'W'],
            [None, 'W', 'W', None, None, None],
            [None, None, None, None, None, 'W'],
            [None, None, 'W', 'W', 'W', 'W'],
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
                    [0, 0, 0, 0, 0, 1],
                    [2, 3, 3, 0, 0, 1],
                    [2, 3, 3, 3, 1, 1],
                    [2, 4, 5, 3, 1, 1],
                    [2, 4, 5, 3, 1, 1],
                    [2, 4, 3, 3, 3, 1],
                ],
                'row_water_counts': [5, 2, 1, 5, 5, 5],
                'col_water_counts': [5, 1, 4, 5, 5, 3],
            },
            'answer': [
                ['W', 'W', 'W', 'W', 'W', None],
                [None, None, None, 'W', 'W', None],
                ['W', None, None, None, None, None],
                ['W', None, 'W', 'W', 'W', 'W'],
                ['W', None, 'W', 'W', 'W', 'W'],
                ['W', None, 'W', 'W', 'W', 'W'],
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
    ret = construct_aquarium_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_aquarium_data(puzzle)
    print(ret)
