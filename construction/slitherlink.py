import os
import matplotlib.pyplot as plt
from construction._common import normalize_size_keys
from construction._render import save_square_figure


# RULES = '''
# **Core Rules:**
# You have to draw lines between the dots to form a single loop without crossings or branches. The numbers indicate how many lines surround it.
# 
# **Coordinates & Output:**
# 1. **Grid System:**
#    - Dots are at integer coordinates `(row, col)`.
#    - Numbers are at half-integer centers `(row+0.5, col+0.5)`.
#    - Top-left is `(0, 0)`; `row` increases downwards, `col` increases rightwards.
# 
# 2. **Required Format:**
#    - **Observation:** A dictionary of the initial numbers.
#      Example: `{(0.5, 0.5): 3, (0.5, 1.5): 2, ...}`
#    - **Answer:** A list of coordinates representing the loop path in order.
#      Example: `[(0, 0), (0, 1), (1, 1), ..., (0, 0)]`
# '''

RULES = '''
**Core Rules:**
Draw lines between dots to form a single closed loop without crossings or branches.
Each clue number indicates how many loop edges surround that cell.

**Coordinates & Output:**
1. Dot coordinates are integer `(row, col)`.
2. Clue coordinates are half-integer cell centers `(row+0.5, col+0.5)`.
3. Top-left is `(0, 0)`; `row` increases downward, `col` increases rightward.
4. **Observation** has one part:
   - `data`: `N x N` clue 2D list (`int` or `None`).
5. **Answer:** ordered list of loop-dot coordinates, e.g. `[(0,0), (0,1), ..., (0,0)]`.
'''


def draw_slitherlink(grid, output_path, answer=None):
    rows = len(grid)
    cols = len(grid[0])
    
    fig, ax = plt.subplots(figsize=(cols + 1, rows + 1))
    
    for r in range(rows + 1):
        for c in range(cols + 1):
            ax.plot(c, rows - r, 'ko', markersize=8, zorder=4)

    for r in range(rows):
        for c in range(cols):
            val = grid[r][c]
            if val is not None:
                ax.text(c + 0.5, rows - r - 0.5, str(val), 
                        va='center', ha='center', 
                        fontsize=20, fontweight='bold', zorder=2)

    if answer:
        path_x = [pt[1] for pt in answer]
        path_y = [rows - pt[0] for pt in answer]
        
        # path_x.append(path_x[0])
        # path_y.append(path_y[0])
        
        ax.plot(path_x, path_y, color='#1A237E', linewidth=5, 
                solid_capstyle='round', alpha=0.8, zorder=3)

    # 4. 设置坐标刻度 (保持原样)
    ticks = [i / 2.0 for i in range(max(rows, cols) * 2 + 1)]
    tick_labels = [f"{t:g}" for t in ticks]

    ax.set_xticks(ticks)
    ax.set_xticklabels(tick_labels)
    ax.xaxis.tick_top()
    
    y_ticks = [rows - t for t in ticks if t <= rows]
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([f"{t:g}" for t in ticks if t <= rows])

    ax.set_xlim(-0.5, cols + 0.5)
    ax.set_ylim(-0.5, rows + 0.5)
    ax.set_aspect('equal')
    
    for spine in ax.spines.values():
        spine.set_edgecolor('#4A90E2')
        spine.set_linewidth(2)

    plt.tight_layout()
    save_square_figure(fig, output_path)
    plt.close()


