import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# Color every cell either black (`B`) or white (`W`) so that:
# 1. All black cells form one orthogonally connected region.
# 2. All white cells form one orthogonally connected region.
# 3. No 2x2 block can be all black or all white.
# 
# **Coordinates & Output:**
# 1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
# 2. `row` increases from top to bottom, `col` increases from left to right.
# 3. **Observation:** dictionary of given clues only.
#    Example: `{(0, 0): 'B', (1, 3): 'W', ...}`
# 4. **Answer:** full grid as a 2D list of `'B'` / `'W'`.
# '''

RULES = '''
**Core Rules:**
Color every cell either black (`B`) or white (`W`) so that:
1. All black cells form one orthogonally connected region.
2. All white cells form one orthogonally connected region.
3. No 2x2 block can be all black or all white.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases from top to bottom, `col` increases from left to right.
3. **Observation** has one part:
   - `data`: `N x N` clue 2D list using `'B'`, `'W'`, or `None`.
4. **Answer:** full `N x N` grid as a 2D list of `'B'` / `'W'`.
'''


BOARD_FACE = '#C99A3F'
GRID_LINE = '#111111'
FRAME_COLOR = '#996C24'

STONE_BLACK = '#050505'
STONE_WHITE = '#F2F2F2'
STONE_WHITE_EDGE = '#BEBEBE'
HIGHLIGHT_WHITE = '#FFFFFF'
HIGHLIGHT_BLACK = '#7A7A7A'


def _draw_board(ax, n):
    bg = patches.Rectangle((-0.5, -0.5), n, n, linewidth=2.2, edgecolor=FRAME_COLOR, facecolor=BOARD_FACE, zorder=0)
    ax.add_patch(bg)

    for r in range(n):
        for c in range(n):
            rect = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                linewidth=1.2,
                edgecolor=GRID_LINE,
                facecolor='none',
                zorder=1,
            )
            ax.add_patch(rect)


def _draw_stone(ax, row, col, color):
    is_black = str(color).upper() == 'B'
    fill = STONE_BLACK if is_black else STONE_WHITE
    edge = '#000000' if is_black else STONE_WHITE_EDGE

    stone = patches.Circle((col, row), radius=0.36, facecolor=fill, edgecolor=edge, linewidth=1.5, zorder=3)
    ax.add_patch(stone)

    # subtle highlight for a glossy style similar to the reference image
    hl_color = HIGHLIGHT_BLACK if is_black else HIGHLIGHT_WHITE
    highlight = patches.Circle((col - 0.10, row - 0.09), radius=0.055, facecolor=hl_color, edgecolor='none', alpha=0.8, zorder=4)
    ax.add_patch(highlight)


def draw_yinyang(grid, output_path, answer=None):
    n = len(grid)
    fig, ax = plt.subplots(figsize=(n + 1.2, n + 1.2))

    _draw_board(ax, n)

    render_grid = answer if answer is not None else grid
    for r in range(n):
        for c in range(n):
            val = render_grid[r][c]
            if val in ('B', 'W'):
                _draw_stone(ax, r, c, val)

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


def format_yinyang_to_string(grid, answer_grid=None):
    show_grid = answer_grid if answer_grid is not None else grid
    lines = []
    for row in show_grid:
        tokens = []
        for cell in row:
            if cell in ('B', 'W'):
                tokens.append(cell)
            else:
                tokens.append('.')
        lines.append(' '.join(tokens))
    return '\n'.join(lines)


def construct_yinyang_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'yinyang'))
    os.makedirs(output_dir, exist_ok=True)

    fig_name = f"yinyang_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_yinyang(
        puzzle_dict['original_data']['data'],
        output_path=os.path.join(output_dir, f'{fig_name}.png'),
    )

    answer_fig_name = f"yinyang_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_yinyang(
        puzzle_dict['original_data']['data'],
        output_path=os.path.join(output_dir, f'{answer_fig_name}.png'),
        answer=puzzle_dict['answer'],
    )

    output_dict = {'puzzle': 'yinyang'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name

    output_dict['initial_str'] = format_yinyang_to_string(puzzle_dict['original_data']['data'])
    output_dict['answer_str'] = format_yinyang_to_string(
        puzzle_dict['original_data']['data'],
        answer_grid=puzzle_dict['answer'],
    )

    return output_dict


def test_observation(observation, gt_observation):
    """Clue grid `data` (B/W only where given); exact match."""
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
    return


def get_observation(data):
    data = normalize_size_keys(data)
    grid = data['original_data']['data']
    n = data['column/row']
    clue_grid = [[None for _ in range(n)] for _ in range(n)]
    for r in range(n):
        for c in range(n):
            if grid[r][c] in ('B', 'W'):
                clue_grid[r][c] = grid[r][c]
    return {'data': clue_grid}


def return_data():
    ref_puzzle_dict = {
        'column/row': 6,
        'level': 'easy',
        'original_data': {
            'data': [
                ['B', None, None, None, None, None],
                [None, 'B', None, 'W', None, None],
                [None, 'B', 'W', None, 'B', 'B'],
                [None, 'B', None, None, 'B', None],
                [None, None, 'W', None, None, None],
                [None, None, None, None, None, None],
            ],
        },
        'answer': [
            ['B', 'B', 'B', 'B', 'B', 'B'],
            ['W', 'B', 'W', 'W', 'W', 'B'],
            ['W', 'B', 'W', 'B', 'B', 'B'],
            ['W', 'B', 'W', 'W', 'B', 'W'],
            ['W', 'B', 'W', 'B', 'B', 'W'],
            ['W', 'W', 'W', 'W', 'W', 'W'],
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
                    [None, None, None, None, None, 'B'],
                    [None, None, 'W', 'W', 'W', None],
                    ['B', None, 'B', 'B', None, 'W'],
                    ['W', 'B', None, None, 'B', None],
                    [None, None, None, 'W', None, None],
                    [None, None, None, None, None, None],
                ],
            },
            'answer': [
                ['B', 'B', 'B', 'B', 'B', 'B'],
                ['B', 'W', 'W', 'W', 'W', 'W'],
                ['B', 'B', 'B', 'B', 'B', 'W'],
                ['W', 'B', 'W', 'W', 'B', 'W'],
                ['W', 'B', 'B', 'W', 'B', 'W'],
                ['W', 'W', 'W', 'W', 'W', 'W'],
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
    ret = construct_yinyang_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_yinyang_data(puzzle)
    print(ret)
