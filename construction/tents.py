import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from construction._common import normalize_size_keys
from construction._render import save_square_figure


RULES = '''
**Core Rules:**
Place tents on empty cells so that:
1. Each tent is orthogonally adjacent to exactly one tree.
2. Each tree is paired with exactly one tent (1-to-1 pairing).
3. Tents cannot touch each other, including diagonally.
4. Row and column clues indicate exactly how many tents must be placed in that row/column.

**Coordinates & Output:**
1. Coordinates use `(row, col)` with top-left as `(0, 0)`.
2. `row` increases top-to-bottom, `col` increases left-to-right.
3. **Observation** has three parts:
   - `tree`: list of lists using `'T'` for tree cells, else `None`.
   - `row_tent_counts`: list from top row to bottom row.
   - `col_tent_counts`: list from left column to right column.
4. **Answer:** same-sized grid using `'t'` for tent cells and `None` for non-tent cells.
'''


COLOR_BG = '#FFFFFF'
COLOR_CELL = '#FFFFFF'
COLOR_GRID = '#4F4F4F'
COLOR_FRAME = '#000000'
COLOR_TREE = '#8EE28E'
COLOR_TREE_CROWN = '#18C718'
COLOR_TREE_TRUNK = '#7A4A1E'
COLOR_TENT = '#F0F0F0'
COLOR_TENT_EDGE = '#111111'
COLOR_CLUE = '#000000'


def _normalize_counts(original_data):
    # preferred names
    row_counts = original_data.get('row_tent_counts')
    col_counts = original_data.get('col_tent_counts')

    # backward-compat names
    if row_counts is None:
        row_counts = original_data.get('L_nums')
    if col_counts is None:
        col_counts = original_data.get('U_nums')

    if row_counts is None or col_counts is None:
        raise ValueError("original_data must include row/col tent counts.")

    return list(row_counts), list(col_counts)


def _draw_grid(ax, n):
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

    frame = patches.Rectangle((-0.5, -0.5), n, n, fill=False, edgecolor=COLOR_FRAME, linewidth=2.8, zorder=4)
    ax.add_patch(frame)


def _draw_trees(ax, tree_grid):
    n = len(tree_grid)
    for r in range(n):
        for c in range(n):
            if tree_grid[r][c] == 'T':
                # green background tile for tree cells
                bg = patches.Rectangle((c - 0.5, r - 0.5), 1, 1, facecolor=COLOR_TREE, edgecolor=COLOR_GRID, linewidth=1.1, zorder=2)
                ax.add_patch(bg)

                crown = patches.Circle((c, r - 0.06), radius=0.26, facecolor=COLOR_TREE_CROWN, edgecolor='#0D0D0D', linewidth=1.5, zorder=3)
                ax.add_patch(crown)
                trunk = patches.Rectangle((c - 0.07, r + 0.14), 0.14, 0.22, facecolor=COLOR_TREE_TRUNK, edgecolor='#3A220D', linewidth=1.0, zorder=3)
                ax.add_patch(trunk)


def _draw_tents(ax, answer_grid):
    n = len(answer_grid)
    for r in range(n):
        for c in range(n):
            if answer_grid[r][c] == 't':
                tent = patches.Polygon(
                    [(c - 0.20, r + 0.23), (c, r - 0.23), (c + 0.20, r + 0.23)],
                    closed=True,
                    facecolor=COLOR_TENT,
                    edgecolor=COLOR_TENT_EDGE,
                    linewidth=2.0,
                    zorder=5,
                )
                ax.add_patch(tent)
                pole = patches.Rectangle((c - 0.015, r - 0.03), 0.03, 0.20, facecolor=COLOR_TENT_EDGE, edgecolor=COLOR_TENT_EDGE, linewidth=0, zorder=6)
                ax.add_patch(pole)


def _draw_side_clues(ax, row_counts, col_counts):
    n = len(row_counts)
    for r, val in enumerate(row_counts):
        ax.text(
            -1.08,
            r,
            str(val),
            ha='center',
            va='center',
            fontsize=26,
            fontweight='bold',
            color=COLOR_CLUE,
            zorder=8,
            clip_on=False,
        )

    for c, val in enumerate(col_counts):
        ax.text(
            c,
            -1.08,
            str(val),
            ha='center',
            va='center',
            fontsize=26,
            fontweight='bold',
            color=COLOR_CLUE,
            zorder=8,
            clip_on=False,
        )


