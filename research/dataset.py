"""CSV schema and loading for recorded gesture landmarks.

Schema v2 stores everything needed to rebuild a feature vector later without
re-recording: both the image-space and metric world landmarks, the capture
resolution (so aspect correction is exact rather than assumed), the anatomical
hand, and the recording condition. Per-frame quality signals are stored too, so
poor frames can be filtered at training time instead of being silently trusted.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import numpy as np

from gesture_features import (
    DEFAULT_CONFIG, LANDMARK_COUNT, FeatureConfig, extract_features, prepare_points,
)

SCHEMA_VERSION = 2

META_COLUMNS = [
    "schema_version", "participant_id", "session_id", "trial_id", "gesture",
    "condition", "hand", "frame_index", "timestamp_ms",
    "frame_width", "frame_height",
    "mp_handedness", "handedness_score",
    "hand_span", "edge_margin",
]
IMAGE_COLUMNS = [f"{axis}{i}" for i in range(LANDMARK_COUNT) for axis in "xyz"]
WORLD_COLUMNS = [f"w{axis}{i}" for i in range(LANDMARK_COUNT) for axis in "xyz"]
COLUMNS = META_COLUMNS + IMAGE_COLUMNS + WORLD_COLUMNS

#: A trial is identified by these fields together; frames within one trial are
#: not independent samples and must never be split across a train/test boundary.
TRIAL_KEY = ("participant_id", "session_id", "trial_id")


def append_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def rewrite_without_trials(path: Path, trial_ids: set[str]) -> int:
    """Drop whole trials from a dataset file. Returns the number of rows removed.

    Used by the recorder's review step. Deletion is by trial, never by frame,
    so a partially removed trial can't leave a biased remainder behind.
    """
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    kept = [row for row in rows if row["trial_id"] not in trial_ids]
    removed = len(rows) - len(kept)
    if not removed:
        return 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(kept)
    return removed


def read_rows(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        if not path.exists():
            raise SystemExit(f"Dataset not found: {path}")
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                version = int(row["schema_version"])
                if version != SCHEMA_VERSION:
                    raise SystemExit(
                        f"{path} uses schema v{version}, this pipeline needs "
                        f"v{SCHEMA_VERSION}. Older recordings lack world landmarks "
                        f"and capture resolution and cannot be upgraded."
                    )
                row["source_file"] = str(path)
                rows.append(row)
    if not rows:
        raise SystemExit("No dataset rows found")
    return rows


def filter_rows(
    rows: list[dict],
    min_score: float = 0.0,
    min_edge_margin: float = 0.0,
    conditions: set[str] | None = None,
    hands: set[str] | None = None,
) -> list[dict]:
    def keep(row: dict) -> bool:
        if float(row["handedness_score"]) < min_score:
            return False
        if float(row["edge_margin"]) < min_edge_margin:
            return False
        if conditions and row["condition"] not in conditions:
            return False
        if hands and row["hand"] not in hands:
            return False
        return True

    return [row for row in rows if keep(row)]


def _landmarks(row: dict, columns: list[str]) -> np.ndarray:
    return np.array([float(row[name]) for name in columns], dtype=np.float64).reshape(-1, 3)


def row_aspect(row: dict) -> float:
    height = float(row["frame_height"]) or 1.0
    return float(row["frame_width"]) / height


def row_points(row: dict) -> tuple[np.ndarray, np.ndarray | None]:
    """Aspect- and chirality-corrected landmarks, ready for augmentation."""
    return prepare_points(
        _landmarks(row, IMAGE_COLUMNS),
        _landmarks(row, WORLD_COLUMNS),
        aspect=row_aspect(row),
        hand=row["hand"],
    )


def row_features(row: dict, config: FeatureConfig = DEFAULT_CONFIG) -> np.ndarray:
    return extract_features(
        _landmarks(row, IMAGE_COLUMNS),
        _landmarks(row, WORLD_COLUMNS),
        aspect=row_aspect(row),
        hand=row["hand"],
        config=config,
    )


def matrix(rows: list[dict], config: FeatureConfig = DEFAULT_CONFIG):
    """Return (X, y, groups) where groups are trial keys for grouped splitting."""
    X = np.stack([row_features(row, config) for row in rows])
    y = np.array([row["gesture"] for row in rows])
    groups = np.array(["|".join(row[key] for key in TRIAL_KEY) for row in rows])
    return X, y, groups


def majority_by_trial(rows: list[dict], predictions) -> tuple[list[str], list[str]]:
    """Collapse frame predictions into one prediction per trial.

    Trial-level accuracy is the honest headline metric: neighbouring video
    frames are near-duplicates, so frame accuracy overstates performance.
    """
    grouped: dict[tuple, list[tuple[str, str]]] = {}
    for row, prediction in zip(rows, predictions):
        key = tuple(row[name] for name in TRIAL_KEY)
        grouped.setdefault(key, []).append((row["gesture"], str(prediction)))
    truth, predicted = [], []
    for samples in grouped.values():
        truth.append(Counter(label for label, _ in samples).most_common(1)[0][0])
        predicted.append(Counter(label for _, label in samples).most_common(1)[0][0])
    return truth, predicted


def summarize(rows: list[dict]) -> dict:
    """Counts used by the recorder UI and by training reports."""
    trials: dict[tuple, dict] = {}
    for row in rows:
        trials.setdefault(tuple(row[name] for name in TRIAL_KEY), row)
    per_gesture: Counter = Counter()
    per_condition: Counter = Counter()
    per_pair: Counter = Counter()
    per_hand: Counter = Counter()
    for row in trials.values():
        per_gesture[row["gesture"]] += 1
        per_condition[row["condition"]] += 1
        per_pair[(row["gesture"], row["condition"])] += 1
        per_hand[row["hand"]] += 1
    return {
        "frames": len(rows),
        "trials": len(trials),
        "sessions": sorted({row["session_id"] for row in rows}),
        "per_gesture": dict(per_gesture),
        "per_condition": dict(per_condition),
        "per_hand": dict(per_hand),
        "per_pair": {f"{g}|{c}": n for (g, c), n in per_pair.items()},
    }
