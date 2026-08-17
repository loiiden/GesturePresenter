"""Landmark → feature-vector conversion shared by training and inference.

This module is deliberately part of the shipped application rather than the
research package: the trainer imports it too, so the feature definition used to
fit a model and the one used to serve it cannot drift apart.

The only dependency is NumPy, which MediaPipe already requires.

Invariances built in here (in application order):

1. **Aspect correction.** MediaPipe normalizes ``x`` by frame width and ``y`` by
   frame height *separately*, so a hand recorded on a 16:9 camera arrives
   stretched ~1.78x horizontally relative to a 4:3 one. Multiplying ``x`` (and
   ``z``, which MediaPipe documents as sharing ``x``'s scale) by the aspect
   ratio restores isotropy and makes a model portable across cameras.
2. **Chirality.** The left hand is mirrored into the right hand's frame so one
   model serves both hands.
3. **Rigid-palm normalization.** Coordinates are centred on the centroid of the
   five palm landmarks and scaled by their RMS radius. Those five points do not
   move when fingers curl, so the resulting scale is independent of both pose
   and distance from the camera.

Feature blocks are individually switchable so their contribution can be
ablated; :func:`feature_names` always matches :func:`extract_features` for the
same :class:`FeatureConfig`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# ── Landmark indices (mirrors gestures.py, kept local to avoid a cycle) ────────
WRIST = 0
THUMB_CMC = 1; THUMB_MCP = 2; THUMB_IP = 3; THUMB_TIP = 4
INDEX_MCP = 5; INDEX_PIP = 6; INDEX_TIP = 8
MIDDLE_MCP = 9; MIDDLE_PIP = 10; MIDDLE_TIP = 12
RING_MCP = 13; RING_PIP = 14; RING_TIP = 16
PINKY_MCP = 17; PINKY_PIP = 18; PINKY_TIP = 20

LANDMARK_COUNT = 21

#: Landmarks forming the rigid palm. Unlike fingertips these keep their mutual
#: distances whatever the pose, which is what makes them a stable scale ruler.
PALM_IDS = (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)

FINGER_CHAINS = (
    ("thumb", THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP),
    ("index", INDEX_MCP, INDEX_PIP, 7, INDEX_TIP),
    ("middle", MIDDLE_MCP, MIDDLE_PIP, 11, MIDDLE_TIP),
    ("ring", RING_MCP, RING_PIP, 15, RING_TIP),
    ("pinky", PINKY_MCP, PINKY_PIP, 19, PINKY_TIP),
)

TIP_IDS = (THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP)

_PAIR_FEATURES = (
    ("thumb_index", THUMB_TIP, INDEX_TIP),
    ("thumb_middle", THUMB_TIP, MIDDLE_TIP),
    ("thumb_ring", THUMB_TIP, RING_TIP),
    ("index_middle", INDEX_TIP, MIDDLE_TIP),
    ("middle_ring", MIDDLE_TIP, RING_TIP),
    ("ring_pinky", RING_TIP, PINKY_TIP),
    ("thumb_index_mcp", THUMB_TIP, INDEX_MCP),
)

FEATURE_VERSION = 2


@dataclass(frozen=True)
class FeatureConfig:
    """Which feature blocks to emit. Defaults are what the shipped model uses."""

    canonical: bool = True      # 63 — palm-normalized 3-D image coordinates
    upright: bool = True        # 42 — the same shape with in-plane rotation removed
    orientation: bool = True    #  6 — how the hand is rotated in the image
    geometry: bool = True       # 23 — human-readable distances and joint angles
    world: bool = True          # 63 — MediaPipe metric 3-D landmarks

    def as_dict(self) -> dict:
        return {
            "canonical": self.canonical, "upright": self.upright,
            "orientation": self.orientation, "geometry": self.geometry,
            "world": self.world,
        }


DEFAULT_CONFIG = FeatureConfig()


# ── Normalization ─────────────────────────────────────────────────────────────

def to_array(landmarks) -> np.ndarray:
    """Accept MediaPipe landmarks, dicts, or an array and return an (N, 3) array."""
    if isinstance(landmarks, np.ndarray):
        return landmarks.astype(np.float64, copy=False).reshape(-1, 3)
    return np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float64)


def normalize_image_points(points: np.ndarray, aspect: float, mirror: bool) -> np.ndarray:
    """Undo MediaPipe's per-axis normalization and canonicalize handedness.

    ``aspect`` is frame width / height. ``z`` is scaled with ``x`` because
    MediaPipe documents them as sharing a scale.
    """
    out = points.copy()
    out[:, 0] *= aspect
    out[:, 2] *= aspect
    if mirror:
        out[:, 0] = -out[:, 0]
    return out


def palm_frame(points: np.ndarray) -> tuple[np.ndarray, float]:
    """Return the palm centroid and its RMS radius (the pose-independent scale)."""
    palm = points[list(PALM_IDS)]
    centroid = palm.mean(axis=0)
    radius = float(np.sqrt(((palm - centroid) ** 2).sum(axis=1).mean()))
    return centroid, max(radius, 1e-9)


def canonicalize(points: np.ndarray) -> np.ndarray:
    """Centre on the palm centroid and scale to unit palm radius."""
    centroid, radius = palm_frame(points)
    return (points - centroid) / radius


def _palm_angle(canonical: np.ndarray) -> float:
    """In-image angle of the wrist → middle-knuckle axis, in radians."""
    axis = canonical[MIDDLE_MCP, :2] - canonical[WRIST, :2]
    return float(np.arctan2(axis[1], axis[0]))


def upright_xy(canonical: np.ndarray, angle: float | None = None) -> np.ndarray:
    """Rotate the hand in-plane so its palm axis points up (-Y).

    This gives the model an orientation-free view of hand *shape*, which is what
    distinguishes e.g. a V-sign from a two-finger scroll. Orientation itself is
    not discarded — it is supplied separately by the orientation block, because
    the thumb-direction classes are defined by it.
    """
    if angle is None:
        angle = _palm_angle(canonical)
    # Rotate by (-pi/2 - angle) so the axis lands on -Y.
    delta = -np.pi / 2 - angle
    cos, sin = np.cos(delta), np.sin(delta)
    rotation = np.array([[cos, -sin], [sin, cos]])
    return canonical[:, :2] @ rotation.T


# ── Feature blocks ────────────────────────────────────────────────────────────

def _unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 1e-9 else np.zeros_like(vector)


def _joint_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Interior angle ABC scaled to 0..1, where 1 is a perfectly straight joint."""
    ab, cb = a - b, c - b
    denom = np.linalg.norm(ab) * np.linalg.norm(cb)
    if denom < 1e-9:
        return 0.0
    cosine = float(np.clip(np.dot(ab, cb) / denom, -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)) / 180.0)


