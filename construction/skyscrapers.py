import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# Fill the `N x N` grid with building heights `1..N` so that:
# 1. Each row contains each height exactly once.
# 2. Each column contains each height exactly once.
# 3. Side clues indicate how many buildings are visible from that direction.
#    A taller building hides all shorter buildings behind it.
# 
# **Coordinates & Output:**
# 1. Cell coordinates use `(row, col)` with top-left as `(0, 0)`.
# 2. `row` increases top-to-bottom, `col` increases left-to-right.
# 3. Side clue order is fixed:
#    - `U` (top): left to right
#    - `D` (bottom): left to right
#    - `L` (left): top to bottom
#    - `R` (right): top to bottom
# 4. **Observation:**
#    `{'U': [...], 'D': [...], 'L': [...], 'R': [...]}`
# 5. **Answer:** full solved `N x N` grid of integers.
# '''

RULES = '''
**Core Rules:**
Fill the `N x N` grid with building heights `1..N` so that:
1. Each row contains each height exactly once.
2. Each column contains each height exactly once.
3. Side clues indicate how many buildings are visible from that direction.
   A taller building hides all shorter buildings behind it.

**Coordinates & Output:**
1. Cell coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. Side clue order is fixed:
   - `U` (top): left to right
   - `D` (bottom): left to right
   - `L` (left): top to bottom
   - `R` (right): top to bottom
4. **Observation** has four parts:
   - `U`: top clues list (`int` or `None`)
   - `D`: bottom clues list (`int` or `None`)
   - `L`: left clues list (`int` or `None`)
   - `R`: right clues list (`int` or `None`)
5. **Answer:** full solved `N x N` 2D list (list of lists) of integers.
'''


COLOR_BG = '#E9E9E9'
COLOR_CELL = '#EFEFEF'
COLOR_GRID = '#222222'
COLOR_FRAME = '#000000'
COLOR_CLUE_FACE = '#D0D0D0'
COLOR_CLUE_EDGE = '#222222'
COLOR_CLUE_TEXT = '#000000'
COLOR_ANSWER_TEXT = '#1E73BE'


def _draw_grid(ax, n):
    for r in range(n):
        for c in range(n):
            rect = patches.Rectangle(
                (c - 0.5, r - 0.5),
                1,
                1,
                facecolor=COLOR_CELL,
                edgecolor=COLOR_GRID,
                linewidth=1.4,
                zorder=1,
            )
            ax.add_patch(rect)

    # obvious outer border
    frame = patches.Rectangle(
        (-0.5, -0.5),
        n,
        n,
        fill=False,
        edgecolor=COLOR_FRAME,
        linewidth=3.6,
        zorder=3,
    )
    ax.add_patch(frame)


def _draw_clue_tag(ax, direction, idx, value, n):
    """Draw clue tags similar to the reference style around the grid."""
    if value is None:
        return

    # tag size around 0.65x0.65
    w = 0.62
    h = 0.62

    if direction == 'U':
        cx, cy = idx, -1.15
        poly = [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h * 0.18), (cx, cy + h / 2), (cx - w / 2, cy + h * 0.18)]
    elif direction == 'D':
        cx, cy = idx, n + 0.15
        poly = [(cx - w / 2, cy + h / 2), (cx + w / 2, cy + h / 2), (cx + w / 2, cy - h * 0.18), (cx, cy - h / 2), (cx - w / 2, cy - h * 0.18)]
    elif direction == 'L':
        cx, cy = -1.15, idx
        poly = [(cx - w / 2, cy - h / 2), (cx + w * 0.18, cy - h / 2), (cx + w / 2, cy), (cx + w * 0.18, cy + h / 2), (cx - w / 2, cy + h / 2)]
    else:  # 'R'
        cx, cy = n + 0.15, idx
        poly = [(cx + w / 2, cy - h / 2), (cx - w * 0.18, cy - h / 2), (cx - w / 2, cy), (cx - w * 0.18, cy + h / 2), (cx + w / 2, cy + h / 2)]

    tag = patches.Polygon(poly, closed=True, facecolor=COLOR_CLUE_FACE, edgecolor=COLOR_CLUE_EDGE, linewidth=1.4, zorder=4)
    ax.add_patch(tag)
    ax.text(cx, cy - 0.02, str(value), ha='center', va='center', fontsize=20, fontweight='bold', color=COLOR_CLUE_TEXT, zorder=5)


