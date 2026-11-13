import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# Place exactly one diagonal in every cell (`/` or `\\`) so that:
# 1. Each numbered dot has exactly that many incident diagonal segments.
# 2. The drawn segments must not form any closed loop.
# 
# **Coordinates & Output:**
# 1. Dot coordinates use `(row, col)` on an `(N+1) x (N+1)` point grid, top-left is `(0, 0)`.
# 2. Cell coordinates use `(row, col)` on an `N x N` cell grid, top-left cell is `(0, 0)`.
# 3. Both coordinate systems start from `0`, with `row` increasing top-to-bottom and `col` left-to-right.
# 4. **Observation:** dictionary for numbered dots only.
#    Example: `{(0, 1): 1, (2, 0): 1, ...}`
# 5. **Answer:** `N x N` grid using `'/'` or `'\\'` in every cell.
# '''

RULES = '''
**Core Rules:**
Place exactly one diagonal in every cell (`/` or `\\`) so that:
1. Each numbered dot has exactly that many incident diagonal segments.
2. The drawn segments must not form any closed loop.

**Coordinates & Output:**
1. Dot coordinates use `(row, col)` on an `(N+1) x (N+1)` point grid.
2. Cell coordinates use `(row, col)` on an `N x N` cell grid.
3. Top-left is `(0, 0)`; `row` increases top-to-bottom, `col` increases left-to-right.
4. **Observation** has one part:
   - `data`: `(N+1) x (N+1)` clue 2D list (`int` or `None`).
5. **Answer:** `N x N` 2D list (list of lists) where each cell element is either `'/'` or `'\\'`.
'''


COLOR_BG = '#F2F2F2'
COLOR_GRID = '#A8A8A8'
COLOR_FRAME = '#9A9A9A'
COLOR_LINE = '#111111'
COLOR_DOT = '#111111'
COLOR_CLUE_FACE = '#FFFFFF'
COLOR_CLUE_EDGE = '#222222'
COLOR_CLUE_TEXT = '#111111'

COLOR_DOT_AXIS = '#1B4F72'   # dot coordinates (integer grid)
COLOR_CELL_AXIS = '#B03A2E'  # cell coordinates (cell index grid)


def _normalize_clues_grid(data, n=None):
    if isinstance(data, dict):
        if not data:
            return [[None]]
        max_r = max(r for r, _ in data.keys())
        max_c = max(c for _, c in data.keys())
        size = max(max_r, max_c) + 1
        grid = [[None for _ in range(size)] for _ in range(size)]
        for (r, c), v in data.items():
            grid[r][c] = v
        return grid

    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError('slant clues must be a dict or 2D list.')

    grid = [row[:] for row in data]
    if n is not None and (len(grid) != n + 1 or any(len(row) != n + 1 for row in grid)):
        raise ValueError('slant clues grid must be (n+1) x (n+1).')
    return grid


def _clues_grid_to_dict(clues_grid):
    ret = {}
    for r, row in enumerate(clues_grid):
        for c, v in enumerate(row):
            if v is not None:
                ret[(r, c)] = v
    return ret


def _draw_grid(ax, n):
    # board frame
    frame = patches.Rectangle((0, 0), n, n, fill=False, edgecolor=COLOR_FRAME, linewidth=3.2, zorder=1)
    ax.add_patch(frame)

    # internal grid lines
    for i in range(1, n):
        ax.plot([0, n], [i, i], color=COLOR_GRID, linewidth=1.6, zorder=1)
        ax.plot([i, i], [0, n], color=COLOR_GRID, linewidth=1.6, zorder=1)


def _draw_dots_and_clues(ax, clues_grid, n):
    # all dots
    for r in range(n + 1):
        for c in range(n + 1):
            ax.plot(c, r, marker='o', markersize=3.6, color=COLOR_DOT, zorder=3)

    # numbered dots in circles
    for r in range(n + 1):
        for c in range(n + 1):
            val = clues_grid[r][c]
            if val is None:
                continue
            circle = patches.Circle((c, r), radius=0.28, facecolor=COLOR_CLUE_FACE, edgecolor=COLOR_CLUE_EDGE, linewidth=1.5, zorder=4)
            ax.add_patch(circle)
            ax.text(c, r, str(val), ha='center', va='center', fontsize=17, fontweight='bold', color=COLOR_CLUE_TEXT, zorder=5)


def _draw_answer(ax, answer):
    n = len(answer)
    for r in range(n):
        for c in range(n):
            mark = answer[r][c]
            if mark == '/':
                ax.plot([c + 1, c], [r, r + 1], color=COLOR_LINE, linewidth=2.8, solid_capstyle='round', zorder=2)
            elif mark == '\\':
                ax.plot([c, c + 1], [r, r + 1], color=COLOR_LINE, linewidth=2.8, solid_capstyle='round', zorder=2)


