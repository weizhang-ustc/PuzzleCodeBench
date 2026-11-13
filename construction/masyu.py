import os
import sys
import matplotlib.pyplot as plt

try:
    from construction._common import normalize_size_keys
    from construction._render import save_square_figure
except ModuleNotFoundError:
    # Allow running this file directly via `python construction/masyu.py`.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from construction._common import normalize_size_keys
    from construction._render import save_square_figure


RULES = '''
**Core Rules:**
Draw lines between dots to form a single closed loop without crossings or branches.
The loop must pass through all clue circles, where:
1. `W` (white circle): the loop goes straight through this circle, and it must turn at least once in the previous or next step.
2. `B` (black circle): the loop turns at this circle, and goes straight in both the previous and next steps.

**Coordinates & Output:**
1. Dot coordinates are integer `(row, col)` on an `N x N` dot grid.
2. Top-left is `(0, 0)`; `row` increases downward, `col` increases rightward.
3. **Observation** has one part:
   - `data`: `N x N` 2D list; each entry is `None`, `'W'`, or `'B'`.
4. **Answer:** an ordered closed loop path as a list of dot coordinates, e.g.
   `[(0,0), (0,1), (1,1), ..., (0,0)]`.
'''


def _normalize_grid(data):
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError('masyu data must be a 2D list.')
    n_rows = len(data)
    if any(len(row) != n_rows for row in data):
        raise ValueError('masyu data must be square (dot grid).')
    return [row[:] for row in data]


def _parse_clue(token):
    if token is None:
        return None
    if not isinstance(token, str):
        return None

    s = token.strip()
    if not s:
        return None

    clue_type = s[0].upper()
    if clue_type not in ('B', 'W'):
        return None

    # Optional numeric suffix support (for variants), default None for classic masyu.
    label = s[1:] if len(s) > 1 else None
    return clue_type, label


def draw_masyu(grid, output_path, answer=None):
    grid = _normalize_grid(grid)
    n = len(grid)

    fig, ax = plt.subplots(figsize=(n + 0.9, n + 0.9))
    ax.set_facecolor('#EFEFEF')

    # Draw all possible dot-to-dot segments as light grid lines.
    for r in range(n):
        y = (n - 1) - r
        ax.plot([0, n - 1], [y, y], color='#D6D6D6', linewidth=1.6, zorder=1)
    for c in range(n):
        ax.plot([c, c], [0, n - 1], color='#D6D6D6', linewidth=1.6, zorder=1)

    # Draw loop path.
    if answer:
        path_x = [pt[1] for pt in answer]
        path_y = [(n - 1) - pt[0] for pt in answer]
        ax.plot(path_x, path_y, color='#111111', linewidth=4.2, solid_capstyle='round', zorder=2)

    # Draw lattice dots.
    for r in range(n):
        for c in range(n):
            ax.plot(c, (n - 1) - r, 'ko', markersize=4.0, zorder=3)

    # Draw clue circles on dot coordinates.
    for r in range(n):
        for c in range(n):
            parsed = _parse_clue(grid[r][c])
            if parsed is None:
                continue
            clue_type, label = parsed
            x = c
            y = (n - 1) - r

            if clue_type == 'B':
                face_color = '#000000'
                edge_color = '#000000'
                text_color = '#FFFFFF'
            else:
                face_color = '#FFFFFF'
                edge_color = '#000000'
                text_color = '#000000'

            circle = plt.Circle((x, y), radius=0.215, facecolor=face_color, edgecolor=edge_color, linewidth=1.6, zorder=4)
            ax.add_patch(circle)
            if label:
                ax.text(x, y, label, va='center', ha='center', fontsize=10, fontweight='bold', color=text_color, zorder=5)

    ticks = list(range(n))
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])
    ax.xaxis.tick_top()

    y_ticks = [(n - 1) - t for t in ticks]
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([str(t) for t in ticks])

    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(-0.5, n - 0.5)
    ax.set_aspect('equal')

    for spine in ax.spines.values():
        spine.set_edgecolor('#4A90E2')
        spine.set_linewidth(2)

    plt.tight_layout()
    save_square_figure(fig, output_path)
    plt.close()


def format_masyu_to_string(grid, answer_path=None):
    clue_dict = {}
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v is not None:
                clue_dict[(r, c)] = v

    lines = [f'clues={clue_dict}']
    if answer_path is not None:
        lines.append(f'path={answer_path}')
    return '\n'.join(lines)


def construct_masyu_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'masyu'))
    os.makedirs(output_dir, exist_ok=True)

    grid = _normalize_grid(puzzle_dict['original_data']['data'])

    fig_name = f"masyu_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_masyu(grid, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"masyu_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_masyu(grid, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict.get('answer'))

    output_dict = {'puzzle': 'masyu'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_masyu_to_string(grid)
    output_dict['answer_str'] = format_masyu_to_string(grid, answer_path=puzzle_dict.get('answer'))
    return output_dict


def test_observation(observation, gt_observation):
    """Observation is fixed grid of clues; exact match."""
    return observation == gt_observation


def test_answer(answer, gt_answer):
    """No Solution (case-insensitive); else closed path equal to gt up to rotation / reversal."""

    def norm_point(p):
        if isinstance(p, (list, tuple)) and len(p) == 2:
            return (p[0], p[1])
        return None

    def norm_path(path):
        if not isinstance(path, list):
            return None
        out = []
        for p in path:
            q = norm_point(p)
            if q is None:
                return None
            out.append(q)
        return out

    def path_core(path):
        """Closed loop lists repeat start at end; return vertices once, or None if not closed / invalid."""
        seq = norm_path(path)
        if seq is None or len(seq) < 2:
            return None
        if seq[0] != seq[-1]:
            return None
        return seq[:-1]

    def cycles_equal(core_a, core_b):
        """True if same closed loop up to starting point and traversal direction."""
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
        'column/row': 6,
        'level': 'easy',
        'original_data': {
            'data': [
                ['B', 'W', None, None, 'W', None],
                [None, None, None, 'W', None, None],
                [None, 'W', None, None, 'W', None],
                [None, 'W', 'W', None, 'W', None],
                [None, 'W', None, None, None, 'W'],
                [None, None, None, 'W', 'W', 'B'],
            ]
        },
        'answer': [
            (0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5),
            (1, 5), (2, 5), (3, 5), (4, 5), (5, 5), (5, 4),
            (5, 3), (5, 2), (4, 2), (4, 1), (4, 0), (3, 0),
            (3, 1), (3, 2), (3, 3), (4, 3), (4, 4), (3, 4),
            (2, 4), (1, 4), (1, 3), (1, 2), (2, 2), (2, 1),
            (2, 0), (1, 0), (0, 0)
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
    ret = construct_masyu_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_masyu_data(puzzle)
    print(ret)
