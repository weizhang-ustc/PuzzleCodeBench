import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# Shade some cells black so that:
# 1. In every row, each unshaded number appears at most once.
# 2. In every column, each unshaded number appears at most once.
# 3. Black cells cannot touch orthogonally (up/down/left/right).
# 4. All unshaded (white) cells must form one orthogonally connected group.
# 
# **Coordinates & Output:**
# 1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
# 2. `row` increases from top to bottom, `col` increases from left to right.
# 3. **Observation:** full number board as a list of lists.
#    Example: `[[3, 1, 1, 4, 4], [2, 5, 4, 1, 3], ...]`
# 4. **Answer:** solved grid mask with `'B'` for black cells and `None` for white cells.
# '''

RULES = '''
**Core Rules:**
Shade some cells black so that:
1. In every row, each unshaded number appears at most once.
2. In every column, each unshaded number appears at most once.
3. Black cells cannot touch orthogonally (up/down/left/right).
4. All unshaded (white) cells must form one orthogonally connected group.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases from top to bottom, `col` increases from left to right.
3. **Observation** has one part:
   - `data`: full number board as a `N x N` list of lists.
4. **Answer:** solved grid mask as a `N x N` 2D list with `'B'` for black cells and `None` for white cells.
'''


COLOR_CELL = '#FFFFFF'
COLOR_GRID = '#1F1F1F'
COLOR_BLACK = '#111111'
COLOR_TEXT = '#111111'
COLOR_TEXT_ON_BLACK = '#F5F5F5'


def _is_black_cell(value):
    return value == 'B'


def draw_hitori(grid, output_path, answer=None):
    n = len(grid)
    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))

    for r in range(n):
        for c in range(n):
            is_black = answer is not None and _is_black_cell(answer[r][c])
            face = COLOR_BLACK if is_black else COLOR_CELL

            rect = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                facecolor=face,
                edgecolor=COLOR_GRID,
                linewidth=1.2,
                zorder=1,
            )
            ax.add_patch(rect)

            text_color = COLOR_TEXT_ON_BLACK if is_black else COLOR_TEXT
            ax.text(
                c,
                r,
                str(grid[r][c]),
                ha='center',
                va='center',
                fontsize=26,
                fontweight='bold',
                color=text_color,
                zorder=2,
            )

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
        spine.set_linewidth(2.2)

    plt.tight_layout()
    save_square_figure(fig, output_path)
    plt.close()


def format_hitori_to_string(grid, answer_grid=None):
    n = len(grid)
    lines = []
    for r in range(n):
        row_tokens = []
        for c in range(n):
            if answer_grid is not None and _is_black_cell(answer_grid[r][c]):
                row_tokens.append(f"{grid[r][c]}(B)")
            else:
                row_tokens.append(str(grid[r][c]))
        lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_hitori_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'hitori'))
    os.makedirs(output_dir, exist_ok=True)

    fig_name = f"hitori_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_hitori(
        puzzle_dict['original_data']['data'],
        output_path=os.path.join(output_dir, f'{fig_name}.png'),
    )

    answer_fig_name = f"hitori_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_hitori(
        puzzle_dict['original_data']['data'],
        output_path=os.path.join(output_dir, f'{answer_fig_name}.png'),
        answer=puzzle_dict['answer'],
    )

    output_dict = {'puzzle': 'hitori'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_hitori_to_string(puzzle_dict['original_data']['data'])
    output_dict['answer_str'] = format_hitori_to_string(
        puzzle_dict['original_data']['data'],
        answer_grid=puzzle_dict['answer'],
    )

    return output_dict


def test_observation(observation, gt_observation):
    """Test if observation matches gt_observation (compare number boards as list-of-lists)."""
    o = observation.get('data') if isinstance(observation, dict) else observation
    g = gt_observation.get('data') if isinstance(gt_observation, dict) else gt_observation
    return o == g


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
    grid = data['original_data']['data']
    return {'data': [row[:] for row in grid]}


def return_data():
    ref_puzzle_dict = {
        'column/row': 5,
        'level': 'easy',
        'original_data': {
            'data': [
                [1, 2, 3, 5, 5],
                [1, 3, 3, 2, 1],
                [2, 5, 1, 1, 3],
                [3, 2, 2, 1, 5],
                [2, 1, 5, 5, 2],
            ],
        },
        'answer': [
            [None, None, None, None, 'B'],
            ['B', None, 'B', None, None],
            [None, None, None, 'B', None],
            [None, 'B', None, None, None],
            ['B', None, None, 'B', None],
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
                    [4, 4, 5, 5, 3],
                    [1, 2, 5, 5, 4],
                    [3, 1, 2, 2, 1],
                    [4, 3, 1, 2, 5],
                    [3, 1, 1, 3, 1],
                ],
            },
            'answer': [
                ['B', None, None, 'B', None],
                [None, None, 'B', None, None],
                [None, 'B', None, 'B', None],
                [None, None, None, None, None],
                ['B', None, 'B', None, 'B'],
            ],
            'id': 'example_0',
            'rules': RULES,
        },
        {
            'column/row': 5,
            'level': 'easy',
            'original_data': {
                'data': [
                    [5, 1, 3, 2, 3],
                    [5, 4, 1, 5, 3],
                    [4, 5, 1, 2, 2],
                    [1, 3, 4, 1, 4],
                    [3, 2, 2, 4, 1],
                ],
            },
            'answer': [
                [None, None, None, None, 'B'],
                ['B', None, 'B', None, None],
                [None, None, None, 'B', None],
                ['B', None, None, None, 'B'],
                [None, None, 'B', None, None],
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
    ret = construct_hitori_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_hitori_data(puzzle)
    print(ret)
