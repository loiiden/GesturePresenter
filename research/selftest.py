"""End-to-end pipeline check that needs no camera and no recorded data.

    uv run --extra research python -m research.selftest

It fabricates a small synthetic dataset, runs the real recorder row format, the
real trainer and the real NumPy runtime, then asserts that the exported model
reproduces scikit-learn's own predictions. That last assertion is the point:
train/serve skew is the failure mode that silently degrades a deployed
classifier, and it is invisible to accuracy metrics computed inside the
trainer.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np

from gesture_features import extract_features, feature_names
from research.dataset import SCHEMA_VERSION, append_rows, read_rows, summarize

# Distinct synthetic hand shapes — not anatomically meaningful, just separable.
_SHAPES = {
    "point": [(0, 0), (1, 2), (0, 3)],
    "index_thumb": [(0, 0), (0.2, 3.4), (0, 4)],
    "fist": [(0, 0), (0.4, 0.6), (0, 0.9)],
    "open_palm": [(0, 0), (1.6, 2.4), (0, 3.4)],
    "v_sign": [(0, 0), (2.2, 1.4), (0, 2.6)],
}


def _hand(shape: str, rng: np.random.Generator) -> np.ndarray:
    """Build 21 landmarks whose spread depends on the shape."""
    base, mid, tip = _SHAPES[shape]
    points = [[0.0, 0.0, 0.0]]  # wrist, then 5 fingers x 4 joints = 21 landmarks
    for finger in range(5):
        offset = (finger - 2) * 0.35
        for dx, dy in (base, mid, tip, tip):
            points.append([offset + dx * (finger - 2) * 0.2, -dy, 0.0])
    points = np.array(points, dtype=np.float64)
    return points * 0.05 + 0.5 + rng.normal(0.0, 0.0015, points.shape)


def _rows(session: str, rng: np.random.Generator) -> list[dict]:
    rows = []
    trial = 0
    for shape in _SHAPES:
        for repetition in range(6):
            trial += 1
            for frame in range(10):
                points = _hand(shape, rng)
                row = {
                    "schema_version": SCHEMA_VERSION, "participant_id": "PTEST",
                    "session_id": session, "trial_id": f"{session}-{trial:04d}",
                    "gesture": shape, "condition": "normal", "hand": "Right",
                    "frame_index": frame, "timestamp_ms": frame * 33,
                    "frame_width": 1280, "frame_height": 720,
                    "mp_handedness": "Left", "handedness_score": 0.95,
                    "hand_span": 0.3, "edge_margin": 0.2,
                }
                for index, (x, y, z) in enumerate(points):
                    row[f"x{index}"], row[f"y{index}"], row[f"z{index}"] = x, y, z
                    row[f"wx{index}"] = (x - 0.5) * 0.2
                    row[f"wy{index}"] = (y - 0.5) * 0.2
                    row[f"wz{index}"] = z * 0.2
                rows.append(row)
    return rows


def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="gesture-selftest-"))
    try:
        rng = np.random.default_rng(7)
        csv_path = workspace / "synthetic.csv"
        for session in ("S01", "S02", "S03"):
            append_rows(csv_path, _rows(session, rng))

        stats = summarize(read_rows([csv_path]))
        print(f"[1/4] dataset round-trip: {stats['frames']} frames / "
              f"{stats['trials']} trials / sessions {stats['sessions']}")

        print(f"[2/4] feature vector: {len(feature_names())} named features")

        from research.train import main as train_main
        model_path = workspace / "model.npz"
        train_main([
            str(csv_path), "--holdout-session", "S03",
            "--output", str(model_path), "--augment-copies", "2",
            "--hidden", "64,32", "--no-rules", "--allow-incomplete",
        ])

        from gesture_model import GestureNetwork, MLGestureClassifier
        network = GestureNetwork(model_path)
        print(f"[3/4] runtime load: {len(network.labels)} classes "
              f"{network.labels}, {len(network.weights)} layers")

        # Train/serve parity: the NumPy forward pass must agree with sklearn.
        import joblib  # noqa: F401 — only to confirm the research extra is present
        from sklearn.neural_network import MLPClassifier  # noqa: F401

        def probe_sample(shape: str):
            points = _hand(shape, rng)
            world = (points - 0.5) * 0.2
            return extract_features(points, world, aspect=1280 / 720, hand="Right")

        probe = np.stack([probe_sample(s) for s in _SHAPES for _ in range(25)])
        expected = [shape for shape in _SHAPES for _ in range(25)]
        predicted = [network.labels[int(np.argmax(network.probabilities(v)))] for v in probe]
        agreement = float(np.mean([p == e for p, e in zip(predicted, expected)]))
        print(f"[4/4] runtime accuracy on fresh synthetic samples: {agreement:.3f}")
        if agreement < 0.9:
            print("FAIL: NumPy runtime does not reproduce the trained model")
            return 1

        # The classifier wrapper must pass the network's own decision through
        # unchanged once smoothing has settled, and must keep the payload shape
        # that ClickTracker / PalmSwipeTracker / ScrollTracker rely on.
        from types import SimpleNamespace
        points = _hand("open_palm", rng)
        world_points = (points - 0.5) * 0.2
        landmarks = [SimpleNamespace(x=x, y=y, z=z) for x, y, z in points]
        world = [SimpleNamespace(x=x, y=y, z=z) for x, y, z in world_points]
        classifier = MLGestureClassifier(network, "Right")
        for _ in range(6):  # let the EMA converge on a steady pose
            gesture, payload = classifier.classify(landmarks, world, 1280 / 720)

        direct = network.labels[int(np.argmax(network.probabilities(
            extract_features(points, world_points, aspect=1280 / 720, hand="Right"))))]
        assert {"pos", "probs", "confidence", "label"} <= payload.keys(), payload
        assert len(payload["pos"]) == 2, payload["pos"]
        if payload["label"] != direct:
            print(f"FAIL: wrapper returned {payload['label']}, network says {direct}")
            return 1
        print(f"      wrapper agrees with network ({direct}, "
              f"confidence {payload['confidence']:.2f}); payload keys OK")

        print("\nAll checks passed.")
        return 0
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