def format_slitherlink_to_string(grid, answer_path=None):
    rows = len(grid)
    cols = len(grid[0])
    
    # 辅助函数：判断两个相邻点之间是否有连线
    def has_edge(p1, p2):
        if not answer_path:
            return False
        # 检查 answer_path 中是否存在这对连续的点
        for i in range(len(answer_path)-1):
            curr = answer_path[i]
            nxt = answer_path[(i + 1) % len(answer_path)] # 考虑闭环
            if (curr == p1 and nxt == p2) or (curr == p2 and nxt == p1):
                return True
        return False

    output = []
    
    # 遍历每一行格点
    for r in range(rows + 1):
        # 1. 构建“横向线”行 (例如: +---+   +)
        line_top = []
        for c in range(cols + 1):
            line_top.append("+")
            if c < cols:
                # 检查 (r, c) 和 (r, c+1) 之间是否有横向边
                if has_edge((r, c), (r, c+1)):
                    line_top.append("---")
                else:
                    line_top.append("   ")
        output.append("".join(line_top))
        
        # 2. 构建“纵向线与数字”行 (例如: | 3 | 0 |)
        if r < rows:
            line_mid = []
            for c in range(cols + 1):
                # 检查 (r, c) 和 (r+1, c) 之间是否有纵向边
                if has_edge((r, c), (r+1, c)):
                    line_mid.append("|")
                else:
                    line_mid.append(" ")
                
                # 放置数字
                if c < cols:
                    val = grid[r][c]
                    num_str = f" {val} " if val is not None else "   "
                    line_mid.append(num_str)
            output.append("".join(line_mid))
            
    return "\n".join(output)


def construct_slitherlink_data(puzzle_dict):
    puzzle_dict = normalize_size_keys(puzzle_dict)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.normpath(os.path.join(base_dir, '..', 'puzzles', 'slitherlink'))
    os.makedirs(output_dir, exist_ok=True)
    fig_name = f"slitherlink_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}"
    draw_slitherlink(
        puzzle_dict['original_data']['data'], 
        output_path=os.path.join(output_dir, f"{fig_name}.png")
    )
    answer_fig_name = f"slitherlink_{puzzle_dict['column/row']}_{puzzle_dict['level']}_{puzzle_dict['id']}_answer"
    draw_slitherlink(
        puzzle_dict['original_data']['data'], 
        output_path=os.path.join(output_dir, f"{answer_fig_name}.png"),
        answer=puzzle_dict['answer']
    )
    # output_dict = puzzle_dict.copy()
    output_dict= {'puzzle': 'slitherlink'}
    output_dict.update(puzzle_dict)
    output_dict['fig_name'] = fig_name
    output_dict['answer_fig_name'] = answer_fig_name

    initial_str = format_slitherlink_to_string(puzzle_dict['original_data']['data'])
    answer_str = format_slitherlink_to_string(puzzle_dict['original_data']['data'], puzzle_dict['answer'])
    output_dict['initial_str'] = initial_str
    output_dict['answer_str'] = answer_str

    # print(output_dict['initial_str'])
    # print(output_dict['answer_str'])
        
    return output_dict


def test_observation(observation, gt_observation):
    """Clue grid; exact match."""
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
    n = data['column/row']
    clue_grid = [row[:] for row in data['original_data']['data']]
    if len(clue_grid) != n or any(len(row) != n for row in clue_grid):
        # Keep observation shape consistent with board size when source is sparse/irregular.
        clue_grid = [[None for _ in range(n)] for _ in range(n)]
        for i in range(n):
            for j in range(n):
                v = data['original_data']['data'][i][j]
                if v is not None:
                    clue_grid[i][j] = v
    return {'data': clue_grid}


