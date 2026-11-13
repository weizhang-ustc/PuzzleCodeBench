import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# Shade some cells black guided by number clues.
# 
# 1. Each clue number counts how many white cells are visible from that clue cell, including the clue cell itself.
# 2. Visibility extends orthogonally (up/down/left/right) until blocked by a black cell or the grid border.
# 3. Clue cells are always white and cannot be shaded black.
# 4. All white cells must form one orthogonally connected group.
# 5. Black cells cannot touch orthogonally (diagonal touching is allowed).
# 
# **Coordinates & Output:**
# 1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
# 2. `row` increases top-to-bottom, `col` increases left-to-right.
# 3. **Observation:** dictionary of clue cells only.
#    Example: `{(1, 0): 4, (2, 1): 9, ...}`
# 4. **Answer:** full solved grid (same shape as board), where black cells are marked by `'B'`.
# '''

RULES = '''
**Core Rules:**
Shade some cells black guided by number clues.
1. Each clue number counts how many white cells are visible from that clue cell, including itself.
2. Visibility extends orthogonally until blocked by a black cell or the grid border.
3. Clue cells are always white and cannot be shaded black.
4. All white cells must form one orthogonally connected group.
5. Black cells cannot touch orthogonally.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has one part:
   - `data`: `N x N` clue 2D list (`int` for clue cells, `None` otherwise).
4. **Answer:** full solved `N x N` 2D list where black cells are `'B'`, initial clue numbers are kept, and other empty cells are `None`.
'''


COLOR_CELL = '#FFFFFF'
COLOR_GRID = '#1F1F1F'
COLOR_BLACK = '#111111'
COLOR_CLUE_CIRCLE_FACE = '#FFFFFF'
COLOR_CLUE_CIRCLE_EDGE = '#111111'
COLOR_TEXT = '#111111'


def _is_black_cell(value):
    return value == 'B'


def _draw_board_base(ax, n):
    for r in range(n):
        for c in range(n):
            rect = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                facecolor=COLOR_CELL,
                edgecolor=COLOR_GRID,
                linewidth=1.2,
                zorder=1,
            )
            ax.add_patch(rect)


def _draw_black_cells(ax, answer_grid):
    n = len(answer_grid)
    for r in range(n):
        for c in range(n):
            if _is_black_cell(answer_grid[r][c]):
                rect = patches.Rectangle(
                    (c - 0.5, r - 0.5),
                    1,
                    1,
                    facecolor=COLOR_BLACK,
                    edgecolor=COLOR_GRID,
                    linewidth=1.2,
                    zorder=2,
                )
                ax.add_patch(rect)


def _draw_clues(ax, clue_grid):
    n = len(clue_grid)
    for r in range(n):
        for c in range(n):
            val = clue_grid[r][c]
            if isinstance(val, int):
                circle = patches.Circle(
                    (c, r),
                    radius=0.38,
                    facecolor=COLOR_CLUE_CIRCLE_FACE,
                    edgecolor=COLOR_CLUE_CIRCLE_EDGE,
                    linewidth=1.6,
                    zorder=4,
                )
                ax.add_patch(circle)
                ax.text(
                    c,
                    r,
                    str(val),
                    ha='center',
                    va='center',
                    fontsize=22,
                    fontweight='bold',
                    color=COLOR_TEXT,
                    zorder=5,
                )


def draw_kurodoko(grid, output_path, answer=None):
    n = len(grid)
    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))

    _draw_board_base(ax, n)
    if answer is not None:
        _draw_black_cells(ax, answer)
    _draw_clues(ax, grid)

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
        spine.set_edgecolor(COLOR_GRID)
        spine.set_linewidth(1.4)

    plt.tight_layout()
    save_square_figure(fig, output_path)
    plt.close()


