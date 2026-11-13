import os
import sys
import matplotlib.pyplot as plt
import matplotlib.patches as patches

try:
    from construction._common import normalize_size_keys
    from construction._render import save_square_figure
except ModuleNotFoundError:
    # Allow running this file directly via `python construction/stitches.py`.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from construction._common import normalize_size_keys
    from construction._render import save_square_figure

# 1. Every pair of orthogonally adjacent cells from different regions is connected by exactly one stitch.

RULES = '''
**Core Rules:**
Place stitches so that:
1. Each pair of neighboring regions must be connected by exactly one stitch, and each stitch must connect cells from different regions.
2. A stitch connects two orthogonally adjacent holes.
3. Two stitches cannot share a hole.
4. Row and column clues give the exact number of used holes in each hole-row and hole-column.

**Coordinates & Output:**
1. Cell coordinates are integer `(row, col)` on an `N x N` grid, top-left is `(0, 0)`.
2. Hole coordinates are integer `(row, col)` on an `N x N` hole grid aligned to cell centers.
3. `row` increases downward, `col` increases rightward.
4. **Observation** has three parts:
   - `region`: `N x N` region ID grid.
   - `row_stitch_counts`: length-`N` list of row clues (top to bottom).
   - `col_stitch_counts`: length-`N` list of column clues (left to right).
5. **Answer:** list of stitches, where each stitch is `[(r1, c1), (r2, c2)]` and the two holes are orthogonally adjacent.
'''


COLOR_BG = '#F3F5F7'
COLOR_CELL = '#FDFDFD'
COLOR_GRID = '#B7BCC2'
COLOR_FRAME = '#16181B'
COLOR_REGION_BORDER = '#0F1113'
COLOR_CLUE = '#0E1012'
COLOR_STITCH = '#1B1E22'
REGION_LINE_WIDTH = 2.8


def _normalize_region_grid(region_data, n=None):
    if not isinstance(region_data, list) or not region_data or not isinstance(region_data[0], list):
        raise ValueError('region must be a non-empty 2D list.')
    grid = [row[:] for row in region_data]
    if n is not None:
        if len(grid) != n or any(len(row) != n for row in grid):
            raise ValueError('region size does not match board size.')
    return grid


def _normalize_counts(original_data):
    row_counts = original_data.get('row_stitch_counts')
    col_counts = original_data.get('col_stitch_counts')
    if row_counts is None:
        row_counts = original_data.get('L_nums')
    if col_counts is None:
        col_counts = original_data.get('U_nums')
    if row_counts is None or col_counts is None:
        raise ValueError('original_data must include row_stitch_counts and col_stitch_counts.')
    return list(row_counts), list(col_counts)


def _normalize_stitches(stitches):
    ret = []
    for seg in stitches or []:
        if not isinstance(seg, (list, tuple)) or len(seg) != 2:
            raise ValueError('each stitch must be a pair of hole coordinates.')
        p1, p2 = seg
        if not isinstance(p1, (list, tuple)) or not isinstance(p2, (list, tuple)) or len(p1) != 2 or len(p2) != 2:
            raise ValueError('hole coordinate must be (row, col).')
        r1, c1 = int(p1[0]), int(p1[1])
        r2, c2 = int(p2[0]), int(p2[1])
        ret.append(((r1, c1), (r2, c2)))
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
                linewidth=0.85,
                zorder=1,
            )
            ax.add_patch(rect)


