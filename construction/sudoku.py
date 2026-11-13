import os
import re
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# Fill the grid with numbers so that:
# 1. Every row contains each value `1..N` exactly once.
# 2. Every column contains each value `1..N` exactly once.
# 3. Every subgrid contains each value `1..N` exactly once.
# 4. Subgrid size is configurable by unit `(r x c)`:
#    - unit `3` means `3x3` subgrids (classic `9x9`).
#    - unit `3x4` means `3x4` subgrids (grid size `12x12`).
#    - unit `4x4` means `4x4` subgrids (grid size `16x16`).
# 5. Given cells are fixed.
# 
# **Coordinates & Output:**
# 1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
# 2. `row` increases top-to-bottom, `col` increases left-to-right.
# 3. **Observation** has one part:
#    - `data`: initial number grid as list of lists, using `None` for blank cells.
# 4. **Answer:** full solved number grid as list of lists.
# '''

RULES = '''
**Core Rules:**
Fill the grid with numbers so that:
1. Every row contains each value `1..N` exactly once.
2. Every column contains each value `1..N` exactly once.
3. Every subgrid contains each value `1..N` exactly once.
4. Subgrid size is configurable by unit `(r x c)`:
   - unit `3` means `3x3` subgrids (classic `9x9`).
   - unit `3x4` means `3x4` subgrids (grid size `12x12`).
   - unit `4x4` means `4x4` subgrids (grid size `16x16`).
5. Given cells are fixed.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has two parts:
   - `data`: initial number grid as list of lists, using `None` for blank cells.
   - `unit`: subgrid shape string, e.g. `'3x3'`, `'3x4'`, `'4x4'`.
4. **Answer:** full solved number grid as list of lists.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_GRID_THIN = '#666666'
COLOR_REGION_BORDER = '#000000'
COLOR_GIVEN_TEXT = '#111111'
COLOR_FILL_TEXT = '#1E73BE'
REGION_LINE_WIDTH = 3.6


def _parse_unit(value):
    """
    Parse unit spec to (unit_rows, unit_cols).
    Supports:
    - int: 3 => (3, 3)
    - tuple/list: (3,4)
    - string: "3x4", "3*4", "3,4", "3 4"
    - dict: {"rows":3,"cols":4} / {"r":3,"c":4}
    """
    if isinstance(value, int):
        return value, value

    if isinstance(value, (tuple, list)) and len(value) == 2:
        return int(value[0]), int(value[1])

    if isinstance(value, str):
        m = re.findall(r'\d+', value)
        if len(m) == 1:
            x = int(m[0])
            return x, x
        if len(m) >= 2:
            return int(m[0]), int(m[1])

    if isinstance(value, dict):
        if 'rows' in value and 'cols' in value:
            return int(value['rows']), int(value['cols'])
        if 'r' in value and 'c' in value:
            return int(value['r']), int(value['c'])

    raise ValueError(f'Invalid unit spec: {value}')


def _get_unit_and_size(puzzle_dict):
    grid = puzzle_dict['original_data']['data']
    n = len(grid)
    for row in grid:
        if len(row) != n:
            raise ValueError('Sudoku grid must be square.')

    original = puzzle_dict['original_data']
    # Priority: explicit unit in original_data, else column/row field.
    unit_spec = original.get('unit', puzzle_dict.get('column/row'))
    unit_r, unit_c = _parse_unit(unit_spec)
    if unit_r <= 0 or unit_c <= 0:
        raise ValueError('Unit sizes must be positive.')
    if n % unit_r != 0 or n % unit_c != 0:
        raise ValueError(f'Grid size {n} is not divisible by unit {unit_r}x{unit_c}.')
    return unit_r, unit_c, n


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


def _draw_subgrid_boundaries(ax, n, unit_r, unit_c):
    # Thin base grid
    for i in range(n + 1):
        ax.plot([-0.5, n - 0.5], [i - 0.5, i - 0.5], color=COLOR_GRID_THIN, linewidth=1.0, zorder=2)
        ax.plot([i - 0.5, i - 0.5], [-0.5, n - 0.5], color=COLOR_GRID_THIN, linewidth=1.0, zorder=2)

    # Thick subgrid lines
    for r in range(0, n + 1, unit_r):
        y = r - 0.5
        ax.plot([-0.5, n - 0.5], [y, y], color=COLOR_REGION_BORDER, linewidth=REGION_LINE_WIDTH, zorder=3)
    for c in range(0, n + 1, unit_c):
        x = c - 0.5
        ax.plot([x, x], [-0.5, n - 0.5], color=COLOR_REGION_BORDER, linewidth=REGION_LINE_WIDTH, zorder=3)

    # Strong outer frame
    x0, x1 = -0.5, n - 0.5
    y0, y1 = -0.5, n - 0.5
    frame_style = dict(color=COLOR_REGION_BORDER, linewidth=REGION_LINE_WIDTH, zorder=4, clip_on=False, solid_capstyle='butt')
    ax.plot([x0, x1], [y0, y0], **frame_style)
    ax.plot([x0, x1], [y1, y1], **frame_style)
    ax.plot([x0, x0], [y0, y1], **frame_style)
    ax.plot([x1, x1], [y0, y1], **frame_style)


def _draw_numbers(ax, givens_grid, answer=None):
    n = len(givens_grid)
    for r in range(n):
        for c in range(n):
            given_val = givens_grid[r][c]
            if given_val is not None:
                ax.text(c, r, str(given_val), ha='center', va='center', fontsize=39 if n <= 5 else 32, fontweight='bold', color=COLOR_GIVEN_TEXT, zorder=5)
            elif answer is not None:
                ax.text(c, r, str(answer[r][c]), ha='center', va='center', fontsize=39 if n <= 5 else 32, fontweight='bold', color=COLOR_FILL_TEXT, zorder=5)


def draw_sudoku(givens_grid, unit_r, unit_c, output_path, answer=None):
    n = len(givens_grid)
    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_cells(ax, n)
    _draw_subgrid_boundaries(ax, n, unit_r, unit_c)
    _draw_numbers(ax, givens_grid, answer=answer)

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


def format_sudoku_to_string(givens_grid, unit_r, unit_c, answer=None):
    lines = [f"unit={unit_r}x{unit_c}", f"data={givens_grid}"]
    n = len(givens_grid)
    for r in range(n):
        row = []
        for c in range(n):
            if givens_grid[r][c] is not None:
                row.append(str(givens_grid[r][c]))
            elif answer is not None:
                row.append(str(answer[r][c]))
            else:
                row.append('.')
        lines.append(' '.join(row))
    return '\n'.join(lines)


def construct_sudoku_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'sudoku'))
    os.makedirs(output_dir, exist_ok=True)

    unit_r, unit_c, n = _get_unit_and_size(puzzle_dict)
    givens_grid = [row[:] for row in puzzle_dict['original_data']['data']]

    fig_name = f"sudoku_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_sudoku(givens_grid, unit_r, unit_c, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"sudoku_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_sudoku(givens_grid, unit_r, unit_c, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'sudoku'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_sudoku_to_string(givens_grid, unit_r, unit_c)
    output_dict['answer_str'] = format_sudoku_to_string(givens_grid, unit_r, unit_c, answer=puzzle_dict['answer'])
    return output_dict


def test_observation(observation, gt_observation):
    """Givens `data` and block `unit`; exact match."""
    return observation == gt_observation


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
    if observation != gt_observation:
        return False
    if answer is None:
        return False

    data = observation.get('data')
    unit = observation.get('unit')
    if data is None or unit is None:
        return False
    unit_r, unit_c = _parse_unit(unit)

    n = len(data)
    if len(answer) != n:
        return False
    for row in answer:
        if len(row) != n:
            return False

    vals = set(range(1, n + 1))

    # Given cells fixed and value range check.
    for r in range(n):
        for c in range(n):
            v = answer[r][c]
            if v not in vals:
                return False
            if data[r][c] is not None and v != data[r][c]:
                return False

    # Row/column uniqueness.
    for r in range(n):
        if set(answer[r]) != vals:
            return False
    for c in range(n):
        if set(answer[r][c] for r in range(n)) != vals:
            return False

    # Subgrid uniqueness.
    for r0 in range(0, n, unit_r):
        for c0 in range(0, n, unit_c):
            block = []
            for r in range(r0, r0 + unit_r):
                for c in range(c0, c0 + unit_c):
                    block.append(answer[r][c])
            if set(block) != vals:
                return False

    if gt_answer is None:
        return True
    return answer == gt_answer


def get_observation(data):
    data = normalize_size_keys(data)
    unit_r, unit_c, _ = _get_unit_and_size(data)
    return {
        'data': [row[:] for row in data['original_data']['data']],
        'unit': f'{unit_r}x{unit_c}',
    }




def return_data():
    ref_puzzle_dict = {
        'column/row': 3, # unit is a 3x3 region
        'level': 'basic',
        'original_data': {
            'data': [
                [None, None, 1, None, 3, 8, None, 5, None],
                [None, None, None, None, None, None, 7, 3, 8],
                [None, None, None, None, None, 5, None, None, 9],
                [9, 1, None, None, None, 7, 4, None, None],
                [None, None, 5, 6, None, 2, 3, None, None],
                [None, None, 3, 5, None, None, None, 8, 2],
                [3, None, None, 8, None, None, None, None, None],
                [1, 4, 7, None, None, None, None, None, None],
                [None, 5, None, 2, 4, None, 1, None, None],
            ]
        },
        'answer': [
            [2, 9, 1, 7, 3, 8, 6, 5, 4],
            [5, 6, 4, 1, 2, 9, 7, 3, 8],
            [7, 3, 8, 4, 6, 5, 2, 1, 9],
            [9, 1, 2, 3, 8, 7, 4, 6, 5],
            [4, 8, 5, 6, 9, 2, 3, 7, 1],
            [6, 7, 3, 5, 1, 4, 9, 8, 2],
            [3, 2, 9, 8, 7, 1, 5, 4, 6],
            [1, 4, 7, 9, 5, 6, 8, 2, 3],
            [8, 5, 6, 2, 4, 3, 1, 9, 7],
        ],
        'id': 'ref',
        'rules': RULES,
    }
    ref_puzzle_dict['observation'] = get_observation(ref_puzzle_dict)

    puzzles = [
        {
            'column/row': 3, # unit is a 3x3 region
            'level': 'basic',
            'original_data': {
                'data': [
                    [None, 9, 5, 1, None, None, None, None, None],
                    [None, 7, 1, 9, None, None, 4, None, None],
                    [None, 6, None, None, 8, 3, None, None, None],
                    [None, None, None, 2, None, None, None, 7, 6],
                    [None, None, 4, None, 7, None, 1, None, None],
                    [6, 1, None, None, None, 9, None, None, None],
                    [None, None, None, 4, 5, None, None, 6, None],
                    [None, None, 9, None, None, 7, 8, 3, None],
                    [None, None, None, None, None, 8, 5, 4, None],
                ]
            },
            'answer': [
                [3, 9, 5, 1, 2, 4, 6, 8, 7],
                [8, 7, 1, 9, 6, 5, 4, 2, 3],
                [4, 6, 2, 7, 8, 3, 9, 1, 5],
                [9, 5, 8, 2, 4, 1, 3, 7, 6],
                [2, 3, 4, 5, 7, 6, 1, 9, 8],
                [6, 1, 7, 8, 3, 9, 2, 5, 4],
                [1, 8, 3, 4, 5, 2, 7, 6, 9],
                [5, 4, 9, 6, 1, 7, 8, 3, 2],
                [7, 2, 6, 3, 9, 8, 5, 4, 1]
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
    ret = construct_sudoku_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_sudoku_data(puzzle)
    print(ret)
