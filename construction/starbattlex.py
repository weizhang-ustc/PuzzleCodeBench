import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules (Shapeless, 1-Star):**
# Place stars on the grid so that:
# 1. Each row contains exactly 1 star.
# 2. Each column contains exactly 1 star.
# 3. Stars cannot touch each other, including diagonally.
# 4. Black obstacle cells cannot contain stars.
# 
# **Coordinates & Output:**
# 1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
# 2. `row` increases top-to-bottom, `col` increases left-to-right.
# 3. **Observation:** a list of lists using `'B'` for black obstacle cells and `None` for empty cells.
# 4. **Answer:** same-sized grid using `'S'` for star cells and `None` for non-star cells.
# '''

RULES = '''
**Core Rules (Shapeless, 1-Star):**
Place stars on the grid so that:
1. Each row contains exactly 1 star.
2. Each column contains exactly 1 star.
3. Stars cannot touch each other, including diagonally.
4. Black obstacle cells cannot contain stars.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has one part:
   - `data`: obstacle grid as `N x N` list of lists (`'B'` or `None`).
4. **Answer:** same-sized grid using `'S'` for star cells and `None` for non-star cells.
'''


COLOR_BG = '#FFFFFF'
COLOR_WHITE = '#FFFFFF'
COLOR_BLACK = '#000000'
COLOR_GRID = '#5A5A5A'
COLOR_FRAME = '#000000'
COLOR_STAR = '#111111'


def _draw_board(ax, obstacle_grid):
    n = len(obstacle_grid)
    for r in range(n):
        for c in range(n):
            is_black = obstacle_grid[r][c] == 'B'
            rect = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                facecolor=COLOR_BLACK if is_black else COLOR_WHITE,
                edgecolor=COLOR_GRID,
                linewidth=1.1,
                zorder=1,
            )
            ax.add_patch(rect)

    frame = patches.Rectangle(
        (-0.5, -0.5),
        n,
        n,
        fill=False,
        edgecolor=COLOR_FRAME,
        linewidth=3.0,
        zorder=3,
    )
    ax.add_patch(frame)


def _draw_stars(ax, answer_grid):
    n = len(answer_grid)
    xs, ys = [], []
    for r in range(n):
        for c in range(n):
            if answer_grid[r][c] == 'S':
                xs.append(c)
                ys.append(r)

    if xs:
        ax.scatter(xs, ys, marker='*', s=820, c=COLOR_STAR, linewidths=1.2, edgecolors=COLOR_STAR, zorder=4)


def draw_starbattlex(obstacle_grid, output_path, answer=None):
    n = len(obstacle_grid)
    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_board(ax, obstacle_grid)
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


