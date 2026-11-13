import os
import sys
import matplotlib.pyplot as plt

try:
    from construction._common import normalize_size_keys
    from construction._render import save_square_figure
except ModuleNotFoundError:
    # Allow running this file directly via `python construction/shingoki.py`.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from construction._common import normalize_size_keys
    from construction._render import save_square_figure


RULES = '''
**Core Rules:**
Draw lines between dots to form a single closed loop without crossings or branches.
The loop must pass through all clue circles, where:
1. `Wk` (white circle): the loop goes straight through the circle.
2. `Bk` (black circle): the loop turns at the circle.
3. The number `k` is the sum of the lengths of the two straight segments extending from that circle.

**Coordinates & Output:**
1. Dot coordinates are integer `(row, col)` on an `(N+1) x (N+1)` dot grid.
2. Top-left is `(0, 0)`; `row` increases downward, `col` increases rightward.
3. **Observation** has one part:
   - `data`: `(N+1) x (N+1)` 2D list; each entry is `None` or a clue token string like `'W3'` / `'B5'`.
4. **Answer:** an ordered closed loop path as a list of dot coordinates, e.g.
   `[(0,0), (0,1), (1,1), ..., (0,0)]`.
'''


def _normalize_grid(data):
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError('shingoki data must be a 2D list.')
    n_rows = len(data)
    if any(len(row) != n_rows for row in data):
        raise ValueError('shingoki data must be square (dot grid).')
    return [row[:] for row in data]


def _parse_clue(token):
    if token is None:
        return None
    if not isinstance(token, str) or len(token) < 2:
        return None

    clue_type = token[0].upper()
    if clue_type not in ('B', 'W'):
        return None

    try:
        value = int(token[1:])
    except ValueError:
        return None
    return clue_type, value


def draw_shingoki(grid, output_path, answer=None):
    grid = _normalize_grid(grid)
    n = len(grid) - 1

    fig, ax = plt.subplots(figsize=(n + 1.2, n + 1.2))

    # Draw all possible dot-to-dot segments as light grid lines.
    for r in range(n + 1):
        ax.plot([0, n], [n - r, n - r], color='#DDDDDD', linewidth=1.6, zorder=1)
    for c in range(n + 1):
        ax.plot([c, c], [0, n], color='#DDDDDD', linewidth=1.6, zorder=1)

    # Draw loop path.
    if answer:
        path_x = [pt[1] for pt in answer]
        path_y = [n - pt[0] for pt in answer]
        ax.plot(path_x, path_y, color='#111111', linewidth=3.6, solid_capstyle='round', zorder=2)

    # Draw lattice dots.
    for r in range(n + 1):
        for c in range(n + 1):
            ax.plot(c, n - r, 'ko', markersize=4.2, zorder=3)

    # Draw numbered black/white circles on dot coordinates.
    for r in range(n + 1):
        for c in range(n + 1):
            clue = _parse_clue(grid[r][c])
            if clue is None:
                continue
            clue_type, value = clue
            x = c
            y = n - r

            if clue_type == 'B':
                face_color = '#000000'
                edge_color = '#000000'
                text_color = '#FFFFFF'
            else:
                face_color = '#FFFFFF'
                edge_color = '#000000'
                text_color = '#000000'

            circle = plt.Circle((x, y), radius=0.24, facecolor=face_color, edgecolor=edge_color, linewidth=1.7, zorder=4)
            ax.add_patch(circle)
            ax.text(x, y, str(value), va='center', ha='center', fontsize=11, fontweight='bold', color=text_color, zorder=5)

    ticks = list(range(n + 1))
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])
    ax.xaxis.tick_top()

    y_ticks = [n - t for t in ticks]
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([str(t) for t in ticks])

    ax.set_xlim(-0.5, n + 0.5)
    ax.set_ylim(-0.5, n + 0.5)
    ax.set_aspect('equal')

    for spine in ax.spines.values():
        spine.set_edgecolor('#4A90E2')
        spine.set_linewidth(2)

    plt.tight_layout()
    save_square_figure(fig, output_path)
    plt.close()


