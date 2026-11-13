import os
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# The numbers are from 1 to the size of the grid i.e. 1 to 5 for a 5x5 puzzle.
# Each row and column must contain only one instance of each number.
# The numbers should satisfy the comparison signs (or inequality symbols) - less than or greater than.
# For bigger puzzles the letters (A,B,C etc.) follow after the number 9.
# 
# **Coordinates & Output:**
# 1. **Grid System:**
#    - Cell centers are at integer coordinates `(row, col)`.
#    - Horizontal inequalities are at `(row, col+0.5)` with symbols `<` or `>`.
#    - Vertical inequalities are at `(row+0.5, col)` with symbols `^` or `v`.
#    - Top-left is `(0, 0)`; `row` increases downwards, `col` increases rightwards.
# 
# 2. **Symbol Meaning:**
#    - At `(row, col+0.5)`: `<` means left cell < right cell, `>` means left cell > right cell.
#    - At `(row+0.5, col)`: `^` means upper cell < lower cell, `v` means upper cell > lower cell.
# 
# 3. **Required Format:**
#    - **Observation:**
#      `{'numbers': {(row, col): value, ...}, 'inequalities': {(r, c): symbol, ...}}`
#    - **Answer:**
#      A fully solved grid as a 2D list.
# '''

RULES = '''
**Core Rules:**
The numbers are from 1 to the size of the grid (e.g. 1..5 for a 5x5 puzzle).
Each row and column must contain each number exactly once.
The numbers must satisfy all inequality signs.

**Coordinates & Output:**
1. Cell centers are at integer coordinates `(row, col)`.
2. Horizontal inequalities are stored at `(row, col+0.5)` with symbols `<` or `>`.
3. Vertical inequalities are stored at `(row+0.5, col)` with symbols `^` or `v`.
4. Top-left is `(0, 0)`; `row` increases downward, `col` increases rightward.
5. **Observation:** a dictionary with:
   - `data`: `N x N` 2D list (givens are ints, empty cells are `None`)
   - `horizontal`: dict `{'(row, col+0.5)': '<' or '>'}`
   - `vertical`: dict `{'(row+0.5, col)': '^' or 'v'}`
6. **Answer:** full solved `N x N` 2D list.
'''


def _normalize_constraint_positions(h_constraints, v_constraints):
    """
    Normalize inequalities to midpoint coordinates.

    Compatible input styles:
    - Horizontal old style: {(row, col): '<'/'>'} -> (row, col+0.5)
    - Vertical old style: {(row, col): '^'/'v'} -> (row+0.5, col)
    - Midpoint style is kept as-is.
    """
    h_mid = {}
    for (r, c), symbol in (h_constraints or {}).items():
        r = float(r)
        c = float(c)
        if c.is_integer():
            h_mid[(r, c + 0.5)] = symbol
        else:
            h_mid[(r, c)] = symbol

    v_mid = {}
    for (r, c), symbol in (v_constraints or {}).items():
        r = float(r)
        c = float(c)
        if r.is_integer():
            v_mid[(r + 0.5, c)] = symbol
        else:
            v_mid[(r, c)] = symbol

    return h_mid, v_mid


def draw_futoshiki(grid, h_constraints=None, v_constraints=None, output_path=None, answer=None):
    """
    Draw a Futoshiki board.

    grid: clue grid with integers or None.
    answer: optional solved grid (2D list). If provided, blanks in `grid` are filled in blue.
    """
    n = len(grid)
    h_constraints, v_constraints = _normalize_constraint_positions(h_constraints, v_constraints)

    fig, ax = plt.subplots(figsize=(n + 0.8, n + 0.8))

    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(-0.5, n - 0.5)

    ticks = [i / 2.0 for i in range((n - 1) * 2 + 1)]
    tick_labels = [f"{t:g}" for t in ticks]
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels(tick_labels)
    ax.set_yticklabels(tick_labels)
    ax.xaxis.tick_top()
    ax.invert_yaxis()

    for r in range(n):
        for c in range(n):
            rect = plt.Rectangle(
                (c - 0.4, r - 0.4),
                0.8,
                0.8,
                fill=False,
                edgecolor='black',
                linewidth=1.5,
            )
            ax.add_patch(rect)

            val = grid[r][c]
            if val is not None:
                ax.text(c, r, str(val), va='center', ha='center', fontsize=18, fontweight='bold', color='black')
            elif answer is not None and answer[r][c] is not None:
                ax.text(c, r, str(answer[r][c]), va='center', ha='center', fontsize=18, color='#1A73B8', fontweight='bold')

    symbol_style = dict(
        fontsize=16,
        fontweight='bold',
        color='#0D47A1',
        bbox=dict(
            boxstyle='round,pad=0.12',
            facecolor='white',
            edgecolor='#0D47A1',
            linewidth=1.0,
            alpha=0.95,
        ),
        zorder=6,
    )
    symbol_effects = [pe.withStroke(linewidth=1.8, foreground='white')]

    h_latex_map = {'<': r'$<$', '>': r'$>$'}
    for (r, c), symbol in h_constraints.items():
        display_char = h_latex_map.get(symbol, symbol)
        txt = ax.text(c, r, display_char, va='center', ha='center', **symbol_style)
        txt.set_path_effects(symbol_effects)

    v_latex_map = {'^': r'$\wedge$', 'v': r'$\vee$'}
    for (r, c), symbol in v_constraints.items():
        display_char = v_latex_map.get(symbol, symbol)
        txt = ax.text(c, r, display_char, va='center', ha='center', **symbol_style)
        txt.set_path_effects(symbol_effects)

    for spine in ax.spines.values():
        spine.set_edgecolor('#4A90E2')
        spine.set_linewidth(2)

    ax.set_aspect('equal')
    plt.tight_layout()
    if output_path:
        save_square_figure(fig, output_path)
    plt.close()


