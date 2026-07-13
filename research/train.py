from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from research.dataset import matrix, read_rows
from research.features import SCHEMA_VERSION, feature_names


def parse_args():
    parser = argparse.ArgumentParser(description="Train a local gesture classifier")
    parser.add_argument("datasets", nargs="+", type=Path)
    parser.add_argument("--model", choices=("tree", "forest", "logistic"), default="tree")
    parser.add_argument("--exclude-session", action="append", default=[],
                        help="Session reserved for later comparison; repeat as needed")
    parser.add_argument("--output", type=Path, default=Path("research/models/gesture.joblib"))
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def make_model(name: str, seed: int):
    if name == "tree":
        return DecisionTreeClassifier(max_depth=8, min_samples_leaf=5,
                                      class_weight="balanced", random_state=seed)
    if name == "forest":
        return RandomForestClassifier(n_estimators=250, min_samples_leaf=3,
                                      class_weight="balanced", n_jobs=-1, random_state=seed)
    return make_pipeline(StandardScaler(), LogisticRegression(
        max_iter=2000, class_weight="balanced", random_state=seed))


def main():
    args = parse_args()
    all_rows = read_rows(args.datasets)
    excluded = set(args.exclude_session)
    rows = [row for row in all_rows if row["session_id"] not in excluded]
    if not rows:
        raise SystemExit("No training rows remain after excluding sessions")
    sessions = sorted({row["session_id"] for row in rows})
    labels = sorted({row["gesture"] for row in rows})
    if len(labels) < 2:
        raise SystemExit("Training requires at least two gesture classes")
    X, y = matrix(rows)
    estimator = make_model(args.model, args.seed)
    estimator.fit(X, y)
    artifact = {
        "schema_version": SCHEMA_VERSION, "created_at": datetime.now(timezone.utc).isoformat(),
        "model_type": args.model, "estimator": estimator, "feature_names": feature_names(),
        "training_sessions": sessions, "excluded_sessions": sorted(excluded),
        "labels": labels, "training_frames": len(rows),
        "training_trials": len({row["trial_id"] for row in rows}),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, args.output)
    print(f"Saved {args.model} model to {args.output}")
    print(f"Training: {artifact['training_trials']} trials / {len(rows)} frames / {len(labels)} classes")
    print(f"Sessions used: {', '.join(sessions)}")
    if excluded:
        print(f"Reserved sessions: {', '.join(sorted(excluded))}")


if __name__ == "__main__":
    main()
