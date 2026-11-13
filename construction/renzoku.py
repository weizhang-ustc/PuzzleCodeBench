import os
import matplotlib.pyplot as plt
from construction._common import normalize_size_keys
from construction._render import save_square_figure



RULES = '''
**Core Rules:**
Fill the grid with numbers so that:
1. Numbers are from `1` to grid size `N`.
2. Each row and each column contains each number exactly once.
3. A dot between two orthogonally adjacent cells means their values are consecutive.
4. If no dot is between two orthogonally adjacent cells, their values are not consecutive.

**Coordinates & Output:**
1. Cell centers are integer coordinates `(row, col)` with top-left `(0, 0)`.
2. Between-cell coordinates use `.5`:
   - Horizontal gap: `(row, col+0.5)`
   - Vertical gap: `(row+0.5, col)`
3. **Observation** has two parts:
   - `data`: clue grid as list of lists with numbers or `None`.
   - `adjacent`: list of midpoint coordinates where a dot exists.
4. **Answer:** full solved number grid as list of lists.
'''


def _normalize_adjacent_positions(adjacent_list):
    return [(float(r), float(c)) for r, c in (adjacent_list or [])]


def _adjacent_set(adjacent_list):
    return set(_normalize_adjacent_positions(adjacent_list))


def draw_renzoku(grid, adjacent=None, output_path=None, answer=None):
    n = len(grid)
    adjacent_set = _adjacent_set(adjacent)

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

            v = grid[r][c]
            if v is not None:
                ax.text(c, r, str(v), va='center', ha='center', fontsize=18, fontweight='bold', color='black')
            elif answer is not None and answer[r][c] is not None:
                ax.text(c, r, str(answer[r][c]), va='center', ha='center', fontsize=18, color='#1A73B8', fontweight='bold')

    # Draw thicker dots on midpoint coordinates.
    for r, c in adjacent_set:
        dot = plt.Circle((c, r), radius=0.055, facecolor='black', edgecolor='black', linewidth=0, zorder=6)
        ax.add_patch(dot)

    for spine in ax.spines.values():
        spine.set_edgecolor('#4A90E2')
        spine.set_linewidth(2)

    ax.set_aspect('equal')
    plt.tight_layout()
    if output_path:
        save_square_figure(fig, output_path)
    plt.close()


def format_renzoku_to_string(grid, adjacent=None, answer=None):
    adjacent_set = _adjacent_set(adjacent)
    n = len(grid)
    shown = []
    for r in range(n):
        row = []
        for c in range(n):
            if grid[r][c] is not None:
                row.append(grid[r][c])
            elif answer is not None:
                row.append(answer[r][c])
            else:
                row.append('.')
        shown.append(row)

    lines = [f"adjacent={sorted(adjacent_set)}"]
    for r in range(n):
        row_parts = []
        for c in range(n):
            row_parts.append(str(shown[r][c]))
            if c < n - 1:
                row_parts.append('•' if (float(r), c + 0.5) in adjacent_set else ' ')
        lines.append(' '.join(row_parts))
        if r < n - 1:
            mid = []
            for c in range(n):
                mid.append('•' if (r + 0.5, float(c)) in adjacent_set else ' ')
                if c < n - 1:
                    mid.append(' ')
            lines.append(' '.join(mid))
    return '\n'.join(lines)


def construct_renzoku_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'renzoku'))
    os.makedirs(output_dir, exist_ok=True)

    grid = puzzle_dict['original_data']['data']
    adjacent = puzzle_dict['original_data'].get('adjacent', [])

    fig_name = f"renzoku_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_renzoku(grid, adjacent=adjacent, output_path=os.path.join(output_dir, f"{fig_name}.png"))

    answer_fig_name = f"renzoku_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_renzoku(grid, adjacent=adjacent, output_path=os.path.join(output_dir, f"{answer_fig_name}.png"), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'renzoku'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_renzoku_to_string(grid, adjacent=adjacent)
    output_dict['answer_str'] = format_renzoku_to_string(grid, adjacent=adjacent, answer=puzzle_dict['answer'])
    return output_dict