def format_futoshiki_to_string(grid, h_constraints=None, v_constraints=None, answer=None):
    """
    ASCII format for debugging / text export.
    """
    n = len(grid)
    h_constraints, v_constraints = _normalize_constraint_positions(h_constraints, v_constraints)

    shown = []
    for r in range(n):
        row_vals = []
        for c in range(n):
            if grid[r][c] is not None:
                row_vals.append(grid[r][c])
            elif answer is not None:
                row_vals.append(answer[r][c])
            else:
                row_vals.append('.')
        shown.append(row_vals)

    lines = []
    for r in range(n):
        row_parts = []
        for c in range(n):
            row_parts.append(str(shown[r][c]))
            if c < n - 1:
                row_parts.append(h_constraints.get((float(r), c + 0.5), ' '))
        lines.append(' '.join(row_parts))

        if r < n - 1:
            mid_parts = []
            for c in range(n):
                mid_parts.append(v_constraints.get((r + 0.5, float(c)), ' '))
                if c < n - 1:
                    mid_parts.append(' ')
            lines.append(' '.join(mid_parts))

    return '\n'.join(lines)


def construct_futoshiki_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'futoshiki'))
    os.makedirs(output_dir, exist_ok=True)

    fig_name = f"futoshiki_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_futoshiki(
        puzzle_dict['original_data']['data'],
        h_constraints=puzzle_dict['original_data'].get('horizontal', {}),
        v_constraints=puzzle_dict['original_data'].get('vertical', {}),
        output_path=os.path.join(output_dir, f"{fig_name}.png"),
    )

    answer_fig_name = f"futoshiki_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_futoshiki(
        puzzle_dict['original_data']['data'],
        h_constraints=puzzle_dict['original_data'].get('horizontal', {}),
        v_constraints=puzzle_dict['original_data'].get('vertical', {}),
        output_path=os.path.join(output_dir, f"{answer_fig_name}.png"),
        answer=puzzle_dict['answer'],
    )

    output_dict = {'puzzle': 'futoshiki'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name

    output_dict['initial_str'] = format_futoshiki_to_string(
        puzzle_dict['original_data']['data'],
        h_constraints=puzzle_dict['original_data'].get('horizontal', {}),
        v_constraints=puzzle_dict['original_data'].get('vertical', {}),
    )
    output_dict['answer_str'] = format_futoshiki_to_string(
        puzzle_dict['original_data']['data'],
        h_constraints=puzzle_dict['original_data'].get('horizontal', {}),
        v_constraints=puzzle_dict['original_data'].get('vertical', {}),
        answer=puzzle_dict['answer'],
    )

    return output_dict


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
                new_d[_key_to_str(parsed)] = v
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
    return


def get_observation(data):
    data = normalize_size_keys(data)
    # Keep the raw futoshiki layout so the solver can always read board size
    # from the data grid, even when there are no given numbers.
    return {
        'data': data['original_data']['data'],
        'horizontal': data['original_data'].get('horizontal', {}),
        'vertical': data['original_data'].get('vertical', {}),
    }

def return_data():
    ref_puzzle_dict = {
        'column/row': 4,
        'level': 'easy',
        'original_data': {
            'data': [
                [None, None, None, 4],
                [None, None, None, None],
                [None, None, 2, None],
                [3, None, None, 1],
            ],
            'horizontal': {},
            'vertical': {
                (0.5, 2): '^',
                (1.5, 1): '^',
            },
        },
        'answer': [
            [2, 3, 1, 4],
            [4, 1, 3, 2],
            [1, 4, 2, 3],
            [3, 2, 4, 1],
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
                'data': [
                    [None, None, None, 2],
                    [None, None, None, None],
                    [None, None, None, None],
                    [None, None, None, None],
                ],
                'horizontal': {
                    (0, 0.5): '>',
                    (0, 2.5): '<',
                },
                'vertical': {
                    (0.5, 3): '^',
                    (2.5, 1): 'v',
                    (2.5, 3): 'v',
                },
            },
            'answer': [
                [4, 3, 1, 2],
                [2, 1, 3, 4],
                [1, 4, 2, 3],
                [3, 2, 4, 1]
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
    ret = construct_futoshiki_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_futoshiki_data(puzzle)
    print(ret)
