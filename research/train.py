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
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from gesture_features import DEFAULT_CONFIG, FEATURE_VERSION, FeatureConfig, feature_names
from research.augment import AugmentConfig, expand
from research.dataset import (
    TRIAL_KEY, filter_rows, majority_by_trial, matrix, read_rows, row_points, summarize,
)
from research.migrate_gestures import RETIRED, partition_rows

DEFAULT_OUTPUT = Path("models/gesture_mlp.npz")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("datasets", nargs="+", type=Path)
    parser.add_argument("--replacement-dataset", action="append", type=Path, default=[],
                        help="Fresh point/index_thumb recordings; old point rows in "
                             "positional datasets are excluded when this is supplied")
    parser.add_argument("--holdout-session", action="append", default=[],
                        help="Session reserved for evaluation; repeat as needed")
    parser.add_argument("--holdout-trials-from-session", action="append", default=[],
                        help="Pilot evaluation: reserve one whole trial per gesture/hand/"
                             "condition in this session; requires at least two per group")
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
    parser.add_argument("--allow-incomplete", action="store_true",
                        help="Development only: allow a partial gesture set")
    return parser.parse_args(argv)


def _split(rows, holdout: set[str], trial_sessions: set[str] | None = None, seed=42):
    trial_sessions = trial_sessions or set()
    if holdout & trial_sessions:
        raise SystemExit("A session cannot have both whole-session and trial holdouts")
    missing = trial_sessions - {r["session_id"] for r in rows}
    if missing:
        raise SystemExit(f"Missing trial-holdout sessions: {sorted(missing)}")
    groups = defaultdict(set)
    for row in rows:
        if row["session_id"] in trial_sessions:
            group = tuple(row[k] for k in ("participant_id", "session_id", "gesture", "hand", "condition"))
            groups[group].add(tuple(row[k] for k in TRIAL_KEY))
    rng = random.Random(seed)
    held_trials = set()
    for group, trials in sorted(groups.items()):
        if len(trials) < 2:
            raise SystemExit(f"Need at least two trials for a trial holdout: {group}")
        held_trials.add(rng.choice(sorted(trials)))
    train, test = [], []
    for row in rows:
        is_test = row["session_id"] in holdout or tuple(row[k] for k in TRIAL_KEY) in held_trials
        (test if is_test else train).append(row)
    return train, test


def prepare_training_rows(datasets, replacement_datasets, min_score=0.0):
    """Keep fresh points separate from the old, ambiguous point definition."""
    rows = read_rows(datasets)
    removed = []
    if replacement_datasets:
        if {p.resolve() for p in datasets} & {p.resolve() for p in replacement_datasets}:
            raise SystemExit("Base and replacement datasets must be different files")
        rows, removed = partition_rows(rows)
        rows += read_rows(replacement_datasets)
    removed += [r for r in rows if r["gesture"] in RETIRED]
    rows = filter_rows([r for r in rows if r["gesture"] not in RETIRED],
                       min_score=min_score)
    return rows, removed


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

    rows, removed = prepare_training_rows(args.datasets, args.replacement_dataset,
                                          args.min_score)
    print(f"Gesture migration: excluded {len(removed)} old gesture frames")
    holdout = set(args.holdout_session)
    trial_sessions = set(args.holdout_trials_from_session)
    train_rows, test_rows = _split(rows, holdout, trial_sessions, args.seed)
    if trial_sessions:
        print("PILOT evaluation: whole trials held out within "
              f"{', '.join(sorted(trial_sessions))}; this does not test a new sitting.")
    if not train_rows:
        raise SystemExit("No training rows remain after holding out sessions")
    if holdout and not test_rows:
        raise SystemExit(f"No rows found for held-out session(s): {sorted(holdout)}")
    missing_sessions = holdout - {r["session_id"] for r in test_rows}
    if missing_sessions:
        raise SystemExit(f"Missing held-out sessions: {sorted(missing_sessions)}")
    expected = set(json.loads(Path(__file__).with_name("protocol.json").read_text())["gestures"])
    present = {r["gesture"] for r in train_rows}
    unknown = {r["gesture"] for r in rows} - expected
    if unknown:
        raise SystemExit(f"Unknown gesture labels: {sorted(unknown)}")
    if not args.allow_incomplete:
        missing = expected - present
        if missing:
            raise SystemExit(
                f"Missing training gestures: {sorted(missing)}. Record point and "
                "index_thumb with --gestures point index_thumb, then supply "
                "--replacement-dataset alongside the retained dataset. "
                "Model not overwritten."
            )
        if (holdout or trial_sessions) and (missing_test := expected - {r["gesture"] for r in test_rows}):
            raise SystemExit(
                f"Held-out data is missing gestures: {sorted(missing_test)}. "
                "Hold out both an old session (e.g. S03) and a new pointer/click "
                "session (e.g. G03) using repeated --holdout-session flags."
            )

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

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "feature_version": FEATURE_VERSION,
        "gesture_protocol_version": 3,
        "migration_excluded_frames": len(removed),
        "replacement_datasets": [str(p) for p in args.replacement_dataset],
        "hidden_layers": list(hidden),
        "augment_copies": args.augment_copies,
        "training_frames": int(len(train_rows)),
        "training_vectors": int(X_train.shape[0]),
        "training_sessions": sorted({r["session_id"] for r in train_rows}),
        "holdout_sessions": sorted(holdout),
        "trial_holdout_sessions": sorted(trial_sessions),
        "holdout_trial_keys": sorted({tuple(r[k] for k in TRIAL_KEY) for r in test_rows}),
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
