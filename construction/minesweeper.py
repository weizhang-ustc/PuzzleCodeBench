import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


RULES = '''
**Core Rules:**
Find which cells contain mines so that:
1. Each numbered cell equals the number of adjacent mines in its 8-neighborhood.
2. Cells without numbers have no direct numeric clue.
3. Mines are represented by flagged cells in the answer.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has one part:
   - `data`: clue grid as list of lists (`None` means no shown number).
4. **Answer:** same-sized grid using `'F'` for flagged mine cells and `None` for non-mine cells.
'''


COLOR_BG = '#D5D5D5'
COLOR_CELL = '#B7B7B7'
COLOR_GRID = '#8F8F8F'
COLOR_FRAME = '#777777'
COLOR_HILITE = '#F7F7F7'
COLOR_SHADOW = '#8D8D8D'
COLOR_REVEALED = '#D7D7D7'

NUM_COLORS = {
    0: '#8F8F8F',  # gray
    1: '#0000CC',  # blue
    2: '#0A8A0A',  # green
    3: '#FF0000',  # red
    4: '#00008B',  # dark blue
    5: '#8B0000',  # dark red
    6: '#008B8B',  # cyan-like
    7: '#111111',  # black
    8: '#666666',  # dark gray
}


def _is_flag(v):
    if v is None:
        return False
    return str(v).upper() == 'F'


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
            base = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                facecolor=COLOR_CELL,
                edgecolor=COLOR_GRID,
                linewidth=0.9,
                zorder=1,
            )
            ax.add_patch(base)

            # Subtle beveled effect like classic Minesweeper tiles.
            ax.plot([c - 0.48, c + 0.48], [r - 0.48, r - 0.48], color=COLOR_HILITE, linewidth=2.0, zorder=2)
            ax.plot([c - 0.48, c - 0.48], [r - 0.48, r + 0.48], color=COLOR_HILITE, linewidth=2.0, zorder=2)
            ax.plot([c - 0.48, c + 0.48], [r + 0.48, r + 0.48], color=COLOR_SHADOW, linewidth=2.2, zorder=2)
            ax.plot([c + 0.48, c + 0.48], [r - 0.48, r + 0.48], color=COLOR_SHADOW, linewidth=2.2, zorder=2)

    frame = patches.Rectangle((-0.5, -0.5), n, n, fill=False, edgecolor=COLOR_FRAME, linewidth=3.0, zorder=5)
    ax.add_patch(frame)


def _draw_numbers(ax, number_grid):
    n = len(number_grid)
    for r in range(n):
        for c in range(n):
            val = number_grid[r][c]
            if val is None:
                continue
            color = NUM_COLORS.get(int(val), '#111111')
            ax.text(
                c,
                r,
                str(val),
                ha='center',
                va='center',
                fontsize=28 if n <= 6 else 20,
                fontweight='bold',
                color=color,
                zorder=6,
            )


def _draw_revealed(ax, number_grid, answer=None):
    # Numbered cells are always revealed (both puzzle/answer views).
    # In answer view, cells that are neither flag nor number are also revealed.
    n = len(number_grid)
    for r in range(n):
        for c in range(n):
            reveal = number_grid[r][c] is not None
            if answer is not None and (not _is_flag(answer[r][c])) and number_grid[r][c] is None:
                reveal = True
            if not reveal:
                continue
            rect = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                facecolor=COLOR_REVEALED,
                edgecolor=COLOR_GRID,
                linewidth=0.9,
                zorder=3.2,
            )
            ax.add_patch(rect)


def _draw_flags(ax, answer):
    n = len(answer)
    for r in range(n):
        for c in range(n):
            if not _is_flag(answer[r][c]):
                continue
            # pole
            ax.plot([c, c], [r + 0.23, r - 0.10], color='black', linewidth=2.2, zorder=7)
            # red flag
            flag = patches.Polygon(
                [(c, r - 0.10), (c, r + 0.02), (c - 0.22, r - 0.04)],
                closed=True,
                facecolor='#E31B23',
                edgecolor='#B00000',
                linewidth=0.8,
                zorder=8,
            )
            ax.add_patch(flag)
            # base
            ax.plot([c - 0.12, c + 0.12], [r + 0.23, r + 0.23], color='black', linewidth=3.0, zorder=7)


def draw_minesweeper(number_grid, output_path, answer=None):
    n = len(number_grid)
    fig, ax = plt.subplots(figsize=(n + 1.1, n + 1.1))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_grid(ax, n)
    _draw_revealed(ax, number_grid, answer=answer)
    if answer is not None:
        _draw_flags(ax, answer)
    _draw_numbers(ax, number_grid)

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


def format_minesweeper_to_string(number_grid, answer=None):
    lines = [f"data={number_grid}"]
    n = len(number_grid)
    if answer is not None:
        for r in range(n):
            row_tokens = []
            for c in range(n):
                row_tokens.append('F' if _is_flag(answer[r][c]) else '.')
            lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_minesweeper_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'minesweeper'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    number_grid = _normalize_number_grid(puzzle_dict['original_data']['data'], n=n)

    fig_name = f"minesweeper_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_minesweeper(number_grid, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"minesweeper_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_minesweeper(number_grid, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'minesweeper'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_minesweeper_to_string(number_grid)
    output_dict['answer_str'] = format_minesweeper_to_string(number_grid, answer=puzzle_dict['answer'])
    return output_dict


def _count_adjacent_flags(answer, r, c):
    n = len(answer)
    total = 0
    for rr in range(max(0, r - 1), min(n - 1, r + 1) + 1):
        for cc in range(max(0, c - 1), min(n - 1, c + 1) + 1):
            if rr == r and cc == c:
                continue
            if _is_flag(answer[rr][cc]):
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
            if _count_adjacent_flags(answer, r, c) != int(clue):
                return False

    if gt_answer is None:
        return True
    return answer == gt_answer


def get_observation(data):
    data = normalize_size_keys(data)
    n = data['column/row']
    number_grid = _normalize_number_grid(data['original_data']['data'], n=n)
    return {'data': number_grid}


def return_data():
    ref_puzzle_dict = {
        'column/row': 5,
        'level': 'easy',
        'original_data': {
            'data': [
                [1, 2, None, None, 0],
                [1, None, None, None, 1],
                [3, None, 4, 3, None],
                [None, None, None, 3, None],
                [None, 3, 2, None, None],
            ]
        },
        'answer': [
            [None, None, None, None, None],
            [None, 'F', 'F', None, None],
            [None, None, None, None, 'F'],
            ['F', 'F', 'F', None, None],
            [None, None, None, None, 'F'],
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
                    [None, None, 2, None, 1],
                    [1, None, None, None, None],
                    [None, 3, None, 3, None],
                    [None, 2, None, None, 3],
                    [1, 2, 3, None, 2],
                ]
            },
            'answer': [
                [None, None, None, 'F', None],
                [None, 'F', None, None, None],
                [None, None, None, None, 'F'],
                ['F', None, 'F', 'F', None],
                [None, None, None, 'F', None],
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
    ret = construct_minesweeper_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_minesweeper_data(puzzle)
    print(ret)