def return_data():
    ref_puzzle_dict = {
        'column/row': 5,
        'level': 'easy',
        'original_data': {
            'data': [
                [None, None, None, None, None],
                [2, None, 2, None, 2],
                [None, None, None, 3, 0],
                [None, None, 2, None, 2],
                [None, 1, None, None, None]
            ],
        },
        'answer':[
            (0,0), (0,1), (1,1), (2,1), (2,2), (1,2), (1,3), (0,3), (0,4), (0,5),
            (1,5), (1,4), (2,4), (2,3), (3,3), (3,4), (4,4), (4,5), (5,5), (5,4),
            (5,3), (4,3), (4,2), (3,2), (3,1), (4,1), (5,1), (5,0), (4,0), (3,0),
            (2,0), (1,0), (0,0)
        ],
        'reason': '''[(1,4), (2,4), (2,3), (3,3), (3,4), (4,4)]: (2.5, 4.5) is 0 and (2.5, 3.5) is 3;
[(1,4), (1,5), (0,5), (0,4)]: (1.5, 4.5) is 2 and [(2,4), (2,5), (1,5)] can not be lines;
[(4,4), (4,5), (5,5), (5,4)]: (3.5, 4.5) is 2 and [(3,4), (3,5), (4,5)] can not be lines;
[(0,4), (0,3)]: [(0,4), (1,4)] can not be line;
[(5,4), (5,3)]: [(5,4), (4,4)] can not be line;
[(1,3), (1,2), (2,2)]: (1.5, 2.5) is 2 and [(2,2), (2,3), (1,3)] can not be lines;
[(4,3), (4,2), (3,2)]: (3.5, 2.5) is 2 and [(3,2), (3,3), (4,3)] can not be lines;
[(0,3), (1,3)]: [(2,3), (1,3), (1,4)] can not be lines;
[(5,3), (4,3)]: [(3,3), (4,3), (4,4)] can not be lines;
[(3,2), (3,1)]: [(3,2), (2,2)] can not be line;
[(2,2), (2,1)]: [(3,2), (2,2)] can not be line;
[(4,1), (5,1), (5,0), (4,0)]: [(5,3), (5,2)] can not be line, [(4,1), (4,2), (5,2)] can not be lines, [(5,2), (5,1)] can not be lines and (4.5, 1.5) is 1;
[(4,0), (3,0)]: [(4,1), (4,1)] can not be line;
[(3,1), (4,1)]: [(4,1), (4,1)] can not be line;
[(3,0), (2,0)]: [(3,0), (3,1)] can not be line;
[(2,1), (1,1)]: [(2,0), (2,1), (3,1)] can not be lines;
[(2,0), (1,0)]: [(2,0), (2,1)] can not be line;
[(1,0), (0,0), (0,1)]: (1.5, 1.5) is 2, [(1,0), (1,1)] can not be line;
[(1,1), (0,1)]: (1.5, 1.5) is 2, [(1,0), (1,1)] can not be line.
As a result, the puzzle is solvable and the solution could be listed by all the lines above.
''',
        'id': 'ref',
        'rules': RULES,
    }
    
    ref_puzzle_dict['observation'] = get_observation(ref_puzzle_dict)

    puzzles = [
        {
            'column/row': 5,
            'level': 'easy',
            'original_data': {
                'data': [
                    [None, None, None, None, None],
                    [1, 2, None, None, 3],
                    [None, 3, None, 1, 3],
                    [None, 2, None, None, 2],
                    [None, 3, 3, 2, 0]
                ],
            },
            'answer': [
                (0,0), (0,1), (0,2), (1,2), (2,2), (2,1), (3,1), (3,2), (3,3), (2,3),
                (1,3), (0,3), (0,4), (0,5), (1,5), (1,4), (2,4), (2,5), (3,5), (3,4),
                (4,4), (4,3), (5,3), (5,2), (4,2), (4,1), (5,1), (5,0), (4,0), (3,0),
                (2,0), (1,0), (0,0)
            ],
            'id': 'example_0',
            'rules': RULES,
        },
        {
            'column/row': 7,
            'level': 'easy',
            'original_data': {
                'data': [
                    [None, 2, 3, 3, 3, None, 3],
                    [None, None, 2, 0, 2, None, None],
                    [2, 1, 3, 2, None, 1, 2],
                    [None, None, None, 3, 2, 2, 2],
                    [None, None, None, 1, 1, None, None],
                    [None, None, 3, 3, None, None, None],
                    [None, None, None, None, 2, 3, None],
                ],
            },
            'answer': [
                (0, 0), (0, 1), (0, 2), (1, 2), (1, 3), (0, 3), (0, 4), (1, 4), (1, 5), 
                (0, 5), (0, 6), (0, 7), (1, 7), (1, 6), (2, 6), (2, 7), (3, 7), (4, 7), 
                (4, 6), (4, 5), (3, 5), (2, 5), (2, 4), (3, 4), (4, 4), (4, 3), (3, 3), 
                (2, 3), (2, 2), (3, 2), (4, 2), (4, 1), (5, 1), (6, 1), (6, 2), (5, 2), 
                (5, 3), (6, 3), (6, 4), (5, 4), (5, 5), (5, 6), (5, 7), (6, 7), (7, 7), 
                (7, 6), (6, 6), (6, 5), (7, 5), (7, 4), (7, 3), (7, 2), (7, 1), (7, 0), 
                (6, 0), (5, 0), (4, 0), (3, 0), (2, 0), (2, 1), (1, 1), (1, 0), (0, 0)
            ],
            'id': 'example_1',
            'rules': RULES,
        },
        {
            'column/row': 10,
            'level': 'easy',
            'original_data': {
                'data': [
                    [None, None, None, 2, None, None, None, None, None, None],
                    [2, None, 3, None, None, 2, 3, None, None, 2],
                    [2, 1, 2, 0, 3, None, 1, None, 2, None],
                    [None, 2, 3, None, 3, 1, 1, 3, None, None],
                    [None, None, 1, 2, 2, 2, 3, 2, None, None],
                    [2, None, 1, None, 3, None, 2, 2, None, None],
                    [None, None, None, None, None, None, None, None, 2, None],
                    [None, None, 1, 2, None, 2, None, 2, None, 2],
                    [3, None, None, 3, 2, None, None, 2, 2, 3],
                    [3, 2, 2, 2, None, None, None, None, 1, None],
                ],
            },
            'answer': [
                (0, 0), (1, 0), (1, 1), (2, 1), (3, 1), (3, 0), (4, 0), (5, 0), (6, 0), 
                (6, 1), (7, 1), (7, 0), (8, 0), (8, 1), (9, 1), (9, 0), (10, 0), (10, 1), 
                (10, 2), (9, 2), (8, 2), (7, 2), (6, 2), (5, 2), (5, 1), (4, 1), (4, 2), 
                (3, 2), (3, 3), (4, 3), (5, 3), (5, 4), (5, 5), (6, 5), (6, 4), (6, 3), 
                (7, 3), (7, 4), (7, 5), (8, 5), (8, 6), (8, 7), (7, 7), (7, 6), (6, 6), 
                (6, 7), (6, 8), (5, 8), (4, 8), (3, 8), (3, 7), (4, 7), (5, 7), (5, 6), 
                (4, 6), (4, 5), (4, 4), (3, 4), (3, 5), (2, 5), (2, 4), (1, 4), (1, 5), 
                (1, 6), (2, 6), (2, 7), (1, 7), (1, 8), (2, 8), (2, 9), (3, 9), (4, 9), 
                (5, 9), (6, 9), (7, 9), (7, 8), (8, 8), (9, 8), (9, 7), (9, 6), (9, 5), 
                (9, 4), (8, 4), (8, 3), (9, 3), (10, 3), (10, 4), (10, 5), (10, 6), (10, 7), 
                (10, 8), (10, 9), (10, 10), (9, 10), (9, 9), (8, 9), (8, 10), (7, 10), 
                (6, 10), (5, 10), (4, 10), (3, 10), (2, 10), (1, 10), (1, 9), (0, 9), 
                (0, 8), (0, 7), (0, 6), (0, 5), (0, 4), (0, 3), (1, 3), (2, 3), (2, 2), 
                (1, 2), (0, 2), (0, 1), (0, 0)
            ],
            'id': 'example_2',
            'rules': RULES,
        }
    ]

    for puzzle in puzzles:
        puzzle['observation'] = get_observation(puzzle)

    return ref_puzzle_dict, puzzles


if __name__ == "__main__":
    ref_puzzle_dict, puzzles = return_data()
    ret = construct_slitherlink_data(ref_puzzle_dict)
    for puzzle in puzzles:
        ret = construct_slitherlink_data(puzzle)
    print(ret)