def _set_dual_coordinates(ax, n):
    # Dot coordinates on top/left (integers 0..n)
    dot_ticks = list(range(n + 1))
    ax.set_xticks(dot_ticks)
    ax.set_yticks(dot_ticks)
    ax.set_xticklabels([str(t) for t in dot_ticks], color=COLOR_DOT_AXIS, fontsize=11, fontweight='bold')
    ax.set_yticklabels([str(t) for t in dot_ticks], color=COLOR_DOT_AXIS, fontsize=11, fontweight='bold')
    ax.xaxis.tick_top()

    # Cell coordinates on bottom/right (indices 0..n-1 at centers)
    cell_ticks = [i + 0.5 for i in range(n)]
    ax_bottom = ax.secondary_xaxis('bottom')
    ax_bottom.set_xticks(cell_ticks)
    ax_bottom.set_xticklabels([str(i) for i in range(n)], color=COLOR_CELL_AXIS, fontsize=10)
    ax_bottom.tick_params(length=0)

    ax_right = ax.secondary_yaxis('right')
    ax_right.set_yticks(cell_ticks)
    ax_right.set_yticklabels([str(i) for i in range(n)], color=COLOR_CELL_AXIS, fontsize=10)
    ax_right.tick_params(length=0)

    # style hints for two coordinate systems
    ax.set_xlabel('Cell Col (0-based)', color=COLOR_CELL_AXIS, fontsize=9, labelpad=18)
    ax.xaxis.set_label_position('bottom')
    ax.set_ylabel('Dot Row (0-based)', color=COLOR_DOT_AXIS, fontsize=9, labelpad=10)


def draw_slant(clues_grid, output_path, answer=None):
    clues_grid = _normalize_clues_grid(clues_grid)
    # answer is N x N, clues are (N+1)x(N+1)
    if answer is not None:
        n = len(answer)
    else:
        n = len(clues_grid) - 1

    fig, ax = plt.subplots(figsize=(n + 1.9, n + 1.9))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_grid(ax, n)
    if answer is not None:
        _draw_answer(ax, answer)
    _draw_dots_and_clues(ax, clues_grid, n)
    _set_dual_coordinates(ax, n)

    ax.set_xlim(-0.35, n + 0.35)
    ax.set_ylim(-0.35, n + 0.35)
    ax.invert_yaxis()
    ax.set_aspect('equal')

    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout()
    save_square_figure(fig, output_path)
    plt.close()


def format_slant_to_string(clues_grid, answer=None, n=None):
    clues_grid = _normalize_clues_grid(clues_grid)
    if n is None:
        n = len(clues_grid) - 1

    lines = []
    lines.append(f'clues={_clues_grid_to_dict(clues_grid)}')
    if answer is None:
        for _ in range(n):
            lines.append('. ' * n)
    else:
        for r in range(n):
            lines.append(' '.join(answer[r]))
    return '\n'.join(lines)


def construct_slant_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'slant'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    clues = _normalize_clues_grid(puzzle_dict['original_data']['data'], n=n)

    fig_name = f"slant_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_slant(clues, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"slant_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_slant(clues, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'slant'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_slant_to_string(clues, n=n)
    output_dict['answer_str'] = format_slant_to_string(clues, answer=puzzle_dict['answer'], n=n)

    return output_dict


def test_observation(observation, gt_observation):
    """Clue grid; exact match."""
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
    n = data['column/row']
    return {'data': _normalize_clues_grid(data['original_data']['data'], n=n)}


def return_data():
    ref_puzzle_dict = {
        'column/row': 5,
        'level': 'easy',
        'original_data': {
            # 'data': {
            #     (0, 1): 1,
            #     (0, 2): 1,
            #     (0, 4): 1,
            #     (0, 5): 1,
            #     (1, 3): 1,
            #     (2, 0): 1,
            #     (2, 1): 3,
            #     (3, 0): 2,
            #     (3, 3): 3,
            #     (3, 5): 1,
            #     (4, 1): 2,
            #     (4, 3): 2,
            #     (4, 5): 0,
            #     (5, 0): 0,
            #     (5, 3): 0,
            # },
            'data': [
                [None, 1, 1, None, 1, 1],
                [None, None, None, 1, None, None],
                [1, 3, None, None, None, None],
                [2, None, None, 3, None, 1],
                [None, 2, None, 2, None, 0],
                [0, None, None, 0, None, None],
            ]
        },
        'answer': [
            ['/', '/', '/', '/', '/'],
            ['/', '/', '\\', '/', '/'],
            ['/', '\\', '\\', '\\', '/'],
            ['\\', '\\', '/', '\\', '/'],
            ['\\', '\\', '/', '\\', '\\'],
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
                # 'data': {
                #     (0,1): 0,
                #     (0,3): 1,
                #     (1,4): 4,
                #     (2,1): 2,
                #     (3,1): 1,
                #     (3,3): 3,
                #     (4,2): 3,
                #     (4,4): 3,
                #     (5,1): 0,
                #     (5,4): 0,
                # },
                'data': [
                    [None, 0, None, 1, None, None],
                    [None, None, None, None, 4, None],
                    [None, 2, None, None, None, None],
                    [None, 1, None, 3, None, None],
                    [None, None, 3, None, 3, None],
                    [None, 0, None, None, 0, None],
                ]
            },
            'answer': [
                ['\\', '/', '\\', '\\', '/'],
                ['/', '\\', '\\', '/', '\\'],
                ['/', '\\', '\\', '/', '/'],
                ['\\', '\\', '/', '/', '/'],
                ['/', '\\', '\\', '/', '\\'],
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
    ret = construct_slant_data(ref_puzzle_dict)
    ret = construct_slant_data(puzzles[0])
    print(ret)
