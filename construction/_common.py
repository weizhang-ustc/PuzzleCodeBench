from __future__ import annotations

from typing import Any, Dict


def normalize_size_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return data

    if "column/row" not in data:
        row = data.get("row")
        col = data.get("column")
        if isinstance(row, int) and isinstance(col, int):
            if row != col:
                raise ValueError(f"non-square puzzle item not supported: row={row}, column={col}")
            data["column/row"] = row
        elif isinstance(row, int):
            data["column/row"] = row
        elif isinstance(col, int):
            data["column/row"] = col
        else:
            original = data.get("original_data")
            if isinstance(original, dict):
                grid = original.get("data")
                if isinstance(grid, list) and grid and isinstance(grid[0], list):
                    n = len(grid)
                    if all(isinstance(r, list) and len(r) == n for r in grid):
                        data["column/row"] = n

    n = data.get("column/row")
    if isinstance(n, int) and n > 0:
        data.setdefault("row", n)
        data.setdefault("column", n)
    return data