def format_kurodoko_to_string(grid, answer_grid=None):
    n = len(grid)
    lines = []
    for r in range(n):
        row_tokens = []
        for c in range(n):
            if answer_grid is not None and _is_black_cell(answer_grid[r][c]):
                row_tokens.append('B')
            elif isinstance(grid[r][c], int):
                row_tokens.append(str(grid[r][c]))
            else:
                row_tokens.append('.')
        lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_kurodoko_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'kurodoko'))
    os.makedirs(output_dir, exist_ok=True)

    fig_name = f"kurodoko_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_kurodoko(
        puzzle_dict['original_data']['data'],
        output_path=os.path.join(output_dir, f'{fig_name}.png'),
    )

    answer_fig_name = f"kurodoko_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_kurodoko(
        puzzle_dict['original_data']['data'],
        output_path=os.path.join(output_dir, f'{answer_fig_name}.png'),
        answer=puzzle_dict['answer'],
    )

    output_dict = {'puzzle': 'kurodoko'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_kurodoko_to_string(puzzle_dict['original_data']['data'])
    output_dict['answer_str'] = format_kurodoko_to_string(
        puzzle_dict['original_data']['data'],
        answer_grid=puzzle_dict['answer'],
    )

    return output_dict


def test_observation(observation, gt_observation):
    """Test if observation matches gt_observation."""
    return observation == gt_observation


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
    grid = data['original_data']['data']
    clue_grid = [[None for _ in range(n)] for _ in range(n)]
    for r in range(n):
        for c in range(n):
            if isinstance(grid[r][c], int):
                clue_grid[r][c] = grid[r][c]
    return {'data': clue_grid}


def return_data():
    ref_puzzle_dict = {
        'column/row': 5,
        'level': 'easy',
        'original_data': {
            'data': [
                [None, None, None, 3, None],
                [4, None, None, None, None],
                [None, 9, None, 7, None],
                [None, None, None, None, 7],
                [None, 6, None, None, None],
            ],
        },
        'answer': [
            ['B', None, None, 3, 'B'],
            [4, None, None, 'B', None],
            [None, 9, None, 7, None],
            ['B', None, None, None, 7],
            [None, 6, 'B', None, None],
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
                    [None, None, None, 4, None],
                    [6, None, 4, None, None],
                    [None, None, None, None, None],
                    [None, None, 5, None, 9],
                    [None, 6, None, None, None],
                ],
            },
            'answer': [
                ['B', None, None, 4, None],
                [6, None, 4, 'B', None],
                [None, None, 'B', None, None],
                [None, None, 5, None, 9],
                [None, 6, 'B', None, None],
            ],
            'id': 'example_0',
            'rules': RULES,
        },
        {
            'column/row': 7,
            'level': 'easy',
            'original_data': {
                'data': [
                    [None, 7, None, None, None, None, None],
                    [None, None, None, 8, 8, None, 8],
                    [None, None, None, None, None, None, None],
                    [7, None, None, 6, None, None, 2],
                    [None, None, None, None, None, None, None],
                    [8, None, 8, 9, None, None, None],
                    [None, None, None, None, None, 9, None]
                ],
            },
            'answer': [
                [None, 7, 'B', None, 'B', None, None],
                [None, None, None, 8, 8, None, 8],
                [None, None, None, 'B', None, None, 'B'],
                [7, None, None, 6, 'B', None, 2],
                ['B', None, 'B', None, None, None, 'B'],
                [8, None, 8, 9, None, None, None],
                [None, 'B', None, 'B', None, 9, None]
            ],
            'id': 'example_1',
            'rules': RULES,
        },
        {
            'column/row': 10,
            'level': 'easy',
            'original_data': {
                'data': [
                    [None, 6, None, None, None, 9, None, None, 5, None],
                    [None, 6, None, None, None, None, None, None, None, None],
                    [None, None, None, 5, None, None, None, None, 4, None],
                    [None, None, None, None, None, None, None, 2, None, None],
                    [None, None, None, None, None, None, 7, None, None, 10],
                    [2, None, None, 6, None, None, None, None, None, None],
                    [None, None, 11, None, None, None, None, None, None, None],
                    [None, 5, None, None, None, None, 6, None, None, None],
                    [None, None, None, None, None, None, None, None, 2, None],
                    [None, 13, None, None, 12, None, None, None, 11, None],
                ],
            },
            'answer': [
                ['B', 6, None, 'B', None, 9, 'B', None, 5, None],
                [None, 6, 'B', None, None, None, None, None, None, None],
                ['B', None, None, 5, 'B', None, None, 'B', 4, None],
                [None, None, None, None, None, None, 'B', 2, 'B', None],
                ['B', None, None, 'B', None, None, 7, None, None, 10],
                [2, 'B', None, 6, None, None, None, 'B', None, 'B'],
                [None, None, 11, None, 'B', None, 'B', None, None, None],
                ['B', 5, None, 'B', None, None, 6, None, 'B', None],
                [None, None, None, None, None, 'B', None, 'B', 2, 'B'],
                [None, 13, None, None, 12, None, None, None, 11, None],
            ],
            'id': 'example_2',
            'rules': RULES,
        },
        {
            'column/row': 10,
            'level': 'easy',
            'original_data': {
                'data': [
                    [None, 4, None, None, None, None, None, None, None, None],
                    [None, None, 13, None, None, None, None, 12, None, None],
                    [None, None, 15, None, None, 11, 13, None, None, None],
                    [None, None, None, None, None, None, 7, None, 13, 8],
                    [None, 8, None, 6, None, None, None, None, None, None],
                    [None, None, None, None, None, None, 4, None, 10, None],
                    [7, 4, None, 2, None, None, None, None, None, None],
                    [None, None, None, 7, 7, None, None, 4, None, None],
                    [None, None, 5, None, None, None, None, 6, None, None],
                    [None, None, None, None, None, None, None, None, 11, None],
                ],
            },
            'answer': [
                ['B', 4, None, None, None, 'B', None, None, None, None],
                [None, 'B', 13, None, None, None, None, 12, None, None],
                [None, None, 15, None, None, 11, 13, None, None, None],
                ['B', None, None, 'B', None, 'B', 7, None, 13, 8],
                [None, 8, None, 6, None, None, 'B', None, None, None],
                [None, 'B', None, 'B', None, None, 4, 'B', 10, 'B'],
                [7, 4, 'B', 2, 'B', None, None, None, None, None],
                [None, None, None, 7, 7, None, 'B', 4, None, 'B'],
                [None, None, 5, 'B', None, 'B', None, 6, None, None],
                [None, 'B', None, None, 'B', None, None, 'B', 11, None],
            ],
            'id': 'example_3',
            'rules': RULES,
        },
    ]
    for puzzle in puzzles:
        puzzle['observation'] = get_observation(puzzle)

    return ref_puzzle_dict, puzzles


if __name__ == '__main__':
    ref_puzzle_dict, puzzles = return_data()
    ret = construct_kurodoko_data(ref_puzzle_dict)
    # ret = construct_kurodoko_data(puzzles[2])
    for puzzle in puzzles:
        ret = construct_kurodoko_data(puzzle)
    print(ret)