def format_shingoki_to_string(grid, answer_path=None):
    clue_dict = {}
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v is not None:
                clue_dict[(r, c)] = v

    lines = [f'clues={clue_dict}']
    if answer_path is not None:
        lines.append(f'path={answer_path}')
    return '\n'.join(lines)


def construct_shingoki_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'shingoki'))
    os.makedirs(output_dir, exist_ok=True)

    grid = _normalize_grid(puzzle_dict['original_data']['data'])

    fig_name = f"shingoki_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_shingoki(grid, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"shingoki_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_shingoki(grid, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict.get('answer'))

    output_dict = {'puzzle': 'shingoki'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_shingoki_to_string(grid)
    output_dict['answer_str'] = format_shingoki_to_string(grid, answer_path=puzzle_dict.get('answer'))
    return output_dict


def test_observation(observation, gt_observation):
    """Clue grid on dots; exact match."""
    return observation == gt_observation


def test_answer(answer, gt_answer):
    """No Solution (case-insensitive); else closed loop path equal to gt after dropping repeated end, up to rotation / reversal."""

    def norm_point(p):
        if isinstance(p, (list, tuple)) and len(p) == 2:
            return (p[0], p[1])
        return None

    def norm_path(path):
        if not isinstance(path, (list, tuple)):
            return None
        out = []
        for p in path:
            q = norm_point(p)
            if q is None:
                return None
            out.append(q)
        return out

    def path_core(path):
        """first == last => drop tail duplicate; else invalid."""
        seq = norm_path(path)
        if seq is None or len(seq) < 2:
            return None
        if seq[0] != seq[-1]:
            return None
        return seq[:-1]

    def cycles_equal(core_a, core_b):
        if len(core_a) != len(core_b) or not core_a:
            return len(core_a) == len(core_b)
        n = len(core_a)
        for i in range(n):
            if core_a == core_b[i:] + core_b[:i]:
                return True
        br = [core_b[0]] + list(reversed(core_b[1:]))
        for i in range(n):
            if core_a == br[i:] + br[:i]:
                return True
        return False

    if isinstance(gt_answer, str) and gt_answer.strip().lower() == 'no solution':
        return isinstance(answer, str) and answer.strip().lower() == 'no solution'

    ca = path_core(answer)
    cg = path_core(gt_answer)
    if ca is None or cg is None:
        return False
    return cycles_equal(ca, cg)


def test_code(observation, answer, gt_observation, gt_answer):
    '''
    1. Observation
    2. No Solution
    3. Answer
    '''
    return


def get_observation(data):
    data = normalize_size_keys(data)
    return {'data': _normalize_grid(data['original_data']['data'])}


def return_data():
    ref_puzzle_dict = {
        'column/row': 5,
        'level': 'easy',
        'original_data': {
            'data': [
                ['B5', 'W3', None, None, None, None],
                [None, 'B2', 'B3', None, None, None],
                [None, None, None, 'W4', None, None],
                [None, None, None, None, None, 'W5'],
                ['W2', None, 'B2', None, None, None],
                [None, None, None, None, None, None],
            ]
        },
        'answer': [
            (0, 0), (0, 1), (0, 2), (0, 3), (1, 3), (2, 3), (3, 3), (4, 3), (4, 4),
            (3, 4), (2, 4), (1, 4), (0, 4), (0, 5), (1, 5), (2, 5), (3, 5), (4, 5), (5, 5),
            (5, 4), (5, 3), (5, 2), (4, 2), (4, 1), (5, 1), (5, 0), (4, 0), (3, 0),
            (3, 1), (3, 2), (2, 2), (1, 2), (1, 1), (2, 1), (2, 0), (1, 0), (0, 0),
        ],
        'id': 'ref',
        'rules': RULES,
    }
    ref_puzzle_dict['observation'] = get_observation(ref_puzzle_dict)

    puzzles = [dict(ref_puzzle_dict)]
    puzzles[0]['id'] = 'example_0'
    puzzles[0]['observation'] = get_observation(puzzles[0])
    return ref_puzzle_dict, puzzles


if __name__ == '__main__':
    ref_puzzle_dict, puzzles = return_data()
    ret = construct_shingoki_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_shingoki_data(puzzle)
    print(ret)
