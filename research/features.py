from __future__ import annotations

import math
from types import SimpleNamespace

from gestures import (
    INDEX_MCP, INDEX_PIP, INDEX_TIP, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP,
    PINKY_MCP, PINKY_PIP, PINKY_TIP, RING_MCP, RING_PIP, RING_TIP,
    THUMB_CMC, THUMB_TIP, WRIST,
)

SCHEMA_VERSION = 1
LANDMARK_COUNT = 21


def landmarks_from_flat(row: dict) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            x=float(row[f"x{i}"]), y=float(row[f"y{i}"]), z=float(row[f"z{i}"])
        )
        for i in range(LANDMARK_COUNT)
    ]


def _dist3(a, b) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def _angle(a, b, c) -> float:
    ab = (a.x - b.x, a.y - b.y, a.z - b.z)
    cb = (c.x - b.x, c.y - b.y, c.z - b.z)
    denom = math.sqrt(sum(v * v for v in ab)) * math.sqrt(sum(v * v for v in cb))
    if denom < 1e-9:
        return 0.0
    cosine = max(-1.0, min(1.0, sum(x * y for x, y in zip(ab, cb)) / denom))
    return math.degrees(math.acos(cosine)) / 180.0


def feature_names() -> list[str]:
    coords = [f"lm{i}_{axis}" for i in range(LANDMARK_COUNT) for axis in "xyz"]
    engineered = [
        "thumb_index_distance", "thumb_middle_distance", "index_middle_distance",
        "thumb_index_mcp_distance", "thumb_dx", "thumb_dy",
        "index_angle", "middle_angle", "ring_angle", "pinky_angle",
        "index_tip_radius", "middle_tip_radius", "ring_tip_radius", "pinky_tip_radius",
    ]
    return coords + engineered


def extract_features(lms) -> list[float]:
    """Wrist-centred, hand-size-normalized coordinates plus readable geometry."""
    origin = lms[WRIST]
    scale = _dist3(origin, lms[MIDDLE_MCP]) or 1e-6
    values = []
    for lm in lms:
        values.extend(((lm.x - origin.x) / scale, (lm.y - origin.y) / scale,
                       (lm.z - origin.z) / scale))

    def d(a: int, b: int) -> float:
        return _dist3(lms[a], lms[b]) / scale

    values.extend([
        d(THUMB_TIP, INDEX_TIP), d(THUMB_TIP, MIDDLE_TIP),
        d(INDEX_TIP, MIDDLE_TIP), d(THUMB_TIP, INDEX_MCP),
        (lms[THUMB_TIP].x - lms[THUMB_CMC].x) / scale,
        (lms[THUMB_TIP].y - lms[THUMB_CMC].y) / scale,
        _angle(lms[INDEX_MCP], lms[INDEX_PIP], lms[INDEX_TIP]),
        _angle(lms[MIDDLE_MCP], lms[MIDDLE_PIP], lms[MIDDLE_TIP]),
        _angle(lms[RING_MCP], lms[RING_PIP], lms[RING_TIP]),
        _angle(lms[PINKY_MCP], lms[PINKY_PIP], lms[PINKY_TIP]),
        d(INDEX_TIP, WRIST), d(MIDDLE_TIP, WRIST),
        d(RING_TIP, WRIST), d(PINKY_TIP, WRIST),
    ])
    return values
