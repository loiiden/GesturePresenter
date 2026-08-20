"""Train the shipped gesture classifier and export it as a dependency-free .npz.

    uv run --extra research python -m research.train research/data/gestures.csv \
        --holdout-session S03 --output models/gesture_mlp.npz

The exported archive holds standardization statistics and dense layer weights,
nothing else. :mod:`gesture_model` reads it with NumPy alone, so the shipped
application never imports scikit-learn and is not exposed to the pickle
compatibility breakage that scikit-learn explicitly does not guarantee against.

Evaluation is **grouped by session**: a whole recording session is held out, so
the reported numbers describe performance on a session the model has never
seen, rather than on frames adjacent to its training data.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from gesture_features import DEFAULT_CONFIG, FEATURE_VERSION, FeatureConfig, feature_names
from research.augment import AugmentConfig, expand
from research.dataset import (
    filter_rows, majority_by_trial, matrix, read_rows, row_points, summarize,
)

DEFAULT_OUTPUT = Path("models/gesture_mlp.npz")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("datasets", nargs="+", type=Path)
    parser.add_argument("--holdout-session", action="append", default=[],
                        help="Session reserved for evaluation; repeat as needed")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--hidden", default="128,64",
                        help="Comma-separated hidden layer sizes")
    parser.add_argument("--augment-copies", type=int, default=6,
                        help="Augmented copies per training frame; 0 disables")
    parser.add_argument("--no-world", action="store_true",
                        help="Ablation: drop the metric world-landmark block")
    parser.add_argument("--baselines", action="store_true",
                        help="Also fit tree/forest/logistic for comparison")
    parser.add_argument("--no-rules", action="store_true",
                        help="Skip the hard-coded rule baseline (used by selftest, "
                             "where synthetic shapes make the comparison meaningless)")
    parser.add_argument("--min-score", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args(argv)


def _split(rows, holdout: set[str]):
    train = [row for row in rows if row["session_id"] not in holdout]
    test = [row for row in rows if row["session_id"] in holdout]
    return train, test


def _report(name: str, rows, predictions) -> dict:
    from sklearn.metrics import accuracy_score, classification_report, f1_score

    frame_truth = [row["gesture"] for row in rows]
    trial_truth, trial_predictions = majority_by_trial(rows, predictions)
    frame_accuracy = accuracy_score(frame_truth, predictions)
    trial_accuracy = accuracy_score(trial_truth, trial_predictions)
    macro_f1 = f1_score(trial_truth, trial_predictions, average="macro", zero_division=0)
    print(f"\n=== {name} ===")
    print(f"Frame accuracy: {frame_accuracy:.3f}   "
          f"Trial accuracy: {trial_accuracy:.3f}   Trial macro-F1: {macro_f1:.3f}")
    print(classification_report(trial_truth, trial_predictions, zero_division=0))
    return {"frame_accuracy": float(frame_accuracy),
            "trial_accuracy": float(trial_accuracy), "trial_macro_f1": float(macro_f1)}


def _rule_predictions(rows) -> list[str]:
    """The hard-coded classifier from main, as the baseline to beat."""
    from types import SimpleNamespace

    from gestures import GestureClassifier
    from research.dataset import IMAGE_COLUMNS

    predictions, previous, classifier = [], None, None
    for row in rows:
        key = (row["participant_id"], row["session_id"], row["trial_id"])
        if key != previous:
            classifier = GestureClassifier()  # reset hysteresis between trials
            previous = key
        landmarks = [
            SimpleNamespace(x=float(row[f"x{i}"]), y=float(row[f"y{i}"]),
                            z=float(row[f"z{i}"]))
            for i in range(21)
        ]
        prediction, _ = classifier.classify(landmarks)
        predictions.append(prediction.value)
    return predictions


def contact_gates(rows, margin: float = 1.20, release: float = 1.55) -> dict:
    """Calibrate per-class fingertip-contact limits from the operator's own data.

    ``pinch`` means the thumb and index finger actually touch. A classifier does
    not learn that definition — it learns whatever separates the training
    classes, and the recorded data contains a wide unlabelled gap between a
    closed pinch and an open point. Inside that gap the learned boundary is
    arbitrary extrapolation, yet it is exactly the region a hand passes through
    while a thumb approaches a finger, so it decides whether a click fires early.

    The gate closes that gap with a measurement instead of a guess: a predicted
    pinch is only accepted when the fingertips really are close. Limits are
    derived per operator because hand proportions differ; ``margin`` is applied
    over the widest genuine example so normal variation is never rejected, and
    ``release`` gives hysteresis so a held pinch does not flicker.
    """
    from gesture_features import CONTACT_PAIRS, contact_distance

    gates = {}
    for label in CONTACT_PAIRS:
        by_trial: dict[str, list[float]] = {}
        for row in rows:
            if row["gesture"] == label:
                by_trial.setdefault(row["trial_id"], []).append(
                    contact_distance(row_points(row)[0], label)
                )
        if not by_trial:
            continue

        # Outlier *trials* are removed before calibrating, not outlier frames. A
        # trial where the fingers never actually met contributes ~45 consistent
        # frames, which survives any per-frame percentile and would widen the
        # gate permanently. Judging trials by their median and cutting at
        # median + 4 MAD isolates that case while keeping normal variation.
        medians = np.array([float(np.median(v)) for v in by_trial.values()])
        centre = float(np.median(medians))
        mad = float(np.median(np.abs(medians - centre))) * 1.4826
        limit = centre + 4 * mad if mad > 0 else centre * 1.5
        kept, rejected = [], []
        for trial_id, values in by_trial.items():
            if float(np.median(values)) <= limit:
                kept.extend(values)
            else:
                rejected.append((trial_id, round(float(np.median(values)), 3)))

        widest = float(np.percentile(kept, 99.0))
        gates[label] = {
            "enter": round(widest * margin, 4),
            "release": round(widest * release, 4),
            "observed_p99": round(widest, 4),
            "observed_median": round(float(np.median(kept)), 4),
            "samples": len(kept),
            "excluded_trials": rejected,
        }
    return gates


def export_npz(path: Path, pipeline, labels, config: FeatureConfig, metadata: dict) -> None:
    """Flatten a StandardScaler + MLPClassifier pipeline into plain arrays."""
    scaler = pipeline.named_steps["standardscaler"]
    network = pipeline.named_steps["mlpclassifier"]
    arrays = {
        "mean": scaler.mean_.astype(np.float32),
        "scale": scaler.scale_.astype(np.float32),
        "labels": np.array(labels, dtype=object),
        "layer_count": np.array(len(network.coefs_)),
        "feature_version": np.array(FEATURE_VERSION),
        "metadata": np.array(json.dumps(metadata)),
        "feature_config": np.array(json.dumps(config.as_dict())),
    }
    for index, (weight, bias) in enumerate(zip(network.coefs_, network.intercepts_)):
        arrays[f"w{index}"] = weight.astype(np.float32)
        arrays[f"b{index}"] = bias.astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)


def main(argv=None) -> None:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeClassifier

    args = parse_args(argv)
    config = FeatureConfig(world=not args.no_world)

    rows = filter_rows(read_rows(args.datasets), min_score=args.min_score)
    holdout = set(args.holdout_session)
    train_rows, test_rows = _split(rows, holdout)
    if not train_rows:
        raise SystemExit("No training rows remain after holding out sessions")
    if holdout and not test_rows:
        raise SystemExit(f"No rows found for held-out session(s): {sorted(holdout)}")

    stats = summarize(rows)
    print(f"Dataset: {stats['frames']} frames / {stats['trials']} trials "
          f"/ sessions {', '.join(stats['sessions'])}")
    print(f"Train: {len(train_rows)} frames   Held out: {len(test_rows)} frames "
          f"({', '.join(sorted(holdout)) or 'none'})")

    labels_present = sorted({row["gesture"] for row in train_rows})
    if len(labels_present) < 2:
        raise SystemExit("Training requires at least two gesture classes")

    train_labels = [row["gesture"] for row in train_rows]
    train_groups = ["|".join((r["participant_id"], r["session_id"], r["trial_id"]))
                    for r in train_rows]
    if args.augment_copies > 0:
        samples = [row_points(row) for row in train_rows]
        X_train, y_train, _ = expand(
            samples, train_labels, train_groups,
            AugmentConfig(copies=args.augment_copies, seed=args.seed), config,
        )
        print(f"Augmented training set: {len(X_train)} vectors "
              f"({args.augment_copies} copies per frame)")
    else:
        X_train, y_train, _ = matrix(train_rows, config)

    hidden = tuple(int(size) for size in args.hidden.split(",") if size.strip())
    pipeline = make_pipeline(
        StandardScaler(),
        MLPClassifier(hidden_layer_sizes=hidden, activation="relu", alpha=1e-4,
                      batch_size=256, learning_rate_init=1e-3, max_iter=400,
                      early_stopping=True, n_iter_no_change=15,
                      random_state=args.seed),
    )
    print(f"Fitting MLP{hidden} on {X_train.shape[0]}x{X_train.shape[1]}…")
    pipeline.fit(X_train, y_train)

    results = {}
    if test_rows:
        X_test, y_test, _ = matrix(test_rows, config)
        results["mlp"] = _report("MLP (shipped)", test_rows, pipeline.predict(X_test))
        if not args.no_rules:
            results["rules"] = _report("Hard-coded rules (baseline from main)",
                                       test_rows, _rule_predictions(test_rows))
        if args.baselines:
            for name, estimator in (
                ("tree", DecisionTreeClassifier(max_depth=10, min_samples_leaf=5,
                                                class_weight="balanced",
                                                random_state=args.seed)),
                ("forest", RandomForestClassifier(n_estimators=300, min_samples_leaf=2,
                                                  class_weight="balanced", n_jobs=-1,
                                                  random_state=args.seed)),
                ("logistic", make_pipeline(StandardScaler(),
                                           LogisticRegression(max_iter=2000,
                                                              class_weight="balanced",
                                                              random_state=args.seed))),
            ):
                estimator.fit(X_train, y_train)
                results[name] = _report(name, test_rows, estimator.predict(X_test))

    gates = contact_gates(train_rows)
    for label, gate in gates.items():
        print(f"Contact gate {label}: enter <= {gate['enter']}, release > {gate['release']} "
              f"(p99 of genuine examples {gate['observed_p99']}, median {gate['observed_median']})")
        for trial_id, value in gate["excluded_trials"]:
            print(f"  ! trial {trial_id} excluded from calibration: median contact "
                  f"distance {value} — the fingers were probably never touching")

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "feature_version": FEATURE_VERSION,
        "contact_gates": gates,
        "hidden_layers": list(hidden),
        "augment_copies": args.augment_copies,
        "training_frames": int(len(train_rows)),
        "training_vectors": int(X_train.shape[0]),
        "training_sessions": sorted({r["session_id"] for r in train_rows}),
        "holdout_sessions": sorted(holdout),
        "labels": sorted(set(y_train.tolist())),
        "results": results,
        "dataset": stats,
    }
    export_npz(args.output, pipeline, pipeline.classes_.tolist(), config, metadata)
    size_kb = args.output.stat().st_size / 1024
    print(f"\nExported {args.output} ({size_kb:.0f} KB, "
          f"{len(feature_names(config))} features, {len(pipeline.classes_)} classes)")


if __name__ == "__main__":
    main()
