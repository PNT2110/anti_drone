"""Small, dependency-free association helpers for ByteTrack."""

from __future__ import annotations

from itertools import permutations
from typing import Iterable

import numpy as np


def valid_box(box: np.ndarray | Iterable[float]) -> bool:
    values = np.asarray(box, dtype=np.float32)
    return bool(values.shape == (4,) and np.isfinite(values).all() and values[2] > values[0] and values[3] > values[1])


def xyxy_to_xywh(box: np.ndarray | Iterable[float]) -> list[float]:
    x1, y1, x2, y2 = map(float, box)
    return [x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)]


def box_iou(a: np.ndarray, b: np.ndarray) -> float:
    if not valid_box(a) or not valid_box(b):
        return 0.0
    x1 = max(float(a[0]), float(b[0]))
    y1 = max(float(a[1]), float(b[1]))
    x2 = min(float(a[2]), float(b[2]))
    y2 = min(float(a[3]), float(b[3]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = (float(a[2]) - float(a[0])) * (float(a[3]) - float(a[1]))
    area_b = (float(b[2]) - float(b[0])) * (float(b[3]) - float(b[1]))
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def center_distance(a: np.ndarray, b: np.ndarray) -> float:
    ac = np.array([(a[0] + a[2]) / 2, (a[1] + a[3]) / 2], dtype=np.float32)
    bc = np.array([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2], dtype=np.float32)
    return float(np.linalg.norm(ac - bc))


def normalized_center_distance(a: np.ndarray, b: np.ndarray) -> float:
    diagonal = max(1.0, float(np.hypot(a[2] - a[0], a[3] - a[1])))
    return center_distance(a, b) / diagonal


def assign_min_cost(cost: np.ndarray) -> list[tuple[int, int]]:
    """Return a deterministic one-to-one minimum-cost assignment.

    A bitmask dynamic program is optimal for the small number of drones this
    runtime targets. For unusually large scenes it falls back to globally
    sorted valid pairs to keep memory and CPU bounded on the Pi.
    """

    if cost.ndim != 2 or not cost.size:
        return []
    rows, cols = cost.shape
    if rows <= 12 and cols <= 12:
        memo: dict[tuple[int, int], tuple[float, tuple[tuple[int, int], ...]]] = {}

        def solve(row: int, used: int) -> tuple[tuple[int, float], tuple[tuple[int, int], ...]]:
            key = (row, used)
            if key in memo:
                return memo[key]
            if row == rows:
                return (0, 0.0), ()
            skip_count, skip_cost = solve(row + 1, used)[0]
            best = ((skip_count, skip_cost), solve(row + 1, used)[1])
            for col in range(cols):
                value = float(cost[row, col])
                if used & (1 << col) or not np.isfinite(value):
                    continue
                tail_score, tail_pairs = solve(row + 1, used | (1 << col))
                candidate = ((tail_score[0] + 1, tail_score[1] + value), ((row, col),) + tail_pairs)
                if candidate[0][0] > best[0][0] or (candidate[0][0] == best[0][0] and candidate[0][1] < best[0][1] - 1e-9) or (candidate[0] == best[0] and candidate[1] < best[1]):
                    best = candidate
            memo[key] = best
            return best

        return list(solve(0, 0)[1])

    pairs = [(float(value), row, col) for row in range(rows) for col, value in enumerate(cost[row]) if np.isfinite(value)]
    pairs.sort(key=lambda item: (item[0], item[1], item[2]))
    used_rows: set[int] = set()
    used_cols: set[int] = set()
    return [(row, col) for _, row, col in pairs if row not in used_rows and col not in used_cols and not (used_rows.add(row) or used_cols.add(col))]