def _draw_region_boundaries(ax, region_grid):
    n = len(region_grid)
    for i in range(n + 1):
        ax.plot([-0.5, n - 0.5], [i - 0.5, i - 0.5], color=COLOR_GRID, linewidth=0.95, zorder=2)
        ax.plot([i - 0.5, i - 0.5], [-0.5, n - 0.5], color=COLOR_GRID, linewidth=0.95, zorder=2)

    for r in range(n):
        for c in range(n):
            rid = region_grid[r][c]
            if c + 1 < n and region_grid[r][c + 1] != rid:
                x = c + 0.5
                ax.plot([x, x], [r - 0.5, r + 0.5], color=COLOR_REGION_BORDER, linewidth=REGION_LINE_WIDTH, zorder=4)
            if r + 1 < n and region_grid[r + 1][c] != rid:
                y = r + 0.5
                ax.plot([c - 0.5, c + 0.5], [y, y], color=COLOR_REGION_BORDER, linewidth=REGION_LINE_WIDTH, zorder=4)

    x0, x1 = -0.5, n - 0.5
    y0, y1 = -0.5, n - 0.5
    frame_style = dict(color=COLOR_FRAME, linewidth=REGION_LINE_WIDTH + 0.1, zorder=5, clip_on=False, solid_capstyle='butt')
    ax.plot([x0, x1], [y0, y0], **frame_style)
    ax.plot([x0, x1], [y1, y1], **frame_style)
    ax.plot([x0, x0], [y0, y1], **frame_style)
    ax.plot([x1, x1], [y0, y1], **frame_style)



def _draw_side_clues(ax, row_counts, col_counts):
    for r, val in enumerate(row_counts):
        ax.text(
            -1.07,
            r,
            str(val),
            ha='center',
            va='center',
            fontsize=22,
            fontweight='bold',
            color=COLOR_CLUE,
            zorder=10,
            clip_on=False,
        )
    for c, val in enumerate(col_counts):
        ax.text(
            c,
            -1.07,
            str(val),
            ha='center',
            va='center',
            fontsize=22,
            fontweight='bold',
            color=COLOR_CLUE,
            zorder=10,
            clip_on=False,
        )


def _draw_stitches(ax, stitches):
    for (r1, c1), (r2, c2) in stitches:
        ax.plot([c1, c2], [r1, r2], color=COLOR_STITCH, linewidth=3.1, solid_capstyle='round', zorder=8)
        for rr, cc in ((r1, c1), (r2, c2)):
            ring = patches.Circle((cc, rr), radius=0.19, facecolor='#FFFFFF', edgecolor='#000000', linewidth=2.0, zorder=9)
            ax.add_patch(ring)
            center = patches.Circle((cc, rr), radius=0.082, facecolor='#000000', edgecolor='#000000', linewidth=0.6, zorder=10)
            ax.add_patch(center)


def draw_stitches(region_grid, row_counts, col_counts, output_path, answer=None):
    n = len(region_grid)
    fig, ax = plt.subplots(figsize=(n + 1.7, n + 1.7))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    stitches = _normalize_stitches(answer) if answer is not None else []

    _draw_cells(ax, n)
    _draw_region_boundaries(ax, region_grid)
    if answer is not None:
        _draw_stitches(ax, stitches)
    _draw_side_clues(ax, row_counts, col_counts)

    ticks = list(range(n))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])
    ax.set_yticklabels([str(t) for t in ticks])
    ax.xaxis.tick_top()
    ax.tick_params(axis='x', pad=2, length=0)
    ax.tick_params(axis='y', pad=2, length=0)

    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(-0.5, n - 0.5)
    ax.invert_yaxis()
    ax.set_aspect('equal')

    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout()
    save_square_figure(fig, output_path)
    plt.close()


def format_stitches_to_string(region_grid, row_counts, col_counts, answer=None):
    lines = [
        f'region={region_grid}',
        f'row_stitch_counts={row_counts}',
        f'col_stitch_counts={col_counts}',
    ]
    if answer is not None:
        lines.append(f'stitches={_normalize_stitches(answer)}')
    return '\n'.join(lines)


