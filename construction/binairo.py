import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


RULES = '''
**Core Rules:**
Fill every cell with `B` or `W` so that:
1. Each row and each column contain the same number of black and white cells.
2. No row or column has three consecutive cells of the same color.
3. All rows are pairwise different, and all columns are pairwise different.
4. Given cells must stay fixed.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has one part:
   - `data`: initial grid as list of lists using `'B'`, `'W'`, or `None`.
4. **Answer:** full solved grid as list of lists using `'B'` / `'W'`.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_GRID = '#C8C8C8'
COLOR_FRAME = '#000000'
STONE_BLACK = '#050505'
STONE_WHITE = '#F2F2F2'
STONE_WHITE_EDGE = '#111111'
STONE_HL_BLACK = '#7A7A7A'
STONE_HL_WHITE = '#FFFFFF'


def _norm_cell(v):
    if v is None:
        return None
    s = str(v).upper()
    if s in ('B', 'W'):
        return s
    return None


def _normalize_grid(grid, n=None):
    if not isinstance(grid, list) or not grid:
        raise ValueError('data must be a non-empty list of lists.')
    if not isinstance(grid[0], list):
        raise ValueError('data must be a 2D list.')
    ret = [[_norm_cell(v) for v in row] for row in grid]
    if n is not None:
        if len(ret) != n:
            raise ValueError('data size does not match board size.')
        for row in ret:
            if len(row) != n:
                raise ValueError('data must be square and match board size.')
    return ret


def _draw_board(ax, n):
    for r in range(n):
        for c in range(n):
            rect = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                linewidth=1.1,
                edgecolor=COLOR_GRID,
                facecolor=COLOR_CELL,
                zorder=1,
            )
            ax.add_patch(rect)
    frame = patches.Rectangle((-0.5, -0.5), n, n, fill=False, edgecolor=COLOR_FRAME, linewidth=2.0, zorder=3)
    ax.add_patch(frame)


def _draw_stone(ax, r, c, val):
    is_black = val == 'B'
    fill = STONE_BLACK if is_black else STONE_WHITE
    edge = '#000000' if is_black else STONE_WHITE_EDGE
    stone = patches.Circle((c, r), radius=0.34, facecolor=fill, edgecolor=edge, linewidth=1.8, zorder=5)
    ax.add_patch(stone)
    hl_color = STONE_HL_BLACK if is_black else STONE_HL_WHITE
    highlight = patches.Circle((c - 0.10, r - 0.09), radius=0.05, facecolor=hl_color, edgecolor='none', alpha=0.85, zorder=6)
    ax.add_patch(highlight)


def draw_binairo(initial_grid, output_path, answer=None):
    n = len(initial_grid)
    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_board(ax, n)

    render_grid = answer if answer is not None else initial_grid
    for r in range(n):
        for c in range(n):
            v = _norm_cell(render_grid[r][c])
            if v in ('B', 'W'):
                _draw_stone(ax, r, c, v)

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


def format_binairo_to_string(initial_grid, answer_grid=None):
    g = answer_grid if answer_grid is not None else initial_grid
    lines = [f"data={initial_grid}"]
    for row in g:
        lines.append(' '.join(_norm_cell(v) if _norm_cell(v) is not None else '.' for v in row))
    return '\n'.join(lines)


def construct_binairo_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'binairo'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    initial_grid = _normalize_grid(puzzle_dict['original_data']['data'], n=n)
    answer_grid = _normalize_grid(puzzle_dict['answer'], n=n)

    fig_name = f"binairo_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_binairo(initial_grid, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"binairo_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_binairo(initial_grid, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=answer_grid)

    output_dict = {'puzzle': 'binairo'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_binairo_to_string(initial_grid)
    output_dict['answer_str'] = format_binairo_to_string(initial_grid, answer_grid=answer_grid)
    return output_dict


def _no_three_consecutive(line):
    for i in range(len(line) - 2):
        if line[i] == line[i + 1] == line[i + 2]:
            return False
    return True


def _check_unique_rows_cols(grid):
    row_tuples = [tuple(row) for row in grid]
    if len(set(row_tuples)) != len(row_tuples):
        return False
    n = len(grid)
    cols = [tuple(grid[r][c] for r in range(n)) for c in range(n)]
    if len(set(cols)) != len(cols):
        return False
    return True


def test_observation(observation, gt_observation):
    """Test if observation matches gt_observation. Handles JSON str keys in horizontal/vertical."""

    def _norm(obs):
        if not isinstance(obs, dict):
            return obs
        out = dict(obs)
        for key in ('horizontal', 'vertical'):
            d = out.get(key)
            if not isinstance(d, dict):
                continue
            new_d = {}
            for k, v in d.items():
                if isinstance(k, (tuple, list)) and len(k) == 2:
                    new_d[(float(k[0]), float(k[1]))] = v
                elif isinstance(k, str):
                    p = k.replace('(', '').replace(')', '').split(',')
                    if len(p) == 2:
                        new_d[(float(p[0].strip()), float(p[1].strip()))] = v
            out[key] = new_d
        return out

    return _norm(observation) == gt_observation


def test_answer(answer, gt_answer):
    """Test if answer matches gt_answer. Handles 'No Solution' case-insensitively."""
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

    initial = observation.get('data')
    if initial is None:
        return False
    initial = _normalize_grid(initial)
    answer = _normalize_grid(answer, n=len(initial))
    n = len(answer)
    if n % 2 != 0:
        return False

    for r in range(n):
        for c in range(n):
            if initial[r][c] is not None and answer[r][c] != initial[r][c]:
                return False

    half = n // 2
    for r in range(n):
        row = answer[r]
        if any(v not in ('B', 'W') for v in row):
            return False
        if row.count('B') != half or row.count('W') != half:
            return False
        if not _no_three_consecutive(row):
            return False

    for c in range(n):
        col = [answer[r][c] for r in range(n)]
        if col.count('B') != half or col.count('W') != half:
            return False
        if not _no_three_consecutive(col):
            return False

    if not _check_unique_rows_cols(answer):
        return False

    if gt_answer is None:
        return True
    return answer == _normalize_grid(gt_answer, n=n)


def get_observation(data):
    data = normalize_size_keys(data)
    n = data['column/row']
    initial = _normalize_grid(data['original_data']['data'], n=n)
    return {'data': initial}


def return_data():
    ref_puzzle_dict = {
        'column/row': 6,
        'level': 'easy',
        'original_data': {
            'data': [
                [None, None, None, None, 'W', None],
                [None, None, None, None, 'W', None],
                [None, 'W', 'B', None, None, 'W'],
                ['B', None, 'B', None, None, 'B'],
                [None, None, None, None, None, None],
                ['W', None, None, 'W', None, 'W'],
            ]
        },
        'answer': [
            ['B', 'W', 'W', 'B', 'W', 'B'],
            ['W', 'B', 'W', 'B', 'W', 'B'],
            ['B', 'W', 'B', 'W', 'B', 'W'],
            ['B', 'W', 'B', 'W', 'W', 'B'],
            ['W', 'B', 'W', 'B', 'B', 'W'],
            ['W', 'B', 'B', 'W', 'B', 'W'],
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
                    ['W', None, None, None, None, 'W'],
                    [None, None, None, None, None, None],
                    [None, None, None, 'W', None, 'B'],
                    [None, 'W', None, 'W', None, None],
                    [None, None, None, None, None, None],
                    [None, 'W', None, None, 'W', 'W'],
                ]
            },
            'answer': [
                ['W', 'B', 'B', 'W', 'B', 'W'],
                ['B', 'W', 'W', 'B', 'W', 'B'],
                ['W', 'B', 'W', 'W', 'B', 'B'],
                ['B', 'W', 'B', 'W', 'B', 'W'],
                ['W', 'B', 'W', 'B', 'W', 'B'],
                ['B', 'W', 'B', 'B', 'W', 'W'],
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
    ret = construct_binairo_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_binairo_data(puzzle)
    print(ret)
