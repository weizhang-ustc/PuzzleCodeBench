import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# Place light bulbs on white cells so that:
# 1. Every white cell is illuminated by at least one bulb.
# 2. A bulb illuminates along its row and column until blocked by a black cell.
# 3. No bulb may illuminate another bulb.
# 4. Numbered black cells indicate exactly how many orthogonally adjacent bulbs they must have.
# 
# **Coordinates & Output:**
# 1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
# 2. `row` increases top-to-bottom, `col` increases left-to-right.
# 3. **Observation:** dictionary of black cells only.
#    - Numbered black cell: `(r, c): k`
#    - Plain black cell: `(r, c): -1`
# 4. **Answer:** same-sized grid using `'B'` for bulb cells and `None` for non-bulb cells.
# '''

RULES = '''
**Core Rules:**
Place light bulbs on white cells so that:
1. Every white cell is illuminated by at least one bulb.
2. A bulb illuminates along its row and column until blocked by a black cell.
3. No bulb may illuminate another bulb.
4. Numbered black cells indicate exactly how many orthogonally adjacent bulbs they must have.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has one part:
   - `data`: `N x N` 2D list for board blocks (`None` / `-1` / `0..4`).
4. **Answer:** `N x N` grid using `'B'` for bulb cells and `None` for non-bulb cells.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_GRID = '#4F4F4F'
COLOR_FRAME = '#000000'
COLOR_BLACK_CELL = '#111111'
COLOR_BLACK_TEXT = '#FFFFFF'
COLOR_BULB_FILL = '#FFFFFF'
COLOR_BULB_EDGE = '#111111'


def _normalize_black_grid(data, n=None):
    if isinstance(data, dict):
        if n is None:
            n = max((max(r for r, _ in data.keys()) if data else 0), (max(c for _, c in data.keys()) if data else 0)) + 1
        grid = [[None for _ in range(n)] for _ in range(n)]
        for (r, c), v in data.items():
            grid[r][c] = v
        return grid

    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError('lightup data must be a dict or 2D list.')

    grid = [row[:] for row in data]
    if n is not None and (len(grid) != n or any(len(row) != n for row in grid)):
        raise ValueError('lightup data must be n x n.')
    return grid


def _black_grid_to_dict(grid):
    ret = {}
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v is not None:
                ret[(r, c)] = v
    return ret


def _draw_cells(ax, n):
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


def _draw_black_cells(ax, black_cells):
    for (r, c), val in black_cells.items():
        rect = patches.Rectangle(
            (c - 0.5, r - 0.5),
            1,
            1,
            facecolor=COLOR_BLACK_CELL,
            edgecolor=COLOR_GRID,
            linewidth=1.1,
            zorder=2,
        )
        ax.add_patch(rect)

        if val != -1:
            ax.text(
                c,
                r,
                str(val),
                ha='center',
                va='center',
                fontsize=22,
                fontweight='bold',
                color=COLOR_BLACK_TEXT,
                zorder=3,
            )


def _draw_bulbs(ax, answer):
    n = len(answer)
    for r in range(n):
        for c in range(n):
            if answer[r][c] == 'B':
                # bulb head
                circ = patches.Circle((c, r - 0.04), radius=0.23, facecolor=COLOR_BULB_FILL, edgecolor=COLOR_BULB_EDGE, linewidth=1.9, zorder=4)
                ax.add_patch(circ)
                # bulb base
                base = patches.Rectangle((c - 0.09, r + 0.14), 0.18, 0.09, facecolor=COLOR_BULB_EDGE, edgecolor=COLOR_BULB_EDGE, linewidth=1.0, zorder=4)
                ax.add_patch(base)
                # filament mark
                ax.plot([c - 0.07, c + 0.07], [r - 0.02, r - 0.02], color=COLOR_BULB_EDGE, linewidth=1.1, zorder=5)


def draw_lightup(black_cells, n, output_path, answer=None):
    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_cells(ax, n)
    _draw_black_cells(ax, black_cells)
    if answer is not None:
        _draw_bulbs(ax, answer)

    # strong outer border
    frame = patches.Rectangle((-0.5, -0.5), n, n, fill=False, edgecolor=COLOR_FRAME, linewidth=2.8, zorder=6)
    ax.add_patch(frame)

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


def format_lightup_to_string(n, black_grid, answer=None):
    black_grid = _normalize_black_grid(black_grid, n=n)
    lines = [f"black_cells={_black_grid_to_dict(black_grid)}"]
    for r in range(n):
        row_tokens = []
        for c in range(n):
            v = black_grid[r][c]
            if v is not None:
                row_tokens.append('#' if v == -1 else str(v))
            elif answer is not None and answer[r][c] == 'B':
                row_tokens.append('B')
            else:
                row_tokens.append('.')
        lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_lightup_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'lightup'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    black_grid = _normalize_black_grid(puzzle_dict['original_data']['data'], n=n)
    black_cells = _black_grid_to_dict(black_grid)

    fig_name = f"lightup_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_lightup(black_cells, n, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"lightup_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_lightup(black_cells, n, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'lightup'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_lightup_to_string(n, black_grid)
    output_dict['answer_str'] = format_lightup_to_string(n, black_grid, answer=puzzle_dict['answer'])

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
    return {'data': _normalize_black_grid(data['original_data']['data'], n=n)}


def return_data():
    ref_puzzle_dict = {
        'column/row': 7,
        'level': 'easy',
        'original_data': {
            # 'data': {
            #     (0, 2): -1,
            #     (0, 3): 1,
            #     (2, 6): 2,
            #     (3, 0): 1,
            #     (3, 6): 0,
            #     (4, 0): 1,
            #     (6, 3): 1,
            #     (6, 4): -1,
            # },
            'data': [
                [None, None, -1, 1, None, None, None],
                [None, None, None, None, None, None, None],
                [None, None, None, None, None, None, 2],
                [1, None, None, None, None, None, 0],
                [1, None, None, None, None, None, None],
                [None, None, None, None, None, None, None],
                [None, None, None, 1, -1, None, None],
            ],
        },
        'answer': [
            ['B', None, None, None, 'B', None, None],
            [None, None, None, None, None, None, 'B'],
            [None, None, None, None, None, 'B', None],
            [None, 'B', None, None, None, None, None],
            [None, None, None, 'B', None, None, None],
            ['B', None, None, None, None, None, None],
            [None, None, 'B', None, None, None, 'B'],
        ],
        'id': 'ref',
        'rules': RULES,
    }
    ref_puzzle_dict['observation'] = get_observation(ref_puzzle_dict)

    puzzles = [
        {
            'column/row': 7,
            'level': 'easy',
            'original_data': {
                # 'data': {
                #     (0, 2): 3,
                #     (0, 4): 1,
                #     (1, 4): -1,
                #     (2, 0): -1,
                #     (2, 1): -1,
                #     (2, 6): 0,
                #     (3, 3): -1,
                #     (4, 0): 0,
                #     (4, 5): 0,
                #     (4, 6): 0,
                #     (5, 2): -1,
                #     (6, 2): 0,
                #     (6, 4): 1,
                # },
                'data': [
                    [None, None, 3, None, 1, None, None],
                    [None, None, None, None, -1, None, None],
                    [-1, -1, None, None, None, None, 0],
                    [None, None, None, -1, None, None, None],
                    [0, None, None, None, None, 0, 0],
                    [None, None, -1, None, None, None, None],
                    [None, None, 0, None, 1, None, None],
                ]
            },
            'answer': [
                [None, 'B', None, 'B', None, None, 'B'],
                [None, None, 'B', None, None, 'B', None],
                [None, None, None, None, None, None, None],
                [None, 'B', None, None, 'B', None, None],
                [None, None, None, None, None, None, None],
                [None, None, None, 'B', None, None, None],
                ['B', None, None, None, None, 'B', None],
            ],
            'id': 'example_0',
            'rules': RULES,
        },
        {
            'column/row': 10,
            'level': 'medium',
            'original_data': {
                # 'data': {
                #     (0, 2): -1,
                #     (0, 7): 2,
                #     (1, 4): 0,
                #     (1, 7): 1,
                #     (2, 0): 1,
                #     (2, 1): -1,
                #     (2, 4): -1,
                #     (2, 9): -1,
                #     (4, 7): 1,
                #     (4, 8): -1,
                #     (5, 1): -1,
                #     (5, 2): 1,
                #     (7, 0): 0,
                #     (7, 5): 0,
                #     (7, 8): 1,
                #     (7, 9): 0,
                #     (8, 2): 3,
                #     (8, 5): -1,
                #     (9, 2): -1,
                #     (9, 7): -1,
                # }
                'data': [
                    [None, None, -1, None, None, None, None, 2, None, None],
                    [None, None, None, None, 0, None, None, 1, None, None],
                    [1, -1, None, None, -1, None, None, None, None, -1],
                    [None, None, None, None, None, None, None, None, None, None],
                    [None, None, None, None, None, None, None, 1, -1, None],
                    [None, -1, 1, None, None, None, None, None, None, None],
                    [None, None, None, None, None, None, None, None, None, None],
                    [0, None, None, None, None, 0, None, None, 1, 0],
                    [None, None, 3, None, None, -1, None, None, None, None],
                    [None, None, -1, None, None, None, None, -1, None, None],
                ]
            },
            'answer': [
                [None, 'B', None, None, None, None, 'B', None, 'B', None],
                ['B', None, None, None, None, None, None, None, None, 'B'],
                [None, None, None, None, None, None, None, 'B', None, None],
                [None, None, None, None, None, 'B', None, None, None, None],
                [None, None, 'B', None, None, None, None, None, None, 'B'],
                ['B', None, None, None, None, None, None, 'B', None, None],
                [None, None, None, None, 'B', None, None, None, None, None],
                [None, None, 'B', None, None, None, None, None, None, None],
                [None, 'B', None, 'B', None, None, None, None, 'B', None],
                ['B', None, None, None, None, 'B', None, None, None, 'B'],
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
    ret = construct_lightup_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_lightup_data(puzzle)
    print(ret)
