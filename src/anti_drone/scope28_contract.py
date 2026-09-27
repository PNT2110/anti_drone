"""Scope 28 detector-to-tracker observation contract.

This module contains only the adapter-side split.  The frozen detector
threshold remains the public stream threshold (0.25); the auxiliary tracker
stream retains post-NMS observations down to the existing ByteTrack floor
(0.10).  No detector, tracker, or production-package artifact is changed.
"""
from __future__ import annotations

from math import sqrt
from typing import Any


PUBLIC_THRESHOLD = 0.25
TRACKER_FLOOR = 0.10
NMS_IOU = 0.70


def _iou(a: list[float], b: list[float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    aa = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    bb = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = aa + bb - inter
    return inter / union if union else (1.0 if aa == bb == 0 else 0.0)


def _nms(rows: list[dict[str, Any]], iou_threshold: float = NMS_IOU) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: row["confidence"], reverse=True)
    kept: list[dict[str, Any]] = []
    while ordered:
        current = ordered.pop(0)
        kept.append(current)
        ordered = [row for row in ordered if _iou(current["bbox"], row["bbox"]) < iou_threshold]
    return kept


def split_observations(
    candidates: list[dict[str, Any]],
    *,
    public_threshold: float = PUBLIC_THRESHOLD,
    tracker_floor: float = TRACKER_FLOOR,
    nms_iou: float = NMS_IOU,
) -> dict[str, Any]:
    """Apply exactly one NMS, then expose frozen-public and tracker streams.

    Candidate dictionaries are source-frame boxes with the original class and
    confidence.  The function intentionally does not alter confidence or
    create boxes.  It also rejects a configuration that would make the
    auxiliary floor higher than the public threshold.
    """
    if not 0 <= tracker_floor <= public_threshold <= 1:
        raise ValueError("tracker_floor must be <= public_threshold in [0,1]")
    floor_candidates = [row for row in candidates if float(row["confidence"]) >= tracker_floor]
    kept = _nms(floor_candidates, nms_iou)
    high, low = split_kept_observations(kept, public_threshold=public_threshold, tracker_floor=tracker_floor)
    for row in high + low:
        row["stream"] = "FROZEN_PUBLIC_STREAM" if row in high else "TRACKER_LOW_STREAM"
    return {
        "raw_candidate_count": len(candidates),
        "floor_candidate_count": len(floor_candidates),
        "nms_applications": 1,
        "nms_iou": nms_iou,
        "public_threshold": public_threshold,
        "tracker_floor": tracker_floor,
        "high": high,
        "low": low,
        "tracker_observations": high + low,
    }


def nms_candidates(candidates: list[dict[str, Any]], nms_iou: float = NMS_IOU) -> list[dict[str, Any]]:
    """Expose the single adapter NMS stage for measured diagnostics/tests."""
    return _nms(candidates, nms_iou)


def suppress_contained_duplicates(
    rows: list[dict[str, Any]],
    *,
    minimum_containment: float = 0.80,
    minimum_area_ratio: float = 1.12,
    minimum_larger_confidence_ratio: float = 0.55,
) -> tuple[list[dict[str, Any]], int]:
    """Drop part-box duplicates while preserving the frozen NMS threshold.

    Close USB views can produce one box around the whole visible drone and a
    second box around an arm/rotor mostly inside it. Their IoU is often below
    0.70, so ordinary NMS correctly leaves both. For the one-class live-camera
    candidate only, suppress the smaller box when at least 80% of it overlaps
    a box at least 1.12x larger and the larger confidence is still credible.
    This does not merge boxes, change confidence, or apply NMS a second time.
    """

    def area(row: dict[str, Any]) -> float:
        x1, y1, x2, y2 = row["bbox"]
        return max(0.0, float(x2) - float(x1)) * max(0.0, float(y2) - float(y1))

    def intersection(a: dict[str, Any], b: dict[str, Any]) -> float:
        ax1, ay1, ax2, ay2 = a["bbox"]
        bx1, by1, bx2, by2 = b["bbox"]
        return max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))

    suppressed: set[int] = set()
    for small_index, small in enumerate(rows):
        small_area = area(small)
        if small_area <= 0:
            continue
        for large_index, large in enumerate(rows):
            if small_index == large_index or int(small["class"]) != int(large["class"]):
                continue
            large_area = area(large)
            if large_area < small_area * minimum_area_ratio:
                continue
            if intersection(small, large) / small_area < minimum_containment:
                continue
            if float(large["confidence"]) < float(small["confidence"]) * minimum_larger_confidence_ratio:
                continue
            suppressed.add(small_index)
            break
    kept = [row for index, row in enumerate(rows) if index not in suppressed]
    kept.sort(key=lambda row: float(row["confidence"]), reverse=True)
    return kept, len(suppressed)