def draw_tents(tree_grid, row_counts, col_counts, output_path, answer=None):
    n = len(tree_grid)
    fig, ax = plt.subplots(figsize=(n + 1.8, n + 1.8))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    _draw_grid(ax, n)
    _draw_trees(ax, tree_grid)
    if answer is not None:
        _draw_tents(ax, answer)
    _draw_side_clues(ax, row_counts, col_counts)

    ticks = list(range(n))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])
    ax.set_yticklabels([str(t) for t in ticks])
    ax.xaxis.tick_top()
    # Keep native ticks/labels and make board-to-tick spacing match lightup.
    ax.tick_params(axis='x', pad=2)
    ax.tick_params(axis='y', pad=2)

    # Same board coordinate window as lightup, so ticks sit tight to the board.
    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(-0.5, n - 0.5)
    ax.invert_yaxis()
    ax.set_aspect('equal')

    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout()
    save_square_figure(fig, output_path)
    plt.close()


def format_tents_to_string(tree_grid, row_counts, col_counts, answer=None):
    lines = [
        f"row_tent_counts={row_counts}",
        f"col_tent_counts={col_counts}",
    ]
    n = len(tree_grid)
    for r in range(n):
        row_tokens = []
        for c in range(n):
            if tree_grid[r][c] == 'T':
                row_tokens.append('T')
            elif answer is not None and answer[r][c] == 't':
                row_tokens.append('t')
            else:
                row_tokens.append('.')
        lines.append(' '.join(row_tokens))
    return '\n'.join(lines)


def construct_tents_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'tents'))
    os.makedirs(output_dir, exist_ok=True)

    original = puzzle_dict['original_data']
    tree_grid = original['tree']
    row_counts, col_counts = _normalize_counts(original)

    fig_name = f"tents_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_tents(tree_grid, row_counts, col_counts, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"tents_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_tents(tree_grid, row_counts, col_counts, output_path=os.path.join(output_dir, f'{answer_fig_name}.png'), answer=puzzle_dict['answer'])

    output_dict = {'puzzle': 'tents'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_tents_to_string(tree_grid, row_counts, col_counts)
    output_dict['answer_str'] = format_tents_to_string(tree_grid, row_counts, col_counts, answer=puzzle_dict['answer'])

    return output_dict


def test_observation(observation, gt_observation):
    """Trees and row/column tent counts; exact match."""
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
    original = data['original_data']
    row_counts, col_counts = _normalize_counts(original)
    return {
        'tree': [row[:] for row in original['tree']],
        'row_tent_counts': row_counts,
        'col_tent_counts': col_counts,
    }


def return_data():
    ref_puzzle_dict = {
        'column/row': 6,
        'level': 'easy',
        'original_data': {
            'tree': [
                [None, None, 'T', None, None, 'T'],
                [None, None, None, None, None, None],
                ['T', 'T', None, None, None, None],
                [None, 'T', None, None, None, None],
                [None, None, None, None, 'T', None],
                [None, None, 'T', None, None, None],
            ],
            'row_tent_counts': [1, 2, 0, 3, 0, 1],
            'col_tent_counts': [1, 2, 1, 1, 1, 1],
        },
        'answer': [
            [None, None, None, 't', None, None],
            [None, 't', None, None, None, 't'],
            [None, None, None, None, None, None],
            ['t', None, 't', None, 't', None],
            [None, None, None, None, None, None],
            [None, 't', None, None, None, None],
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
                'tree': [
                    [None, None, 'T', 'T', None, 'T'],
                    [None, None, None, None, None, None],
                    [None, None, None, None, None, None],
                    ['T', None, None, None, None, None],
                    ['T', None, None, None, None, None],
                    [None, 'T', None, None, 'T', None],
                ],
                'row_tent_counts': [1, 2, 1, 0, 0, 3],
                'col_tent_counts': [2, 1, 1, 1, 0, 2],
            },
            'answer': [
                [None, 't', None, None, None, None],
                [None, None, None, 't', None, 't'],
                ['t', None, None, None, None, None],
                [None, None, None, None, None, None],
                [None, None, None, None, None, None],
                ['t', None, 't', None, None, 't'],
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
    ret = construct_tents_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_tents_data(puzzle)
    print(ret)
