import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


RULES = '''
**Core Rules:**
Fill some cells black so that:
1. In each row, the sum of the column-weights of black cells equals the row target number.
2. In each column, the sum of the row-weights of black cells equals the column target number.
3. Column-weights are listed above the board (left-to-right), row-weights are listed left of the board (top-to-bottom).
4. Cells are either black or non-black.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has two parts:
   - `row_sum`: row target sums from top row to bottom row.
   - `col_sum`: column target sums from left column to right column.
4. **Answer:** same-sized grid using `'B'` for black cells and `None` for non-black cells.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_GRID = '#4F4F4F'
COLOR_FRAME = '#000000'
COLOR_BLACK = '#111111'
COLOR_WEIGHT = '#8A8A8A'
COLOR_SUM = '#2E5EC4'


def _is_black(value):
    return value in {'B', '#', 1, True}


def _normalize_data(original_data, n):
    row_sum = original_data.get('row_sum')
    col_sum = original_data.get('col_sum')
    if row_sum is None or col_sum is None:
        raise ValueError("original_data must include row_sum and col_sum.")

    row_sum = list(row_sum)
    col_sum = list(col_sum)
    if len(row_sum) != n or len(col_sum) != n:
        raise ValueError("row_sum/col_sum length must equal board size.")

    # Optional custom weights; default is 1..n.
    row_weights = original_data.get('row_weights')
    col_weights = original_data.get('col_weights')
    if row_weights is None:
        row_weights = list(range(1, n + 1))
    else:
        row_weights = list(row_weights)
    if col_weights is None:
        col_weights = list(range(1, n + 1))
    else:
        col_weights = list(col_weights)

    if len(row_weights) != n or len(col_weights) != n:
        raise ValueError("row_weights/col_weights length must equal board size.")

    return row_sum, col_sum, row_weights, col_weights


def _draw_grid(ax, n):
    for r in range(n):
        for c in range(n):
            rect = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                facecolor=COLOR_CELL,
                edgecolor=COLOR_GRID,
                linewidth=1.6,
                zorder=1,
            )
            ax.add_patch(rect)

    frame = patches.Rectangle((-0.5, -0.5), n, n, fill=False, edgecolor=COLOR_FRAME, linewidth=4.0, zorder=5)
    ax.add_patch(frame)


def _draw_answer(ax, answer):
    n = len(answer)
    for r in range(n):
        for c in range(n):
            if _is_black(answer[r][c]):
                rect = patches.Rectangle(
                    (c - 0.5, r - 0.5),
                    1,
                    1,
                    facecolor=COLOR_BLACK,
                    edgecolor=COLOR_GRID,
                    linewidth=1.6,
                    zorder=3,
                )
                ax.add_patch(rect)


def _draw_weights_and_sums(ax, row_sum, col_sum, row_weights, col_weights):
    n = len(row_sum)

    # Gray weights on left/top.
    for r, w in enumerate(row_weights):
        ax.text(
            -0.92,
            r,
            str(w),
            ha='center',
            va='center',
            fontsize=20,
            fontweight='bold',
            color=COLOR_WEIGHT,
            zorder=8,
            clip_on=False,
        )
    for c, w in enumerate(col_weights):
        ax.text(
            c,
            -0.92,
            str(w),
            ha='center',
            va='center',
            fontsize=20,
            fontweight='bold',
            color=COLOR_WEIGHT,
            zorder=8,
            clip_on=False,
        )

    # Blue target sums on right/bottom.
    for r, s in enumerate(row_sum):
        ax.text(
            n - 0.5 + 0.32,
            r,
            str(s),
            ha='center',
            va='center',
            fontsize=30,
            fontweight='bold',
            color=COLOR_SUM,
            zorder=9,
            clip_on=False,
        )
    for c, s in enumerate(col_sum):
        ax.text(
            c,
            n - 0.5 + 0.32,
            str(s),
            ha='center',
            va='center',
            fontsize=30,
            fontweight='bold',
            color=COLOR_SUM,
            zorder=9,
            clip_on=False,
        )


def draw_kakurasu(row_sum, col_sum, row_weights, col_weights, output_path, answer=None):
    n = len(row_sum)
    fig, ax = plt.subplots(figsize=(n + 2.6, n + 2.6))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_grid(ax, n)
    if answer is not None:
        _draw_answer(ax, answer)
    _draw_weights_and_sums(ax, row_sum, col_sum, row_weights, col_weights)

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


def format_kakurasu_to_string(row_sum, col_sum, row_weights, col_weights, answer=None):
    lines = [
        f"row_sum={row_sum}",
        f"col_sum={col_sum}",
        f"row_weights={row_weights}",
        f"col_weights={col_weights}",
    ]

    n = len(row_sum)
    if answer is not None:
        for r in range(n):
            row_tokens = []
            for c in range(n):
                row_tokens.append('B' if _is_black(answer[r][c]) else '.')
            lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_kakurasu_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'kakurasu'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    row_sum, col_sum, row_weights, col_weights = _normalize_data(puzzle_dict['original_data'], n)

    fig_name = f"kakurasu_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_kakurasu(row_sum, col_sum, row_weights, col_weights, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"kakurasu_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_kakurasu(
        row_sum,
        col_sum,
        row_weights,
        col_weights,
        output_path=os.path.join(output_dir, f'{answer_fig_name}.png'),
        answer=puzzle_dict['answer'],
    )

    output_dict = {'puzzle': 'kakurasu'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_kakurasu_to_string(row_sum, col_sum, row_weights, col_weights)
    output_dict['answer_str'] = format_kakurasu_to_string(row_sum, col_sum, row_weights, col_weights, answer=puzzle_dict['answer'])

    return output_dict


def _compute_weighted_sums(answer, row_weights, col_weights):
    n = len(answer)
    calc_row_sum = []
    calc_col_sum = []

    for r in range(n):
        s = 0
        for c in range(n):
            if _is_black(answer[r][c]):
                s += col_weights[c]
        calc_row_sum.append(s)

    for c in range(n):
        s = 0
        for r in range(n):
            if _is_black(answer[r][c]):
                s += row_weights[r]
        calc_col_sum.append(s)

    return calc_row_sum, calc_col_sum


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
    if observation != gt_observation:
        return False
    if answer is None:
        return False

    row_sum = observation.get('row_sum')
    col_sum = observation.get('col_sum')
    if row_sum is None or col_sum is None:
        return False

    n = len(row_sum)
    if len(col_sum) != n or len(answer) != n:
        return False
    for row in answer:
        if len(row) != n:
            return False

    default_weights = list(range(1, n + 1))
    calc_row_sum, calc_col_sum = _compute_weighted_sums(answer, default_weights, default_weights)
    if calc_row_sum != row_sum:
        return False
    if calc_col_sum != col_sum:
        return False

    if gt_answer is None:
        return True
    return answer == gt_answer


def get_observation(data):
    data = normalize_size_keys(data)
    n = data['column/row']
    row_sum, col_sum, _, _ = _normalize_data(data['original_data'], n)
    return {
        'row_sum': row_sum,
        'col_sum': col_sum,
    }


def return_data():
    ref_puzzle_dict = {
        'column/row': 4,
        'level': 'easy',
        'original_data': {
            'row_sum': [9, 5, 7, 3],
            'col_sum': [3, 6, 7, 4],
        },
        'answer': [
            [None, 'B', 'B', 'B'],
            [None, 'B', 'B', None],
            ['B', 'B', None, 'B'],
            [None, None, 'B', None],
        ],
        'id': 'ref',
        'rules': RULES,
    }
    ref_puzzle_dict['observation'] = get_observation(ref_puzzle_dict)

    puzzles = [
        {
            'column/row': 4,
            'level': 'easy',
            'original_data': {
                'row_sum': [7, 4, 9, 5],
                'col_sum': [7, 4, 5, 8],
            },
            'answer': [
                ['B', 'B', None, 'B'],
                ['B', None, 'B', None],
                [None, 'B', 'B', 'B'],
                ['B', None, None, 'B'],
            ],
            'id': 'example_0',
            'rules': RULES,
        },
        {
            'column/row': 5,
            'level': 'easy',
            'original_data': {
                'row_sum': [12, 11, 1, 6, 12],
                'col_sum': [14, 7, 3, 6, 12],
            },
            'answer': [
                [None, None, 'B', 'B', 'B'],
                ['B', 'B', 'B', None, 'B'],
                ['B', None, None, None, None],
                ['B', None, None, None, 'B'],
                ['B', 'B', None, 'B', 'B'],
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
    ret = construct_kakurasu_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_kakurasu_data(puzzle)
    print(ret)
