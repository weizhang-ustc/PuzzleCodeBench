import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


RULES = '''
**Core Rules:**
Fill some cells black so that:
1. Each row matches its row clues: clue numbers are lengths of consecutive black-cell runs in that row.
2. Each column matches its column clues: clue numbers are lengths of consecutive black-cell runs in that column.
3. Multiple runs in one row/column must be separated by at least one non-black cell.
4. Clue order is fixed (left-to-right for rows, top-to-bottom for columns).

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has two parts:
   - `row_black_runs`: list of row clues from top row to bottom row; each item is a list (possibly multiple numbers).
   - `col_black_runs`: list of column clues from left column to right column; each item is a list (possibly multiple numbers).
4. **Answer:** same-sized grid using `'B'` for black cells and `None` for non-black cells.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_GRID = '#4F4F4F'
COLOR_FRAME = '#000000'
COLOR_BLACK = '#111111'
COLOR_CLUE = '#000000'


def _normalize_runs(original_data):
    # Preferred names.
    row_runs = original_data.get('row_black_runs')
    col_runs = original_data.get('col_black_runs')

    # Backward-compatible names.
    if row_runs is None:
        row_runs = original_data.get('row_numbers')
    if col_runs is None:
        col_runs = original_data.get('col_numbers')

    if row_runs is None or col_runs is None:
        raise ValueError("original_data must include row/column runs.")

    return [list(x) for x in row_runs], [list(x) for x in col_runs]


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

    frame = patches.Rectangle((-0.5, -0.5), n, n, fill=False, edgecolor=COLOR_FRAME, linewidth=4.0, zorder=4)
    ax.add_patch(frame)


def _is_black(value):
    return value in {'B', '#', 1, True}


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


def _draw_row_clues(ax, row_runs):
    # Compact spacing: keep clues close to the grid while avoiding overlaps.
    clue_gap = 0.42
    n = len(row_runs)
    for r in range(n):
        clues = row_runs[r]
        for i, clue in enumerate(clues):
            # Right-aligned toward the board: last clue is nearest to the board.
            x = -0.5 - (len(clues) - i) * clue_gap
            ax.text(
                x,
                r,
                str(clue),
                ha='center',
                va='center',
                fontsize=19,
                fontweight='bold',
                color=COLOR_CLUE,
                zorder=8,
                clip_on=False,
            )


def _draw_col_clues(ax, col_runs):
    clue_gap = 0.42
    n = len(col_runs)
    for c in range(n):
        clues = col_runs[c]
        for i, clue in enumerate(clues):
            # Bottom-aligned toward the board: last clue is nearest to the board.
            y = -0.5 - (len(clues) - i) * clue_gap
            ax.text(
                c,
                y,
                str(clue),
                ha='center',
                va='center',
                fontsize=19,
                fontweight='bold',
                color=COLOR_CLUE,
                zorder=8,
                clip_on=False,
            )


def draw_nonograms(row_runs, col_runs, output_path, answer=None):
    n = len(row_runs)
    fig, ax = plt.subplots(figsize=(n + 1.8, n + 1.8))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_grid(ax, n)
    if answer is not None:
        _draw_answer(ax, answer)
    _draw_row_clues(ax, row_runs)
    _draw_col_clues(ax, col_runs)

    ticks = list(range(n))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])
    ax.set_yticklabels([str(t) for t in ticks])
    ax.xaxis.tick_top()
    ax.tick_params(axis='x', pad=2)
    ax.tick_params(axis='y', pad=2)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_clip_on(False)

    # Keep the board frame as the native plotting window; clues are drawn outside with clip_on=False.
    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(-0.5, n - 0.5)
    ax.invert_yaxis()
    ax.set_aspect('equal')

    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout()
    save_square_figure(
        fig,
        output_path,
        vertical_shift_ratio=0.02,
        horizontal_shift_ratio=0.02,
    )
    plt.close()


def format_nonograms_to_string(row_runs, col_runs, answer=None):
    lines = [
        f"row_black_runs={row_runs}",
        f"col_black_runs={col_runs}",
    ]

    n = len(row_runs)
    if answer is not None:
        for r in range(n):
            row_tokens = []
            for c in range(n):
                row_tokens.append('B' if _is_black(answer[r][c]) else '.')
            lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_nonograms_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'nonograms'))
    os.makedirs(output_dir, exist_ok=True)

    original = puzzle_dict['original_data']
    row_runs, col_runs = _normalize_runs(original)

    fig_name = f"nonograms_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_nonograms(row_runs, col_runs, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"nonograms_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_nonograms(row_runs, col_runs, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'nonograms'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_nonograms_to_string(row_runs, col_runs)
    output_dict['answer_str'] = format_nonograms_to_string(row_runs, col_runs, answer=puzzle_dict['answer'])

    return output_dict


def _extract_runs(line):
    runs = []
    run_len = 0
    for val in line:
        if _is_black(val):
            run_len += 1
        else:
            if run_len > 0:
                runs.append(run_len)
                run_len = 0
    if run_len > 0:
        runs.append(run_len)
    return runs


def test_observation(observation, gt_observation):
    """Observation is row/column black runs; exact match."""
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

    row_runs = observation.get('row_black_runs')
    col_runs = observation.get('col_black_runs')
    if row_runs is None or col_runs is None:
        return False

    n_rows = len(row_runs)
    n_cols = len(col_runs)
    if len(answer) != n_rows:
        return False
    for row in answer:
        if len(row) != n_cols:
            return False

    for r in range(n_rows):
        if _extract_runs(answer[r]) != row_runs[r]:
            return False

    for c in range(n_cols):
        col_vals = [answer[r][c] for r in range(n_rows)]
        if _extract_runs(col_vals) != col_runs[c]:
            return False

    if gt_answer is None:
        return True
    return answer == gt_answer


def get_observation(data):
    data = normalize_size_keys(data)
    original = data['original_data']
    row_runs, col_runs = _normalize_runs(original)
    return {
        'row_black_runs': row_runs,
        'col_black_runs': col_runs,
    }


def return_data():
    ref_puzzle_dict = {
        'column/row': 5,
        'level': 'easy',
        'original_data': {
            'row_black_runs': [[2], [3], [1], [2, 2], [1, 2]],
            'col_black_runs': [[4], [2, 2], [1], [2], [2]],
        },
        'answer': [
            ['B', 'B', None, None, None],
            ['B', 'B', 'B', None, None],
            ['B', None, None, None, None],
            ['B', 'B', None, 'B', 'B'],
            [None, 'B', None, 'B', 'B'],
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
                'row_black_runs': [[2, 2], [3], [3], [2], [1]],
                'col_black_runs': [[2], [4], [4], [1, 1], [1]],
            },
            'answer': [
                ['B', 'B', None, 'B', 'B'],
                ['B', 'B', 'B', None, None],
                [None, 'B', 'B', 'B', None],
                [None, 'B', 'B', None, None],
                [None, None, 'B', None, None],
            ],
            'id': 'example_0',
            'rules': RULES,
        },
        {
            'column/row': 5,
            'level': 'easy',
            'original_data': {
                'row_black_runs': [[3], [3], [3], [1, 1], [2]],
                'col_black_runs': [[1], [1], [3], [3, 1], [2, 2]],
            },
            'answer': [
                [None, None, 'B', 'B', 'B'],
                [None, None, 'B', 'B', 'B'],
                [None, 'B', 'B', 'B', None],
                ['B', None, None, None, 'B'],
                [None, None, None, 'B', 'B'],
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
    ret = construct_nonograms_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_nonograms_data(puzzle)
    print(ret)
