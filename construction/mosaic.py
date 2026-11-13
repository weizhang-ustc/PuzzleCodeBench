import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


RULES = '''
**Core Rules:**
Color cells black or white so that:
1. Each numbered cell equals the count of black cells in its 3x3 neighborhood (including itself).
2. Unnumbered cells have no direct numeric constraint.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has one part:
   - `data`: number grid as list of lists (`None` means no given number).
4. **Answer:** same-sized grid using `'B'` for black cells and `None` for white cells.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_GRID = '#4F4F4F'
COLOR_FRAME = '#000000'
COLOR_BLACK = '#111111'
COLOR_GIVEN_TEXT = '#111111'
COLOR_GIVEN_TEXT_ON_BLACK = '#FFFFFF'


def _is_black(value):
    return value in {'B', '#', 1, True}


def _normalize_number_grid(number_grid, n=None):
    if not isinstance(number_grid, list) or not number_grid:
        raise ValueError('data must be a non-empty list of lists.')
    if not isinstance(number_grid[0], list):
        raise ValueError('data must be a 2D list.')

    grid = [row[:] for row in number_grid]
    if n is not None:
        if len(grid) != n:
            raise ValueError('data size does not match board size.')
        for row in grid:
            if len(row) != n:
                raise ValueError('data must be square and match board size.')
    return grid


def _draw_grid(ax, n):
    for r in range(n):
        for c in range(n):
            rect = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                facecolor=COLOR_CELL,
                edgecolor=COLOR_GRID,
                linewidth=1.1,
                zorder=1,
            )
            ax.add_patch(rect)

    frame = patches.Rectangle((-0.5, -0.5), n, n, fill=False, edgecolor=COLOR_FRAME, linewidth=3.2, zorder=4)
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
                    linewidth=1.1,
                    zorder=2.5,
                )
                ax.add_patch(rect)


def _draw_numbers(ax, number_grid, answer=None):
    n = len(number_grid)
    for r in range(n):
        for c in range(n):
            val = number_grid[r][c]
            if val is None:
                continue
            color = COLOR_GIVEN_TEXT
            if answer is not None and _is_black(answer[r][c]):
                color = COLOR_GIVEN_TEXT_ON_BLACK
            ax.text(
                c,
                r,
                str(val),
                ha='center',
                va='center',
                fontsize=24,
                fontweight='bold',
                color=color,
                zorder=5,
            )


def draw_mosaic(number_grid, output_path, answer=None):
    n = len(number_grid)
    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_grid(ax, n)
    if answer is not None:
        _draw_answer(ax, answer)
    _draw_numbers(ax, number_grid, answer=answer)

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


def format_mosaic_to_string(number_grid, answer=None):
    lines = [f"data={number_grid}"]
    n = len(number_grid)
    if answer is not None:
        for r in range(n):
            row_tokens = []
            for c in range(n):
                row_tokens.append('B' if _is_black(answer[r][c]) else '.')
            lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_mosaic_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'mosaic'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    number_grid = _normalize_number_grid(puzzle_dict['original_data']['data'], n=n)

    fig_name = f"mosaic_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_mosaic(number_grid, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"mosaic_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_mosaic(number_grid, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'mosaic'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_mosaic_to_string(number_grid)
    output_dict['answer_str'] = format_mosaic_to_string(number_grid, answer=puzzle_dict['answer'])
    return output_dict


def _count_adjacent_black(answer, r, c):
    n = len(answer)
    total = 0
    for rr in range(max(0, r - 1), min(n - 1, r + 1) + 1):
        for cc in range(max(0, c - 1), min(n - 1, c + 1) + 1):
            if _is_black(answer[rr][cc]):
                total += 1
    return total


def test_observation(observation, gt_observation):
    """Observation is the clue grid; exact match."""
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

    number_grid = observation.get('data')
    if number_grid is None:
        return False

    n = len(number_grid)
    if len(answer) != n:
        return False
    for row in answer:
        if len(row) != n:
            return False

    for r in range(n):
        for c in range(n):
            clue = number_grid[r][c]
            if clue is None:
                continue
            if _count_adjacent_black(answer, r, c) != clue:
                return False

    if gt_answer is None:
        return True
    return answer == gt_answer

def return_data():
    ref_puzzle_dict = {
        'column/row': 5,
        'level': 'easy',
        'original_data': {
            'data': [
                [None, 4, 5, None, 1],
                [None, None, None, None, None],
                [1, None, None, None, 0],
                [2, None, None, 3, None],
                [None, None, 4, None, None],
            ]
        },
        'answer': [
            [None, 'B', 'B', 'B', None],
            [None, 'B', 'B', None, None],
            [None, None, None, None, None],
            [None, None, 'B', None, None],
            ['B', 'B', 'B', 'B', None],
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
                    [3, None, 3, None, None],
                    [None, None, None, 2, None],
                    [6, 7, 5, None, 1],
                    [None, 6, 3, None, None],
                    [3, None, 1, 1, None],
                ]
            },
            'answer': [
                [None, 'B', None, None, None],
                ['B', 'B', None, 'B', None],
                ['B', 'B', 'B', None, None],
                ['B', 'B', None, None, None],
                ['B', None, None, None, 'B'],
            ],
            'id': 'example_0',
            'rules': RULES,
        }
    ]
    for puzzle in puzzles:
        puzzle['observation'] = get_observation(puzzle)

    return ref_puzzle_dict, puzzles


def get_observation(data):
    data = normalize_size_keys(data)
    n = data['column/row']
    number_grid = _normalize_number_grid(data['original_data']['data'], n=n)
    return {'data': number_grid}


if __name__ == '__main__':
    ref_puzzle_dict, puzzles = return_data()
    ret = construct_mosaic_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_mosaic_data(puzzle)
    print(ret)
