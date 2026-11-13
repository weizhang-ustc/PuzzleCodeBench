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
3. A `=` constraint means the two adjacent cells are the same color.
4. A `x` constraint means the two adjacent cells are different colors.
5. Given cells must stay fixed.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has three parts:
   - `data`: initial grid as list of lists using `'B'`, `'W'`, or `None`.
   - `horizontal`: dict `{'(row, col+0.5)': '=' or 'x'}` for constraints between left-right neighbors.
   - `vertical`: dict `{'(row+0.5, col)': '=' or 'x'}` for constraints between up-down neighbors.
4. **Answer:** full solved grid as list of lists using `'B'` / `'W'`.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_GRID = '#C8C8C8'
COLOR_FRAME = '#000000'
COLOR_CONSTRAINT = '#9A9A9A'
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


def _normalize_constraint_positions(h_constraints, v_constraints):
    """
    Normalize to midpoint coordinates.
    Compatible formats:
    - Horizontal old style: (row, col) -> (row, col+0.5)
    - Vertical old style: (row, col) -> (row+0.5, col)
    - Midpoint style is kept.
    """
    h_mid = {}
    for (r, c), sym in (h_constraints or {}).items():
        r = float(r)
        c = float(c)
        s = str(sym).strip()
        if s not in ('=', 'x', 'X'):
            continue
        if c.is_integer():
            h_mid[(r, c + 0.5)] = 'x' if s in ('x', 'X') else '='
        else:
            h_mid[(r, c)] = 'x' if s in ('x', 'X') else '='

    v_mid = {}
    for (r, c), sym in (v_constraints or {}).items():
        r = float(r)
        c = float(c)
        s = str(sym).strip()
        if s not in ('=', 'x', 'X'):
            continue
        if r.is_integer():
            v_mid[(r + 0.5, c)] = 'x' if s in ('x', 'X') else '='
        else:
            v_mid[(r, c)] = 'x' if s in ('x', 'X') else '='

    return h_mid, v_mid


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


def _draw_constraints(ax, h_constraints, v_constraints):
    for (r, c), sym in h_constraints.items():
        if sym == 'x':
            d = 0.08
            ax.plot([c - d, c + d], [r - d, r + d], color=COLOR_CONSTRAINT, linewidth=3.0, zorder=7, solid_capstyle='round')
            ax.plot([c - d, c + d], [r + d, r - d], color=COLOR_CONSTRAINT, linewidth=3.0, zorder=7, solid_capstyle='round')
        else:
            ax.text(
                c,
                r,
                sym,
                ha='center',
                va='center',
                fontsize=24,
                fontweight='bold',
                color=COLOR_CONSTRAINT,
                zorder=7,
            )
    for (r, c), sym in v_constraints.items():
        if sym == 'x':
            d = 0.08
            ax.plot([c - d, c + d], [r - d, r + d], color=COLOR_CONSTRAINT, linewidth=3.0, zorder=7, solid_capstyle='round')
            ax.plot([c - d, c + d], [r + d, r - d], color=COLOR_CONSTRAINT, linewidth=3.0, zorder=7, solid_capstyle='round')
        else:
            rotation = 90 if sym == '=' else 0
            y = r - 0.03 if sym == '=' else r
            ax.text(
                c,
                y,
                sym,
                ha='center',
                va='center',
                fontsize=24,
                fontweight='bold',
                color=COLOR_CONSTRAINT,
                rotation=rotation,
                zorder=7,
            )


def draw_binairoplus(initial_grid, h_constraints, v_constraints, output_path, answer=None):
    n = len(initial_grid)
    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_board(ax, n)
    _draw_constraints(ax, h_constraints, v_constraints)

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


def format_binairoplus_to_string(initial_grid, h_constraints, v_constraints, answer_grid=None):
    g = answer_grid if answer_grid is not None else initial_grid
    lines = [
        f"data={initial_grid}",
        f"horizontal={h_constraints}",
        f"vertical={v_constraints}",
    ]
    for row in g:
        lines.append(' '.join(_norm_cell(v) if _norm_cell(v) is not None else '.' for v in row))
    return '\n'.join(lines)


