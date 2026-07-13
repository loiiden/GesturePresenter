from __future__ import annotations

import argparse
from pathlib import Path

import joblib
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from gestures import GestureClassifier
from research.dataset import majority_by_trial, matrix, read_rows
from research.features import landmarks_from_flat


def parse_args():
    parser = argparse.ArgumentParser(description="Compare learned and hard-coded classifiers")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("datasets", nargs="+", type=Path)
    parser.add_argument("--session", action="append", required=True,
                        help="Held-out session to evaluate; repeat as needed")
    parser.add_argument("--allow-training-overlap", action="store_true")
    return parser.parse_args()


def hard_coded_predictions(rows):
    predictions, previous_trial, classifier = [], None, None
    for row in rows:
        key = (row["participant_id"], row["session_id"], row["trial_id"])
        if key != previous_trial:
            classifier = GestureClassifier()  # reset hysteresis between trials
            previous_trial = key
        prediction, _ = classifier.classify(landmarks_from_flat(row))
        predictions.append(prediction.value)
    return predictions


def report(name: str, rows, predictions):
    frame_truth = [row["gesture"] for row in rows]
    trial_truth, trial_predictions = majority_by_trial(rows, predictions)
    labels = sorted(set(frame_truth) | set(predictions))
    print(f"\n=== {name} ===")
    print(f"Frame accuracy: {accuracy_score(frame_truth, predictions):.3f}")
    print(f"Trial accuracy: {accuracy_score(trial_truth, trial_predictions):.3f}")
    print("\nTrial-level classification report:")
    print(classification_report(trial_truth, trial_predictions, labels=labels, zero_division=0))
    print("Trial-level confusion matrix (rows=true, columns=predicted):")
    print("labels:", labels)
    print(confusion_matrix(trial_truth, trial_predictions, labels=labels))


def main():
    args = parse_args()
    artifact = joblib.load(args.model)
    requested = set(args.session)
    overlap = requested & set(artifact.get("training_sessions", []))
    if overlap and not args.allow_training_overlap:
        raise SystemExit(
            "Refusing data leakage: model trained on evaluated session(s): "
            + ", ".join(sorted(overlap))
        )
    rows = [row for row in read_rows(args.datasets) if row["session_id"] in requested]
    if not rows:
        raise SystemExit("No rows matched the requested held-out sessions")
    X, _ = matrix(rows)
    learned = artifact["estimator"].predict(X)
    rules = hard_coded_predictions(rows)
    print(f"Evaluation: {len(set(r['trial_id'] for r in rows))} trials / {len(rows)} frames")
    report(f"Learned {artifact['model_type']}", rows, learned)
    report("Hard-coded rules", rows, rules)


if __name__ == "__main__":
    main()
