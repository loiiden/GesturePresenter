from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from research.features import LANDMARK_COUNT, SCHEMA_VERSION, extract_features, landmarks_from_flat

META_COLUMNS = [
    "schema_version", "participant_id", "session_id", "trial_id", "gesture",
    "frame_index", "timestamp_ms", "handedness", "handedness_score",
]
LANDMARK_COLUMNS = [f"{axis}{i}" for i in range(LANDMARK_COUNT) for axis in "xyz"]
COLUMNS = META_COLUMNS + LANDMARK_COLUMNS


def append_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def read_rows(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if int(row["schema_version"]) != SCHEMA_VERSION:
                    raise ValueError(f"Unsupported schema in {path}: {row['schema_version']}")
                row["source_file"] = str(path)
                rows.append(row)
    if not rows:
        raise ValueError("No dataset rows found")
    return rows


def matrix(rows: list[dict]):
    return [extract_features(landmarks_from_flat(row)) for row in rows], [r["gesture"] for r in rows]


def majority_by_trial(rows: list[dict], predictions: list[str]):
    grouped: dict[tuple, list[tuple[str, str]]] = {}
    for row, prediction in zip(rows, predictions):
        key = (row["participant_id"], row["session_id"], row["trial_id"])
        grouped.setdefault(key, []).append((row["gesture"], str(prediction)))
    truth, predicted = [], []
    for samples in grouped.values():
        truth.append(Counter(label for label, _ in samples).most_common(1)[0][0])
        predicted.append(Counter(label for _, label in samples).most_common(1)[0][0])
    return truth, predicted