def construct_binairoplus_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'binairoplus'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    original = puzzle_dict['original_data']
    initial_grid = _normalize_grid(original['data'], n=n)
    answer_grid = _normalize_grid(puzzle_dict['answer'], n=n)
    h_constraints, v_constraints = _normalize_constraint_positions(
        original.get('horizontal', {}),
        original.get('vertical', {}),
    )

    fig_name = f"binairoplus_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_binairoplus(initial_grid, h_constraints, v_constraints, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"binairoplus_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_binairoplus(
        initial_grid,
        h_constraints,
        v_constraints,
        output_path=os.path.join(output_dir, f'{answer_fig_name}.png'),
        answer=answer_grid,
    )

    output_dict = {'puzzle': 'binairoplus'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_binairoplus_to_string(initial_grid, h_constraints, v_constraints)
    output_dict['answer_str'] = format_binairoplus_to_string(initial_grid, h_constraints, v_constraints, answer_grid=answer_grid)
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


def _check_constraints(answer, h_constraints, v_constraints):
    n = len(answer)
    for (r, c), sym in h_constraints.items():
        rr = int(round(r))
        c_left = int(round(c - 0.5))
        c_right = c_left + 1
        if not (0 <= rr < n and 0 <= c_left < n and 0 <= c_right < n):
            return False
        a, b = answer[rr][c_left], answer[rr][c_right]
        if sym == '=' and a != b:
            return False
        if sym == 'x' and a == b:
            return False

    for (r, c), sym in v_constraints.items():
        cc = int(round(c))
        r_up = int(round(r - 0.5))
        r_down = r_up + 1
        if not (0 <= cc < n and 0 <= r_up < n and 0 <= r_down < n):
            return False
        a, b = answer[r_up][cc], answer[r_down][cc]
        if sym == '=' and a != b:
            return False
        if sym == 'x' and a == b:
            return False
    return True


def test_observation(observation, gt_observation):
    """Test if observation matches gt_observation.

    Accept key formats in `horizontal`/`vertical` as:
    - tuple/list: (r, c)
    - string: "a,b" or "(a,b)"
    and compare with a canonical string-key representation.
    """

    def _parse_key(k):
        if isinstance(k, (tuple, list)) and len(k) == 2:
            return float(k[0]), float(k[1])
        if isinstance(k, str):
            t = k.strip()
            if t.startswith('(') and t.endswith(')'):
                t = t[1:-1]
            parts = t.split(',')
            if len(parts) == 2:
                try:
                    return float(parts[0].strip()), float(parts[1].strip())
                except Exception:
                    return None
        return None

    def _fmt_num(x):
        return str(int(x)) if float(x).is_integer() else str(float(x))

    def _key_to_str(rc):
        r, c = rc
        return f"({_fmt_num(r)},{_fmt_num(c)})"

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
                parsed = _parse_key(k)
                if parsed is None:
                    continue
                s = str(v).strip()
                if s in ('X', 'x'):
                    s = 'x'
                if s not in ('=', 'x'):
                    continue
                new_d[_key_to_str(parsed)] = s
            out[key] = new_d
        return out

    return _norm(observation) == _norm(gt_observation)


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
    h_constraints = observation.get('horizontal', {})
    v_constraints = observation.get('vertical', {})
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

    h_constraints, v_constraints = _normalize_constraint_positions(h_constraints, v_constraints)
    if not _check_constraints(answer, h_constraints, v_constraints):
        return False

    if gt_answer is None:
        return True
    return answer == _normalize_grid(gt_answer, n=n)


def get_observation(data):
    data = normalize_size_keys(data)
    n = data['column/row']
    original = data['original_data']
    initial = _normalize_grid(original['data'], n=n)
    h_constraints, v_constraints = _normalize_constraint_positions(
        original.get('horizontal', {}),
        original.get('vertical', {}),
    )
    return {
        'data': initial,
        'horizontal': h_constraints,
        'vertical': v_constraints,
    }


def return_data():
    ref_puzzle_dict = {
        'column/row': 6,
        'level': 'easy',
        'original_data': {
            'data': [
                ['W', None, None, None, None, None],
                ['W', None, None, None, None, None],
                [None, 'W', None, 'B', None, None],
                [None, None, 'B', None, 'W', None],
                [None, None, None, None, None, 'W'],
                [None, None, None, None, None, 'W'],
            ],
            'horizontal': {
                (2, 4.5): '=',
                (3, 0.5): 'x',
            },
            'vertical': {
                (0.5, 1): '=',
                (0.5, 3): '=',
                (2.5, 0): '=',
                (2.5, 5): 'x',
                (4.5, 2): '=',
                (4.5, 4): '=',
            },
        },
        'answer': [
            ['W', 'B', 'B', 'W', 'W', 'B'],
            ['W', 'B', 'W', 'W', 'B', 'B'],
            ['B', 'W', 'B', 'B', 'W', 'W'],
            ['B', 'W', 'B', 'W', 'W', 'B'],
            ['W', 'B', 'W', 'B', 'B', 'W'],
            ['B', 'W', 'W', 'B', 'B', 'W'],
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
                    [None, 'W', None, None, 'B', None],
                    [None, None, None, None, None, None],
                    [None, None, None, None, None, None],
                    [None, None, 'W', 'W', None, None],
                    [None, None, None, None, None, None],
                    ['B', 'W', None, None, 'W', 'W'],
                ],
                'horizontal': {
                    (1, 1.5): 'x',
                    (1, 3.5): '=',
                    (3, 0.5): '=',
                    (3, 4.5): 'x',
                },
                'vertical': {
                    (3.5, 1): '=',
                    (3.5, 4): 'x',
                },
            },
            'answer': [
                ['W', 'W', 'B', 'W', 'B', 'B'],
                ['W', 'B', 'W', 'B', 'B', 'W'],
                ['B', 'W', 'B', 'W', 'W', 'B'],
                ['B', 'B', 'W', 'W', 'B', 'W'],
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
    ret = construct_binairoplus_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_binairoplus_data(puzzle)
    print(ret)
