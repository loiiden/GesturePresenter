"""Training-time augmentation of hand landmarks.

Augmentation is what turns a single-person, single-room recording into a model
that survives other cameras and other rooms, so it is worth being precise about
what each transform stands in for — and about what is *not* here.

**Not augmented: uniform scale and translation.** Both are already removed by
the palm-rigid normalization in :mod:`gesture_features`. Jittering them would
produce identical feature vectors and merely duplicate rows. Their absence is
evidence the normalization does its job, not an oversight.

**Rotation is capped per class.** ``fist_thumb_up``, ``fist_thumb_left`` and
``fist_thumb_right`` are *defined* by their in-image orientation: rotating one
by 40 degrees turns it into a different class while keeping the old label.
Those classes get a tight cap; orientation-free poses get a wide one.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gesture_features import DEFAULT_CONFIG, FeatureConfig, features_from_points

#: Classes whose label depends on how the hand is rotated in the image.
ORIENTATION_SENSITIVE = frozenset({
    "fist_thumb_up", "fist_thumb_left", "fist_thumb_right",
})


@dataclass(frozen=True)
class AugmentConfig:
    copies: int = 6
    #: In-plane rotation, degrees. The tight cap protects the thumb classes.
    roll_degrees: float = 25.0
    roll_degrees_oriented: float = 10.0
    #: Out-of-plane rotation, degrees — stands in for viewing angle.
    pitch_degrees: float = 12.0
    yaw_degrees: float = 12.0
    #: Landmark jitter as a fraction of the palm radius — stands in for sensor
    #: noise, motion blur and dim lighting.
    noise_min: float = 0.005
    noise_max: float = 0.045
    #: Mild anisotropic scaling — stands in for lens and perspective variation
    #: that exact aspect correction does not cover.
    stretch: float = 0.05
    seed: int = 20260817


def _rotation(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """Z (in-plane) then Y then X rotation, angles in radians."""
    cz, sz = np.cos(roll), np.sin(roll)
    cy, sy = np.cos(yaw), np.sin(yaw)
    cx, sx = np.cos(pitch), np.sin(pitch)
    rz = np.array([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]])
    ry = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]])
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]])
    return rz @ ry @ rx


def _transform(points: np.ndarray, matrix: np.ndarray, centre: np.ndarray,
               stretch: np.ndarray, noise: np.ndarray) -> np.ndarray:
    moved = (points - centre) @ matrix.T
    return moved * stretch + noise + centre


def augment_sample(
    points: np.ndarray,
    world: np.ndarray | None,
    label: str,
    rng: np.random.Generator,
    config: AugmentConfig,
    feature_config: FeatureConfig = DEFAULT_CONFIG,
) -> list[np.ndarray]:
    """Return ``config.copies`` augmented feature vectors for one sample."""
    from gesture_features import palm_frame

    cap = (config.roll_degrees_oriented if label in ORIENTATION_SENSITIVE
           else config.roll_degrees)
    centre, radius = palm_frame(points)
    world_radius = palm_frame(world)[1] if world is not None else 1.0
    world_centre = palm_frame(world)[0] if world is not None else None

    out: list[np.ndarray] = []
    for _ in range(config.copies):
        matrix = _rotation(
            np.radians(rng.uniform(-cap, cap)),
            np.radians(rng.uniform(-config.pitch_degrees, config.pitch_degrees)),
            np.radians(rng.uniform(-config.yaw_degrees, config.yaw_degrees)),
        )
        stretch = 1.0 + rng.uniform(-config.stretch, config.stretch, size=3)
        sigma = rng.uniform(config.noise_min, config.noise_max)
        noisy = _transform(
            points, matrix, centre, stretch,
            rng.normal(0.0, sigma * radius, size=points.shape),
        )
        noisy_world = None
        if world is not None:
            noisy_world = _transform(
                world, matrix, world_centre, stretch,
                rng.normal(0.0, sigma * world_radius, size=world.shape),
            )
        out.append(features_from_points(noisy, noisy_world, feature_config))
    return out


def expand(
    samples: list[tuple[np.ndarray, np.ndarray | None]],
    labels,
    groups,
    config: AugmentConfig,
    feature_config: FeatureConfig = DEFAULT_CONFIG,
):
    """Augment a training set, keeping labels and trial groups aligned.

    Groups are carried through so an augmented copy never lands on the other
    side of a grouped train/validation split from its original.
    """
    rng = np.random.default_rng(config.seed)
    features, out_labels, out_groups = [], [], []
    for (points, world), label, group in zip(samples, labels, groups):
        features.append(features_from_points(points, world, feature_config))
        out_labels.append(label)
        out_groups.append(group)
        for vector in augment_sample(points, world, label, rng, config, feature_config):
            features.append(vector)
            out_labels.append(label)
            out_groups.append(group)
    return np.stack(features), np.array(out_labels), np.array(out_groups)