def _geometry_block(canonical: np.ndarray) -> list[float]:
    values = [
        float(np.linalg.norm(canonical[a] - canonical[b])) for _, a, b in _PAIR_FEATURES
    ]
    for _, mcp, pip, dip, tip in FINGER_CHAINS:
        values.append(_joint_angle(canonical[mcp], canonical[pip], canonical[tip]))
        values.append(_joint_angle(canonical[pip], canonical[dip], canonical[tip]))
    # Tip distance from the palm centre separates curled from extended fingers
    # even when a joint angle is ambiguous under foreshortening.
    values.extend(float(np.linalg.norm(canonical[tip])) for tip in TIP_IDS)
    values.append(float(np.linalg.norm(canonical[THUMB_TIP] - canonical[PINKY_TIP])))
    return values


def _orientation_block(canonical: np.ndarray, angle: float) -> list[float]:
    """Rotation of the hand and of the thumb, as sin/cos pairs.

    Angles are encoded as sin/cos rather than radians so the representation is
    continuous across the +/-pi wrap, which a raw angle is not.
    """
    thumb = _unit(canonical[THUMB_TIP, :2] - canonical[THUMB_CMC, :2])
    spread = _unit(canonical[INDEX_MCP, :2] - canonical[PINKY_MCP, :2])
    return [np.cos(angle), np.sin(angle), thumb[0], thumb[1], spread[0], spread[1]]