def format_starbattlex_to_string(observation_grid, answer_grid=None):
    n = len(observation_grid)
    lines = []
    for r in range(n):
        row_tokens = []
        for c in range(n):
            if observation_grid[r][c] == 'B':
                row_tokens.append('B')
            elif answer_grid is not None and answer_grid[r][c] == 'S':
                row_tokens.append('S')
            else:
                row_tokens.append('.')
        lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_starbattlex_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'starbattlex'))
    os.makedirs(output_dir, exist_ok=True)

    obstacle_grid = puzzle_dict['original_data']['data']

    fig_name = f"starbattlex_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_starbattlex(obstacle_grid, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"starbattlex_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_starbattlex(obstacle_grid, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'starbattlex'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_starbattlex_to_string(obstacle_grid)
    output_dict['answer_str'] = format_starbattlex_to_string(obstacle_grid, answer_grid=puzzle_dict['answer'])

    return output_dict


def test_observation(observation, gt_observation):
    """Obstacle grid `data`; exact match."""
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
    return {'data': [row[:] for row in grid]}


def return_data():
    ref_puzzle_dict = {
        'column/row': 6,
        'level': 'easy',
        'original_data': {
            'data': [
                ['B', 'B', None, None, 'B', None],
                [None, None, None, None, None, None],
                [None, None, None, None, 'B', None],
                [None, None, None, None, None, 'B'],
                ['B', 'B', 'B', None, 'B', None],
                [None, 'B', None, None, None, None],
            ],
        },
        'answer': [
            [None, None, 'S', None, None, None],
            [None, None, None, None, 'S', None],
            [None, 'S', None, None, None, None],
            [None, None, None, 'S', None, None],
            [None, None, None, None, None, 'S'],
            ['S', None, None, None, None, None],
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
                    [None, None, None, None, 'B', None],
                    [None, 'B', None, 'B', None, None],
                    [None, None, None, None, 'B', None],
                    [None, None, None, 'B', None, 'B'],
                    [None, None, 'B', None, None, None],
                    [None, 'B', 'B', 'B', None, 'B'],
                ],
            },
            'answer': [
                [None, None, 'S', None, None, None],
                [None, None, None, None, None, 'S'],
                [None, None, None, 'S', None, None],
                [None, 'S', None, None, None, None],
                [None, None, None, None, 'S', None],
                ['S', None, None, None, None, None],
            ],
            'id': 'example_0',
            'rules': RULES,
        },
        {
            'column/row': 6,
            'level': 'easy',
            'original_data': {
                'data': [
                    [None, None, None, None, None, None],
                    ['B', 'B', None, 'B', 'B', 'B'],
                    ['B', None, None, None, None, None],
                    [None, 'B', None, None, None, None],
                    [None, None, None, None, None, None],
                    [None, 'B', None, None, None, None],
                ],
            },
            'answer': [
                ['S', None, None, None, None, None],
                [None, None, 'S', None, None, None],
                [None, None, None, None, None, 'S'],
                [None, None, None, 'S', None, None],
                [None, 'S', None, None, None, None],
                [None, None, None, None, 'S', None],
            ],
            'id': 'example_1',
            'rules': RULES,
        },
        {
            'column/row': 8,
            'level': 'easy',
            'original_data': {
                'data': [
                    ['B', None, 'B', None, 'B', 'B', None, 'B'],
                    [None, None, None, None, None, None, None, None],
                    ['B', None, 'B', None, None, 'B', None, None],
                    [None, None, 'B', None, None, None, None, 'B'],
                    ['B', None, 'B', 'B', 'B', 'B', None, 'B'],
                    [None, None, 'B', None, None, None, None, None],
                    ['B', None, 'B', 'B', None, None, None, None],
                    [None, None, 'B', None, None, None, None, None],
                ],
            },
            'answer': [
                [None, None, None, None, None, None, 'S', None],
                [None, None, 'S', None, None, None, None, None],
                [None, None, None, None, None, None, None, 'S'],
                [None, None, None, None, 'S', None, None, None],
                [None, 'S', None, None, None, None, None, None],
                [None, None, None, 'S', None, None, None, None],
                [None, None, None, None, None, 'S', None, None],
                ['S', None, None, None, None, None, None, None],
            ],
            'id': 'example_2',
            'rules': RULES,
        },
        {
            'column/row': 8,
            'level': 'easy',
            'original_data': {
                'data': [
                    ['B', 'B', 'B', 'B', None, 'B', None, 'B'],
                    [None, None, 'B', None, None, None, None, 'B'],
                    [None, 'B', 'B', 'B', None, 'B', None, 'B'],
                    [None, None, 'B', None, None, None, None, None],
                    ['B', None, None, None, None, 'B', None, None],
                    ['B', None, None, None, 'B', 'B', None, 'B'],
                    ['B', None, None, None, None, None, None, None],
                    [None, 'B', 'B', 'B', None, None, None, None],
                ],
            },
            'answer': [
                [None, None, None, None, 'S', None, None, None],
                [None, 'S', None, None, None, None, None, None],
                [None, None, None, None, None, None, 'S', None],
                [None, None, None, 'S', None, None, None, None],
                [None, None, None, None, None, None, None, 'S'],
                [None, None, 'S', None, None, None, None, None],
                [None, None, None, None, None, 'S', None, None],
                ['S', None, None, None, None, None, None, None],
            ],
            'id': 'example_3',
            'rules': RULES,
        }
    ]
    for puzzle in puzzles:
        puzzle['observation'] = get_observation(puzzle)

    return ref_puzzle_dict, puzzles


if __name__ == '__main__':
    ref_puzzle_dict, puzzles = return_data()
    ret = construct_starbattlex_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_starbattlex_data(puzzle)
    print(ret)