def select_single_drone_observation(
    high: list[dict[str, Any]],
    low: list[dict[str, Any]],
    *,
    preferred_point: tuple[float, float] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Keep one whole-object candidate for a declared single-drone session.

    Confidence multiplied by the square root of area balances confidence with
    whole-object coverage, so a high-confidence rotor/arm crop does not win
    merely because it is tight. HIGH always takes precedence over LOW; LOW is
    retained only when no HIGH observation exists. Thresholds and NMS remain
    unchanged, and no synthetic box is created.
    """

    def score(row: dict[str, Any]) -> float:
        x1, y1, x2, y2 = row["bbox"]
        area = max(0.0, float(x2) - float(x1)) * max(0.0, float(y2) - float(y1))
        return float(row["confidence"]) * sqrt(area)

    def point_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if preferred_point is None:
            return rows
        px, py = preferred_point
        return [row for row in rows if row["bbox"][0] <= px <= row["bbox"][2] and row["bbox"][1] <= py <= row["bbox"][3]]

    if high:
        eligible = point_candidates(high)
        if not eligible:
            return [], [], len(high) + len(low)
        selected = max(eligible, key=score)
        return [selected], [], len(high) + len(low) - 1
    if low:
        eligible = point_candidates(low)
        if not eligible:
            return [], [], len(low)
        selected = max(eligible, key=score)
        return [], [selected], len(low) - 1
    return [], [], 0


def split_kept_observations(
    kept: list[dict[str, Any]], *, public_threshold: float = PUBLIC_THRESHOLD, tracker_floor: float = TRACKER_FLOOR
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    high = [row for row in kept if float(row["confidence"]) >= public_threshold]
    low = [row for row in kept if tracker_floor <= float(row["confidence"]) < public_threshold]
    for row in high:
        row["stream"] = "FROZEN_PUBLIC_STREAM"
    for row in low:
        row["stream"] = "TRACKER_LOW_STREAM"
    return high, low


def compare_detections(reference: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> dict[str, Any]:
    """Scope 20/21 frozen parity gate for ordered single-class detections."""
    result: dict[str, Any] = {
        "status": "PARITY_PASS",
        "reference_count": len(reference),
        "candidate_count": len(candidate),
        "max_confidence_abs": 0.0,
        "min_bbox_iou": 1.0,
        "class_exact": True,
    }
    if len(reference) != len(candidate):
        result["status"] = "PARITY_FAIL"
    for left, right in zip(reference, candidate):
        result["max_confidence_abs"] = max(result["max_confidence_abs"], abs(float(left["confidence"]) - float(right["confidence"])))
        result["min_bbox_iou"] = min(result["min_bbox_iou"], _iou(left["bbox"], right["bbox"]))
        result["class_exact"] = bool(result["class_exact"] and int(left["class"]) == int(right["class"]))
    if result["max_confidence_abs"] > 0.05 or result["min_bbox_iou"] < 0.95 or not result["class_exact"]:
        result["status"] = "PARITY_FAIL"
    return result


def box_iou(a: list[float], b: list[float]) -> float:
    return _iou(a, b)