# ── Public API ────────────────────────────────────────────────────────────────

def feature_names(config: FeatureConfig = DEFAULT_CONFIG) -> list[str]:
    names: list[str] = []
    if config.canonical:
        names += [f"canon{i}_{axis}" for i in range(LANDMARK_COUNT) for axis in "xyz"]
    if config.upright:
        names += [f"upright{i}_{axis}" for i in range(LANDMARK_COUNT) for axis in "xy"]
    if config.orientation:
        names += ["palm_cos", "palm_sin", "thumb_dx", "thumb_dy", "spread_dx", "spread_dy"]
    if config.geometry:
        names += [f"dist_{name}" for name, _, _ in _PAIR_FEATURES]
        for finger, *_ in FINGER_CHAINS:
            names += [f"{finger}_proximal_angle", f"{finger}_distal_angle"]
        names += [f"{finger}_tip_radius" for finger, *_ in FINGER_CHAINS]
        names += ["thumb_pinky_span"]
    if config.world:
        names += [f"world{i}_{axis}" for i in range(LANDMARK_COUNT) for axis in "xyz"]
    return names


def prepare_points(
    image_landmarks, world_landmarks=None, aspect: float = 1.0, hand: str = "Right"
) -> tuple[np.ndarray, np.ndarray | None]:
    """Apply aspect correction and chirality canonicalization.

    Returns points in an isotropic, right-handed space that is still un-centred
    and un-scaled, which is what augmentation needs to operate on: rotations and
    noise must be applied before the palm normalization absorbs them.
    """
    mirror = str(hand).lower().startswith("l")
    points = normalize_image_points(to_array(image_landmarks), aspect, mirror)
    world = None
    if world_landmarks is not None:
        world = to_array(world_landmarks).copy()
        # World landmarks are already metric and aspect-free; they need only the
        # same chirality canonicalization.
        if mirror:
            world[:, 0] = -world[:, 0]
    return points, world


def extract_features(
    image_landmarks,
    world_landmarks=None,
    aspect: float = 1.0,
    hand: str = "Right",
    config: FeatureConfig = DEFAULT_CONFIG,
) -> np.ndarray:
    """Build one feature vector.

    ``hand`` is the *anatomical* hand. Left hands are mirrored so that every
    sample is expressed in the right hand's frame.
    """
    points, world = prepare_points(image_landmarks, world_landmarks, aspect, hand)
    return features_from_points(points, world, config)


def features_from_points(
    points: np.ndarray,
    world: np.ndarray | None = None,
    config: FeatureConfig = DEFAULT_CONFIG,
) -> np.ndarray:
    """Feature blocks from already aspect- and chirality-corrected points."""
    canonical = canonicalize(points)
    angle = _palm_angle(canonical)

    values: list[float] = []
    if config.canonical:
        values.extend(canonical.reshape(-1).tolist())
    if config.upright:
        values.extend(upright_xy(canonical, angle).reshape(-1).tolist())
    if config.orientation:
        values.extend(_orientation_block(canonical, angle))
    if config.geometry:
        values.extend(_geometry_block(canonical))
    if config.world:
        if world is None:
            values.extend([0.0] * (LANDMARK_COUNT * 3))
        else:
            values.extend(canonicalize(world).reshape(-1).tolist())
    return np.asarray(values, dtype=np.float64)


def feature_count(config: FeatureConfig = DEFAULT_CONFIG) -> int:
    return len(feature_names(config))