def _draw_clues(ax, clues, n):
    for i, v in enumerate(clues.get('U', [])):
        _draw_clue_tag(ax, 'U', i, v, n)
    for i, v in enumerate(clues.get('D', [])):
        _draw_clue_tag(ax, 'D', i, v, n)
    for i, v in enumerate(clues.get('L', [])):
        _draw_clue_tag(ax, 'L', i, v, n)
    for i, v in enumerate(clues.get('R', [])):
        _draw_clue_tag(ax, 'R', i, v, n)


def _draw_answer(ax, answer):
    n = len(answer)
    for r in range(n):
        for c in range(n):
            ax.text(
                c,
                r,
                str(answer[r][c]),
                ha='center',
                va='center',
                fontsize=31,
                fontweight='bold',
                color=COLOR_ANSWER_TEXT,
                zorder=2,
            )


def draw_skyscrapers(clues, output_path, answer=None):
    n = len(clues['U'])
    fig, ax = plt.subplots(figsize=(n + 2.2, n + 2.2))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_grid(ax, n)
    if answer is not None:
        _draw_answer(ax, answer)
    _draw_clues(ax, clues, n)

    ticks = list(range(n))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])
    ax.set_yticklabels([str(t) for t in ticks])
    ax.xaxis.tick_top()

    ax.set_xlim(-1.6, n + 0.6)
    ax.set_ylim(-1.6, n + 0.6)
    ax.invert_yaxis()
    ax.set_aspect('equal')

    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout()
    save_square_figure(fig, output_path)
    plt.close()


def format_skyscrapers_to_string(clues, answer=None):
    lines = [
        f"U={clues.get('U', [])}",
        f"D={clues.get('D', [])}",
        f"L={clues.get('L', [])}",
        f"R={clues.get('R', [])}",
    ]
    if answer is None:
        lines.append('answer=.')
    else:
        for row in answer:
            lines.append(' '.join(str(v) for v in row))
    return '\n'.join(lines)


def construct_skyscrapers_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'skyscrapers'))
    os.makedirs(output_dir, exist_ok=True)

    clues = puzzle_dict['original_data']

    fig_name = f"skyscrapers_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_skyscrapers(clues, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"skyscrapers_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_skyscrapers(clues, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'skyscrapers'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_skyscrapers_to_string(clues)
    output_dict['answer_str'] = format_skyscrapers_to_string(clues, answer=puzzle_dict['answer'])

    return output_dict


def test_observation(observation, gt_observation):
    """Edge clues U/D/L/R; exact match."""
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
    clues = data['original_data']
    return {
        'U': list(clues.get('U', [])),
        'D': list(clues.get('D', [])),
        'L': list(clues.get('L', [])),
        'R': list(clues.get('R', [])),
    }


def return_data():
    ref_puzzle_dict = {
        'column/row': 4,
        'level': 'easy',
        'original_data': {
            'L': [1, 2, 2, 3],
            'U': [1, 3, 2, 2],
            'R': [2, 2, 3, 1],
            'D': [3, 2, 3, 1],
        },
        'answer': [
            [4, 1, 2, 3],
            [3, 2, 4, 1],
            [1, 4, 3, 2],
            [2, 3, 1, 4],
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
                'L': [2, 1, 3, 3, 2],
                'U': [2, 3, 3, 1, 4],
                'R': [2, 3, 2, 1, 4],
                'D': [2, 1, 2, 4, 2],
            },
            'answer': [
                [4, 3, 1, 5, 2],
                [5, 1, 2, 4, 3],
                [1, 2, 5, 3, 4],
                [2, 4, 3, 1, 5],
                [3, 5, 4, 2, 1],
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
    ret = construct_skyscrapers_data(ref_puzzle_dict)
    ret = construct_skyscrapers_data(puzzles[0])
    print(ret)