def _is_consecutive(a, b):
    return abs(a - b) == 1


def test_observation(observation, gt_observation):
    """Only `data` + `adjacent`: `data` ==; `adjacent` parsed like futoshiki coords then sorted list ==."""

    def norm_adj(adj):
        if adj is None:
            return []
        if not isinstance(adj, (list, tuple)):
            return None
        pts = []
        for p in adj:
            if isinstance(p, (tuple, list)) and len(p) == 2:
                pts.append((float(p[0]), float(p[1])))
            elif isinstance(p, str):
                parts = p.replace('(', '').replace(')', '').split(',')
                if len(parts) == 2:
                    pts.append((float(parts[0].strip()), float(parts[1].strip())))
        return sorted(pts)

    if not isinstance(observation, dict) or not isinstance(gt_observation, dict):
        return False
    if observation.get('data') != gt_observation.get('data'):
        return False
    a, b = norm_adj(observation.get('adjacent')), norm_adj(gt_observation.get('adjacent'))
    if a is None or b is None:
        return False
    return a == b


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

    data = observation.get('data')
    adjacent = observation.get('adjacent', [])
    if data is None:
        return False

    n = len(data)
    if len(answer) != n:
        return False
    for row in answer:
        if len(row) != n:
            return False

    valid_vals = set(range(1, n + 1))

    # Given cells fixed + domain check
    for r in range(n):
        for c in range(n):
            v = answer[r][c]
            if v not in valid_vals:
                return False
            if data[r][c] is not None and v != data[r][c]:
                return False

    # Latin constraints
    for r in range(n):
        if set(answer[r]) != valid_vals:
            return False
    for c in range(n):
        if set(answer[r][c] for r in range(n)) != valid_vals:
            return False

    adjacent_set = _adjacent_set(adjacent)
    # Adjacency constraints: with dot => consecutive, without dot => not consecutive.
    for r in range(n):
        for c in range(n - 1):
            pos = (float(r), c + 0.5)
            cons = _is_consecutive(answer[r][c], answer[r][c + 1])
            if (pos in adjacent_set) != cons:
                return False
    for r in range(n - 1):
        for c in range(n):
            pos = (r + 0.5, float(c))
            cons = _is_consecutive(answer[r][c], answer[r + 1][c])
            if (pos in adjacent_set) != cons:
                return False

    if gt_answer is None:
        return True
    return answer == gt_answer


def get_observation(data):
    data = normalize_size_keys(data)
    return {
        'data': [row[:] for row in data['original_data']['data']],
        'adjacent': _normalize_adjacent_positions(data['original_data'].get('adjacent', [])),
    }


def return_data():
    ref_puzzle_dict = {
        'column/row': 4,
        'level': 'easy',
        'original_data': {
            'data': [
                [None, None, 1, None],
                [None, None, None, 1],
                [None, None, None, None],
                [None, None, None, None],
            ],
            'adjacent': [
                (0, 0.5), (0, 1.5),
                (1, 0.5), (1, 1.5),
                (2, 2.5),
                (3, 2.5),
                (0.5, 0), (0.5, 1),
                (1.5, 0), (1.5, 1),
                (2.5, 2), (2.5, 3),
            ]
        },
        'answer': [
            [3, 2, 1, 4],
            [2, 3, 4, 1],
            [1, 4, 2, 3],
            [4, 1, 3, 2],
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
                    [None, None, None, None],
                    [None, None, None, None],
                    [None, None, None, None],
                    [None, 1, None, None],
                ],
                'adjacent': [
                    (0, 0.5), (0, 1.5),
                    (1, 1.5),
                    (2, 1.5),
                    (3, 1.5), (3, 2.5),
                    (0.5, 0),
                    (1.5, 0), (1.5, 1), (1.5, 2), (1.5, 3),
                    (2.5, 3),
                ]
            },
            'answer': [
                [3, 2, 1, 4],
                [2, 4, 3, 1],
                [1, 3, 4, 2],
                [4, 1, 2, 3],
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
    ret = construct_renzoku_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_renzoku_data(puzzle)
    print(ret)