def construct_stitches_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'stitches'))
    os.makedirs(output_dir, exist_ok=True)

    n = puzzle_dict['column/row']
    original = puzzle_dict['original_data']
    region_grid = _normalize_region_grid(original['region'], n=n)
    row_counts, col_counts = _normalize_counts(original)

    fig_name = f"stitches_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_stitches(region_grid, row_counts, col_counts, output_path=os.path.join(output_dir, f'{fig_name}.png'))

    answer_fig_name = f"stitches_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_stitches(
        region_grid,
        row_counts,
        col_counts,
        output_path=os.path.join(output_dir, f'{answer_fig_name}.png'),
        answer=puzzle_dict.get('answer'),
    )

    output_dict = {'puzzle': 'stitches'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name
    output_dict['initial_str'] = format_stitches_to_string(region_grid, row_counts, col_counts)
    output_dict['answer_str'] = format_stitches_to_string(region_grid, row_counts, col_counts, answer=puzzle_dict.get('answer'))
    return output_dict


def test_observation(observation, gt_observation):
    """`region` with ID permutation normalization; `row_stitch_counts` / `col_stitch_counts` exact ==."""

    def _normalize_region_ids(region):
        if not isinstance(region, list) or not region:
            return None
        n = len(region)
        regions = {}
        for r in range(n):
            if not isinstance(region[r], list) or len(region[r]) != n:
                return None
            for c in range(n):
                rid = region[r][c]
                regions.setdefault(rid, []).append((r, c))
        sorted_items = sorted(
            regions.items(),
            key=lambda x: (len(x[1]), tuple(sorted(x[1]))),
        )
        rid_to_new = {old_rid: i for i, (old_rid, _) in enumerate(sorted_items)}
        return [[rid_to_new[region[r][c]] for c in range(n)] for r in range(n)]

    if not isinstance(observation, dict) or not isinstance(gt_observation, dict):
        return False
    ro, rg = observation['region'], gt_observation['region']
    no, ng = _normalize_region_ids(ro), _normalize_region_ids(rg)
    if no is None or ng is None:
        if ro != rg:
            return False
    elif no != ng:
        return False
    if observation.get('row_stitch_counts') != gt_observation.get('row_stitch_counts'):
        return False
    if observation.get('col_stitch_counts') != gt_observation.get('col_stitch_counts'):
        return False
    return True


def test_answer(answer, gt_answer):
    """No Solution (case-insensitive); else each stitch as undirected hole-pair (min (r,c) first), then sorted list ==."""

    def hole(p):
        if isinstance(p, (list, tuple)) and len(p) == 2:
            return (int(p[0]), int(p[1]))
        return None

    def norm_stitch(seg):
        if not isinstance(seg, (list, tuple)) or len(seg) != 2:
            return None
        a, b = hole(seg[0]), hole(seg[1])
        if a is None or b is None:
            return None
        return (a, b) if a <= b else (b, a)

    def norm_stitch_sequence(stitches):
        if not isinstance(stitches, (list, tuple)):
            return None
        out = []
        for seg in stitches:
            e = norm_stitch(seg)
            if e is None:
                return None
            out.append(e)
        return sorted(out)

    if isinstance(gt_answer, str) and gt_answer.strip().lower() == 'no solution':
        return isinstance(answer, str) and answer.strip().lower() == 'no solution'

    na = norm_stitch_sequence(answer)
    ng = norm_stitch_sequence(gt_answer)
    if na is None or ng is None:
        return False
    return na == ng


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
    original = data['original_data']
    region_grid = _normalize_region_grid(original['region'], n=n)
    row_counts, col_counts = _normalize_counts(original)
    return {
        'region': region_grid,
        'row_stitch_counts': row_counts,
        'col_stitch_counts': col_counts,
    }


def return_data():
    ref_puzzle_dict = {
        'column/row': 5,
        'level': 'easy',
        'original_data': {
            'region': [
                [0, 1, 1, 1, 2],
                [0, 1, 2, 2, 2],
                [1, 1, 1, 2, 3],
                [1, 1, 1, 4, 3],
                [1, 1, 1, 4, 4],
            ],
            'row_stitch_counts': [0, 4, 3, 2, 3],
            'col_stitch_counts': [1, 1, 3, 3, 4],
        },
        'answer': [
            [(1, 0), (1, 1)],
            [(1, 2), (2, 2)],
            [(1, 4), (2, 4)],
            [(2, 3), (3, 3)],
            [(3, 4), (4, 4)],
            [(4, 2), (4, 3)],
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
    ret = construct_stitches_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_stitches_data(puzzle)
    print(ret)
