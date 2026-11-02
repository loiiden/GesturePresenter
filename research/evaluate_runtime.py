"""Replay recorded holdout trials through the shipped classifier and click tracker.

No camera or mouse actions are used. Trial boundaries reset smoothing because
recordings do not include continuous transitions between commanded poses.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

from sklearn.metrics import accuracy_score, classification_report

from gesture_model import GestureNetwork, MLGestureClassifier
from gestures import ClickTracker, Gesture
from research.dataset import TRIAL_KEY, read_rows


def evaluate(model: Path, datasets: list[Path]) -> dict:
    network = GestureNetwork(model)
    held_keys = {tuple(k) for k in network.metadata["holdout_trial_keys"]}
    trials = defaultdict(list)
    for row in read_rows(datasets):
        key = tuple(row[k] for k in TRIAL_KEY)
        if key in held_keys:
            trials[key].append(row)
    if set(trials) != held_keys:
        raise ValueError("Evaluation inputs do not contain every model holdout trial")
    truth, predictions, trial_truth, trial_predictions = [], [], [], []
    details = []
    for key, rows in sorted(trials.items()):
        rows.sort(key=lambda r: int(r["frame_index"]))
        classifier = MLGestureClassifier(network, rows[0]["hand"])
        click = ClickTracker()
        labels, events = [], []
        for row in rows:
            image = [SimpleNamespace(**{a: float(row[f"{a}{i}"]) for a in "xyz"})
                     for i in range(21)]
            world = [SimpleNamespace(**{a: float(row[f"w{a}{i}"]) for a in "xyz"})
                     for i in range(21)]
            gesture, _ = classifier.classify(image, world,
                                            float(row["frame_width"])/float(row["frame_height"]))
            labels.append(gesture.value)
            events.extend(click.update(gesture == Gesture.INDEX_THUMB))
        # Simulate a deliberate pose release; actual hand loss resets the tracker.
        events.extend(click.update(False))
        events.extend(click.update(False))
        expected = rows[0]["gesture"]
        majority = Counter(labels).most_common(1)[0][0]
        truth.extend([expected] * len(rows))
        predictions.extend(labels)
        trial_truth.append(expected)
        trial_predictions.append(majority)
        details.append({
            "key": key, "gesture": expected, "hand": rows[0]["hand"],
            "condition": rows[0]["condition"], "frames": len(rows),
            "prediction": majority, "frame_predictions": dict(Counter(labels)),
            "clicks_with_simulated_release": len(events),
        })
    report = {
        "model": str(model), "frames": len(truth), "trials": len(details),
        "whole_holdout_sessions": network.metadata["holdout_sessions"],
        "within_session_trial_holdouts": network.metadata.get("trial_holdout_sessions", []),
        "frame_accuracy": float(accuracy_score(truth, predictions)),
        "trial_accuracy": float(accuracy_score(trial_truth, trial_predictions)),
        "per_class": classification_report(trial_truth, trial_predictions,
                                           output_dict=True, zero_division=0),
        "false_click_trials": [t for t in details if t["gesture"] != "index_thumb"
                               and t["clicks_with_simulated_release"]],
        "click_count_failures": [t for t in details if t["gesture"] == "index_thumb"
                                 and t["clicks_with_simulated_release"] != 1],
        "trial_details": details,
        "limits": "Recorded static poses with resets between trials and simulated releases; "
                  "not a live camera or continuous-transition test.",
    }
    print(classification_report(trial_truth, trial_predictions, zero_division=0))
    print(f"Runtime: {report['frame_accuracy']:.3%} frames, "
          f"{report['trial_accuracy']:.3%} trials")
    print(f"False-click trials: {len(report['false_click_trials'])}; "
          f"click-count failures: {len(report['click_count_failures'])}")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("model", type=Path)
    parser.add_argument("datasets", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = evaluate(args.model, args.datasets)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
