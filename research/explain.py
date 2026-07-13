"""Interactive, action-free XAI sandbox for the gesture study.

The sandbox deliberately stops at classification: it never imports ``actions``
and never sends mouse or keyboard events.  It can classify a live hand or replay
the stored landmark-only test session so a presentation remains reproducible.
"""

from __future__ import annotations

import argparse
import re
import time
import warnings
from collections import Counter, OrderedDict
from dataclasses import dataclass
from pathlib import Path

import cv2
import joblib
import numpy as np
from sklearn.metrics import accuracy_score, f1_score

from gestures import (
    GestureClassifier,
    INDEX_TIP,
    MIDDLE_TIP,
    THUMB_TIP,
    _extended_fingers,
    _pinch_ratio,
)
from research.dataset import read_rows
from research.features import (
    SCHEMA_VERSION,
    extract_features,
    feature_names,
    landmarks_from_flat,
)


WINDOW = "Gesture Presenter - XAI Sandbox"
WIDTH, HEIGHT = 1600, 900
MODEL_PATH = Path(__file__).resolve().parent.parent / "hand_landmarker.task"
HAND_CONNECTIONS = (
    (0, 1), (0, 5), (0, 9), (0, 13), (0, 17),
    (5, 9), (9, 13), (13, 17),
    (1, 2), (2, 3), (3, 4),
    (5, 6), (6, 7), (7, 8),
    (9, 10), (10, 11), (11, 12),
    (13, 14), (14, 15), (15, 16),
    (17, 18), (18, 19), (19, 20),
)
BG = (12, 12, 12)
PANEL = (24, 24, 24)
PANEL_2 = (34, 34, 34)
WHITE = (242, 242, 242)
MUTED = (158, 158, 158)
GREEN = (116, 222, 154)
RED = (112, 112, 240)
AMBER = (85, 198, 245)
BLUE = (235, 180, 90)

FILTERS = (
    "all trials",
    "rules wrong / model right",
    "rules-model disagreement",
    "selected model errors",
)

LANDMARK_NAMES = (
    "wrist", "thumb cmc", "thumb mcp", "thumb ip", "thumb tip",
    "index mcp", "index pip", "index dip", "index tip",
    "middle mcp", "middle pip", "middle dip", "middle tip",
    "ring mcp", "ring pip", "ring dip", "ring tip",
    "pinky mcp", "pinky pip", "pinky dip", "pinky tip",
)

ENGINEERED_NAMES = {
    "thumb_index_distance": "thumb-index distance",
    "thumb_middle_distance": "thumb-middle distance",
    "index_middle_distance": "index-middle distance",
    "thumb_index_mcp_distance": "thumb-index MCP distance",
    "thumb_dx": "thumb horizontal offset",
    "thumb_dy": "thumb vertical offset",
    "index_angle": "index joint angle",
    "middle_angle": "middle joint angle",
    "ring_angle": "ring joint angle",
    "pinky_angle": "pinky joint angle",
    "index_tip_radius": "index tip radius",
    "middle_tip_radius": "middle tip radius",
    "ring_tip_radius": "ring tip radius",
    "pinky_tip_radius": "pinky tip radius",
}


@dataclass
class ModelBundle:
    name: str
    estimator: object
    features: list[str]
    training_sessions: set[str]


@dataclass
class Prediction:
    label: str
    confidence: float


@dataclass
class Trial:
    key: tuple[str, str, str]
    indices: list[int]
    truth: str
    rule_label: str
    model_labels: dict[str, str]


@dataclass
class ReplayData:
    rows: list[dict]
    landmarks: list[list]
    matrix: np.ndarray
    rules: list[Prediction]
    rule_evidence: list[list[str]]
    model_predictions: dict[str, list[Prediction]]
    trials: list[Trial]
    metrics: dict[str, tuple[float, float]]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Live and replay XAI sandbox; never executes presentation actions"
    )
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    parser.add_argument("--dataset", type=Path,
                        default=Path("research/data/landmarks.csv"))
    parser.add_argument("--session", default="S03",
                        help="Held-out session used by replay mode (default: S03)")
    parser.add_argument("--models-dir", type=Path,
                        default=Path("research/models"))
    parser.add_argument("--model", action="append", type=Path, default=[],
                        help="Model artifact; repeat to override automatic discovery")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--allow-training-overlap", action="store_true")
    parser.add_argument("--headless-check", action="store_true",
                        help="Validate artifacts/data and print a demo explanation")
    return parser.parse_args()


def pretty_feature(name: str) -> str:
    if name in ENGINEERED_NAMES:
        return ENGINEERED_NAMES[name]
    match = re.fullmatch(r"lm(\d+)_(x|y|z)", name)
    if match:
        landmark = LANDMARK_NAMES[int(match.group(1))]
        return f"{landmark} {match.group(2)}"
    return name.replace("_", " ")


def load_models(args) -> list[ModelBundle]:
    if args.model:
        paths = args.model
    else:
        paths = [args.models_dir / f"{name}.joblib"
                 for name in ("tree", "forest", "logistic")]
        paths = [path for path in paths if path.exists()]
    if not paths:
        raise SystemExit("No model artifacts found. Train models first; see research/README.md")

    expected_features = feature_names()
    bundles = []
    for path in paths:
        artifact = joblib.load(path)
        if artifact.get("schema_version") != SCHEMA_VERSION:
            raise SystemExit(f"Incompatible feature schema in {path}")
        if artifact.get("feature_names") != expected_features:
            raise SystemExit(f"Feature order in {path} does not match current code")
        name = str(artifact.get("model_type", path.stem))
        bundles.append(ModelBundle(
            name=name,
            estimator=artifact["estimator"],
            features=artifact["feature_names"],
            training_sessions=set(artifact.get("training_sessions", [])),
        ))
    return bundles


def model_predictions(bundle: ModelBundle, matrix: np.ndarray) -> list[Prediction]:
    # The saved logistic artifact can make older BLAS/scikit-learn combinations
    # emit overflow warnings even though its final logits/probabilities are finite
    # (the report documents this). Keep the demo clean, but never accept bad output.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        labels = bundle.estimator.predict(matrix)
        probabilities = bundle.estimator.predict_proba(matrix)
    if not np.isfinite(probabilities).all():
        raise RuntimeError(f"{bundle.name} produced non-finite probabilities")
    return [Prediction(str(label), float(np.max(probs)))
            for label, probs in zip(labels, probabilities)]


def rule_snapshot(classifier: GestureClassifier, landmarks) -> tuple[Prediction, list[str]]:
    threshold = (classifier.PINCH_OPEN if classifier._index_pinched
                 else classifier.PINCH_CLOSE)
    index_ratio = _pinch_ratio(landmarks, THUMB_TIP, INDEX_TIP)
    middle_ratio = _pinch_ratio(landmarks, THUMB_TIP, MIDDLE_TIP)
    finger_gap = _pinch_ratio(landmarks, INDEX_TIP, MIDDLE_TIP)
    extended = _extended_fingers(landmarks)
    gesture, _ = classifier.classify(landmarks)
    evidence = [
        f"thumb-index {index_ratio:.3f}  (pinch threshold {threshold:.2f})",
        f"thumb-middle {middle_ratio:.3f}  |  finger gap {finger_gap:.3f}",
        "extended I/M/R/P  " + "/".join("yes" if value else "no"
                                         for value in extended),
    ]
    return Prediction(gesture.value, 1.0), evidence


def majority(values) -> str:
    return Counter(str(value) for value in values).most_common(1)[0][0]


def prepare_replay(args, bundles: list[ModelBundle]) -> ReplayData:
    overlaps = [bundle.name for bundle in bundles if args.session in bundle.training_sessions]
    if overlaps and not args.allow_training_overlap:
        raise SystemExit(
            f"Refusing data leakage: {args.session} trained models: {', '.join(overlaps)}"
        )

    rows = [row for row in read_rows([args.dataset])
            if row["session_id"] == args.session]
    if not rows:
        raise SystemExit(f"No rows from session {args.session} in {args.dataset}")
    landmarks = [landmarks_from_flat(row) for row in rows]
    matrix = np.asarray([extract_features(lms) for lms in landmarks], dtype=float)

    rule_results = []
    rule_evidence = []
    previous_key = None
    classifier = None
    for row, lms in zip(rows, landmarks):
        key = (row["participant_id"], row["session_id"], row["trial_id"])
        if key != previous_key:
            classifier = GestureClassifier()
            previous_key = key
        prediction, evidence = rule_snapshot(classifier, lms)
        rule_results.append(prediction)
        rule_evidence.append(evidence)

    by_model = {bundle.name: model_predictions(bundle, matrix) for bundle in bundles}
    grouped = OrderedDict()
    for index, row in enumerate(rows):
        key = (row["participant_id"], row["session_id"], row["trial_id"])
        grouped.setdefault(key, []).append(index)

    trials = []
    for key, indices in grouped.items():
        truth = majority(rows[index]["gesture"] for index in indices)
        trials.append(Trial(
            key=key,
            indices=indices,
            truth=truth,
            rule_label=majority(rule_results[index].label for index in indices),
            model_labels={
                name: majority(predictions[index].label for index in indices)
                for name, predictions in by_model.items()
            },
        ))

    truths = [trial.truth for trial in trials]
    metrics = {
        "rules": (
            accuracy_score(truths, [trial.rule_label for trial in trials]),
            f1_score(truths, [trial.rule_label for trial in trials],
                     average="macro", zero_division=0),
        )
    }
    for bundle in bundles:
        predicted = [trial.model_labels[bundle.name] for trial in trials]
        metrics[bundle.name] = (
            accuracy_score(truths, predicted),
            f1_score(truths, predicted, average="macro", zero_division=0),
        )

    return ReplayData(rows, landmarks, matrix, rule_results, rule_evidence,
                      by_model, trials, metrics)


def model_explanation(bundle: ModelBundle, vector: np.ndarray,
                      prediction: Prediction) -> tuple[str, list[str]]:
    x = np.asarray(vector, dtype=float).reshape(1, -1)
    estimator = bundle.estimator

    if bundle.name == "tree":
        nodes = estimator.decision_path(x).indices
        lines = []
        boundaries = []
        for node in nodes[:-1]:
            feature_index = int(estimator.tree_.feature[node])
            threshold = float(estimator.tree_.threshold[node])
            value = float(x[0, feature_index])
            went_left = value <= threshold
            operator = "<=" if went_left else ">"
            lines.append(
                f"{pretty_feature(bundle.features[feature_index])}: "
                f"{value:.3f} {operator} {threshold:.3f}"
            )
            boundaries.append((abs(value - threshold), feature_index, threshold, went_left))
        shown = lines[-5:]
        if boundaries:
            _, feature_index, threshold, went_left = min(boundaries)
            direction = "increase above" if went_left else "decrease to"
            shown.append(
                f"Nearest split (may not change class): "
                f"{pretty_feature(bundle.features[feature_index])} "
                f"must {direction} {threshold:.3f}"
            )
        return "Last steps of the exact decision path", shown

    if bundle.name == "logistic":
        scaler = estimator.named_steps["standardscaler"]
        logistic = estimator.named_steps["logisticregression"]
        scaled = scaler.transform(x)[0]
        class_index = list(logistic.classes_).index(prediction.label)
        contributions = scaled * logistic.coef_[class_index]
        order = np.argsort(np.abs(contributions))[::-1][:6]
        lines = [
            f"{pretty_feature(bundle.features[index])}: {contributions[index]:+.2f} logit"
            for index in order
        ]
        return "Local contributions to predicted class", lines

    importances = np.asarray(estimator.feature_importances_)
    order = np.argsort(importances)[::-1][:6]
    lines = [
        f"{pretty_feature(bundle.features[index])}: {importances[index] * 100:.1f}%"
        for index in order
    ]
    return "Global forest importance (not a local cause)", lines


def global_importance(bundle: ModelBundle) -> list[tuple[str, float]]:
    estimator = bundle.estimator
    if bundle.name == "logistic":
        logistic = estimator.named_steps["logisticregression"]
        values = np.mean(np.abs(logistic.coef_), axis=0)
    else:
        values = np.asarray(estimator.feature_importances_)
    maximum = float(np.max(values)) or 1.0
    order = np.argsort(values)[::-1][:9]
    return [(pretty_feature(bundle.features[index]), float(values[index] / maximum))
            for index in order]


def filtered_trials(data: ReplayData, selected: str, filter_name: str) -> list[Trial]:
    if filter_name == FILTERS[0]:
        return data.trials
    if filter_name == FILTERS[1]:
        result = [trial for trial in data.trials
                  if trial.rule_label != trial.truth
                  and trial.model_labels[selected] == trial.truth]
    elif filter_name == FILTERS[2]:
        result = [trial for trial in data.trials
                  if trial.rule_label != trial.model_labels[selected]]
    else:
        result = [trial for trial in data.trials
                  if trial.model_labels[selected] != trial.truth]
    return result or data.trials


def text(image, value, position, scale=0.55, color=WHITE, thickness=1):
    cv2.putText(image, str(value), position, cv2.FONT_HERSHEY_SIMPLEX,
                scale, color, thickness, cv2.LINE_AA)


def box(image, x1, y1, x2, y2, color=PANEL, radius=0, border=None):
    del radius  # OpenCV has no native rounded rectangle; keep the call sites semantic.
    cv2.rectangle(image, (x1, y1), (x2, y2), color, -1)
    if border is not None:
        cv2.rectangle(image, (x1, y1), (x2, y2), border, 2)


def fit_camera(frame: np.ndarray, rect: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = rect
    width, height = x2 - x1, y2 - y1
    scale = min(width / frame.shape[1], height / frame.shape[0])
    resized = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    result = np.full((height, width, 3), 20, dtype=np.uint8)
    ox = (width - resized.shape[1]) // 2
    oy = (height - resized.shape[0]) // 2
    result[oy:oy + resized.shape[0], ox:ox + resized.shape[1]] = resized
    return result


def draw_skeleton(image: np.ndarray, landmarks, rect, live_frame=None):
    x1, y1, x2, y2 = rect
    if live_frame is not None:
        fitted = fit_camera(live_frame, rect)
        image[y1:y2, x1:x2] = fitted
        source_ratio = live_frame.shape[1] / live_frame.shape[0]
        target_ratio = (x2 - x1) / (y2 - y1)
        if source_ratio > target_ratio:
            drawn_w = x2 - x1
            drawn_h = int(drawn_w / source_ratio)
            ox, oy = x1, y1 + ((y2 - y1) - drawn_h) // 2
        else:
            drawn_h = y2 - y1
            drawn_w = int(drawn_h * source_ratio)
            ox, oy = x1 + ((x2 - x1) - drawn_w) // 2, y1
        points = [(int(ox + lm.x * drawn_w), int(oy + lm.y * drawn_h))
                  for lm in landmarks]
    else:
        box(image, x1, y1, x2, y2, PANEL)
        xs = np.asarray([lm.x for lm in landmarks])
        ys = np.asarray([lm.y for lm in landmarks])
        center_x, center_y = float(np.mean(xs)), float(np.mean(ys))
        span = max(float(np.ptp(xs)), float(np.ptp(ys)), 0.18) * 1.35
        side = min(x2 - x1, y2 - y1) * 0.82
        points = [
            (int((x1 + x2) / 2 + (lm.x - center_x) / span * side),
             int((y1 + y2) / 2 + (lm.y - center_y) / span * side))
            for lm in landmarks
        ]

    for a, b in HAND_CONNECTIONS:
        cv2.line(image, points[a], points[b], (210, 210, 210), 3, cv2.LINE_AA)
    for index, point in enumerate(points):
        is_tip = index in (4, 8, 12, 16, 20)
        cv2.circle(image, point, 9 if is_tip else 5,
                   AMBER if is_tip else WHITE, -1, cv2.LINE_AA)


def prediction_card(image, y, name, prediction, truth, selected, number=None):
    x1, x2 = 950, 1570
    correct = truth is not None and prediction.label == truth
    border = WHITE if selected else (52, 52, 52)
    box(image, x1, y, x2, y + 65, PANEL_2, border=border)
    prefix = f"{number}  " if number else ""
    text(image, prefix + name.upper(), (x1 + 18, y + 25), 0.48, MUTED, 1)
    color = GREEN if correct else (RED if truth is not None else WHITE)
    text(image, prediction.label.replace("_", " "), (x1 + 18, y + 52),
         0.68, color, 2)
    if name != "rules":
        text(image, f"{prediction.confidence * 100:.1f}%", (x2 - 92, y + 44),
             0.55, color, 1)


def draw_explanation(image, bundle, vector, prediction, rule_evidence):
    title, lines = model_explanation(bundle, vector, prediction)
    text(image, "WHY THIS PREDICTION", (950, 420), 0.48, MUTED, 1)
    text(image, title, (950, 450), 0.55, WHITE, 1)
    y = 484
    for line in lines[:6]:
        text(image, line, (968, y), 0.47, WHITE, 1)
        y += 28

    text(image, "RULE EVIDENCE", (950, 672), 0.48, MUTED, 1)
    for index, line in enumerate(rule_evidence[:3]):
        text(image, line, (968, 704 + index * 27), 0.47, WHITE, 1)


def base_canvas(mode, subtitle):
    image = np.full((HEIGHT, WIDTH, 3), BG, dtype=np.uint8)
    text(image, "GESTURE PRESENTER", (30, 34), 0.48, MUTED, 1)
    text(image, "XAI SANDBOX", (30, 67), 0.92, WHITE, 2)
    text(image, mode.upper(), (950, 38), 0.50, GREEN, 1)
    text(image, subtitle, (950, 66), 0.48, MUTED, 1)
    return image


def draw_dashboard(landmarks, bundles, predictions, rules, evidence, selected_index,
                   truth=None, mode="replay", subtitle="", live_frame=None,
                   footer=""):
    image = base_canvas(mode, subtitle)
    selected = bundles[selected_index]
    selected_prediction = predictions[selected.name]
    draw_skeleton(image, landmarks, (30, 95, 910, 770), live_frame)

    if truth is not None:
        text(image, "EXPECTED", (58, 130), 0.46, MUTED, 1)
        text(image, truth.replace("_", " "), (58, 164), 0.75, WHITE, 2)
    labels = [rules.label] + [predictions[bundle.name].label for bundle in bundles]
    if len(set(labels)) > 1:
        box(image, 48, 704, 892, 750, (34, 34, 34), border=AMBER)
        text(image, "DISAGREEMENT — same landmarks, different decisions",
             (70, 734), 0.60, AMBER, 2)

    prediction_card(image, 95, "rules", rules, truth, False)
    for index, bundle in enumerate(bundles):
        prediction_card(image, 170 + index * 75, bundle.name,
                        predictions[bundle.name], truth, index == selected_index,
                        number=index + 1)
    draw_explanation(image, selected, np.asarray(
        [extract_features(landmarks)], dtype=float)[0], selected_prediction, evidence)

    text(image, footer, (30, 813), 0.45, MUTED, 1)
    text(image, "SPACE pause  A/D trial  J/K frame  F filter  M model  G overview  Q quit",
         (30, 856), 0.51, WHITE, 1)
    text(image, "Research only · classification stops here · no OS actions",
         (950, 856), 0.44, GREEN, 1)
    return image


def bar(image, label, value, x, y, width, color=WHITE, suffix=None):
    text(image, label, (x, y), 0.50, WHITE, 1)
    cv2.rectangle(image, (x, y + 12), (x + width, y + 26), (48, 48, 48), -1)
    cv2.rectangle(image, (x, y + 12), (x + int(width * max(0, min(1, value))), y + 26),
                  color, -1)
    if suffix:
        text(image, suffix, (x + width + 12, y + 25), 0.46, color, 1)


def draw_overview(bundles, selected_index, metrics=None, subtitle=""):
    image = base_canvas("model overview", subtitle)
    selected = bundles[selected_index]
    text(image, "HELD-OUT TRIAL RESULTS", (45, 125), 0.55, MUTED, 1)
    if metrics:
        y = 165
        for name in ["rules"] + [bundle.name for bundle in bundles]:
            accuracy, macro_f1 = metrics[name]
            color = GREEN if name == selected.name else WHITE
            text(image, name.upper(), (45, y), 0.54, color, 2 if name == selected.name else 1)
            bar(image, "accuracy", accuracy, 190, y - 15, 350, color,
                f"{accuracy * 100:.1f}%")
            bar(image, "macro F1", macro_f1, 650, y - 15, 350, color,
                f"{macro_f1:.2f}")
            y += 88
    else:
        text(image, "Metrics require replay mode.", (45, 170), 0.60, WHITE, 1)

    text(image, f"{selected.name.upper()} — GLOBAL FEATURE VIEW", (1070, 125),
         0.55, MUTED, 1)
    y = 165
    for name, value in global_importance(selected):
        bar(image, name, value, 1070, y, 360, BLUE)
        y += 62

    box(image, 45, 610, 1010, 790, PANEL)
    text(image, "HOW TO READ THIS", (70, 646), 0.50, MUTED, 1)
    notes = (
        "Tree path = exact local threshold decisions for one frame.",
        "Logistic bars = local contributions to the predicted class score.",
        "Forest bars here = global importance, not proof of a local cause.",
        "Confidence is model output, not calibrated certainty.",
        "This pilot covers one participant and static classification only.",
    )
    for index, note in enumerate(notes):
        text(image, note, (70, 680 + index * 25), 0.47, WHITE, 1)

    text(image, "1/2/3 or M model  G return to sandbox  Q quit", (45, 856),
         0.53, WHITE, 1)
    return image


def print_headless_summary(data: ReplayData, bundles: list[ModelBundle]):
    print(f"XAI sandbox validation: {len(data.trials)} trials / {len(data.rows)} frames")
    for name, (accuracy, macro_f1) in data.metrics.items():
        print(f"{name:10s} trial accuracy={accuracy:.3f} macro-F1={macro_f1:.3f}")
    selected = next((bundle for bundle in bundles if bundle.name == "forest"), bundles[0])
    examples = [trial for trial in data.trials
                if trial.rule_label != trial.truth
                and trial.model_labels[selected.name] == trial.truth]
    trial = examples[0] if examples else data.trials[0]
    index = trial.indices[len(trial.indices) // 2]
    prediction = data.model_predictions[selected.name][index]
    title, lines = model_explanation(selected, data.matrix[index], prediction)
    print(f"\nDemo trial {trial.key[2]}: truth={trial.truth}, "
          f"rules={trial.rule_label}, {selected.name}={trial.model_labels[selected.name]}")
    print(f"Explanation: {title}")
    for line in lines:
        print(f"  - {line}")


def handle_model_key(key, current, count):
    if ord("1") <= key <= ord("9") and key - ord("1") < count:
        return key - ord("1")
    if key == ord("m"):
        return (current + 1) % count
    return current


def run_replay(args, bundles: list[ModelBundle], data: ReplayData):
    selected_index = next((i for i, bundle in enumerate(bundles)
                           if bundle.name == "forest"), 0)
    filter_index = 0
    trial_position = 0
    frame_position = 0
    paused = False
    overview = False
    speed = max(0.25, min(4.0, args.speed))
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, WIDTH, HEIGHT)

    while True:
        selected = bundles[selected_index].name
        trials = filtered_trials(data, selected, FILTERS[filter_index])
        trial_position %= len(trials)
        trial = trials[trial_position]
        frame_position %= len(trial.indices)
        row_index = trial.indices[frame_position]

        if overview:
            image = draw_overview(bundles, selected_index, data.metrics,
                                  f"{args.session} · {len(data.trials)} trials")
        else:
            predictions = {bundle.name: data.model_predictions[bundle.name][row_index]
                           for bundle in bundles}
            footer = (f"{FILTERS[filter_index]}  ·  trial {trial_position + 1}/{len(trials)} "
                      f"· frame {frame_position + 1}/{len(trial.indices)} · {speed:.1f}x")
            image = draw_dashboard(
                data.landmarks[row_index], bundles, predictions, data.rules[row_index],
                data.rule_evidence[row_index], selected_index, truth=trial.truth,
                subtitle=f"REPLAY {args.session} · LANDMARKS ONLY",
                footer=footer,
            )
        cv2.imshow(WINDOW, image)
        key = cv2.waitKey(max(1, int(33 / speed))) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord(" "):
            paused = not paused
        if key == ord("g"):
            overview = not overview
        old_selected = selected_index
        selected_index = handle_model_key(key, selected_index, len(bundles))
        if selected_index != old_selected:
            trial_position = frame_position = 0
        if key == ord("f"):
            filter_index = (filter_index + 1) % len(FILTERS)
            trial_position = frame_position = 0
        elif key == ord("d"):
            trial_position = (trial_position + 1) % len(trials)
            frame_position = 0
        elif key == ord("a"):
            trial_position = (trial_position - 1) % len(trials)
            frame_position = 0
        elif key == ord("j"):
            frame_position = (frame_position - 1) % len(trial.indices)
        elif key == ord("k"):
            frame_position = (frame_position + 1) % len(trial.indices)
        elif key == ord("r"):
            frame_position = 0
        elif key in (ord("+"), ord("=")):
            speed = min(4.0, speed * 1.25)
        elif key == ord("-"):
            speed = max(0.25, speed / 1.25)
        elif not paused and not overview:
            frame_position = (frame_position + 1) % len(trial.indices)
    cv2.destroyAllWindows()


def run_live(args, bundles: list[ModelBundle]):
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    if not Path(MODEL_PATH).exists():
        raise SystemExit(f"MediaPipe model not found: {MODEL_PATH}")
    capture = cv2.VideoCapture(args.camera)
    if not capture.isOpened():
        raise SystemExit(f"Could not open camera {args.camera}")
    options = vision.HandLandmarkerOptions(
        # MediaPipe's ctypes bridge calls ``encode`` on this value and therefore
        # requires a plain string rather than pathlib.Path.
        base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.7,
        min_tracking_confidence=0.7,
    )
    classifier = GestureClassifier()
    selected_index = next((i for i, bundle in enumerate(bundles)
                           if bundle.name == "tree"), 0)
    overview = False
    last_dashboard = base_canvas("live", "waiting for hand")
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, WIDTH, HEIGHT)
    try:
        with vision.HandLandmarker.create_from_options(options) as landmarker:
            while True:
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("Camera stopped returning frames")
                frame = cv2.flip(frame, 1)
                result = landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB,
                             data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)),
                    int(time.monotonic() * 1000),
                )
                if overview:
                    image = draw_overview(bundles, selected_index,
                                          subtitle="LIVE · no ground-truth labels")
                elif result.hand_landmarks:
                    landmarks = result.hand_landmarks[0]
                    vector = np.asarray([extract_features(landmarks)], dtype=float)
                    rules, evidence = rule_snapshot(classifier, landmarks)
                    predictions = {bundle.name: model_predictions(bundle, vector)[0]
                                   for bundle in bundles}
                    image = draw_dashboard(
                        landmarks, bundles, predictions, rules, evidence,
                        selected_index, mode="live",
                        subtitle="LIVE CAMERA · NO ACTIONS", live_frame=frame,
                        footer="Move naturally to expose disagreements; press G for global XAI",
                    )
                    last_dashboard = image
                else:
                    image = last_dashboard.copy()
                    box(image, 280, 360, 660, 420, BG, border=AMBER)
                    text(image, "SHOW ONE HAND", (350, 399), 0.74, AMBER, 2)
                cv2.imshow(WINDOW, image)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord("g"):
                    overview = not overview
                selected_index = handle_model_key(key, selected_index, len(bundles))
    finally:
        capture.release()
        cv2.destroyAllWindows()


def main():
    args = parse_args()
    bundles = load_models(args)
    if args.mode == "replay" or args.headless_check:
        data = prepare_replay(args, bundles)
        if args.headless_check:
            print_headless_summary(data, bundles)
            return
        run_replay(args, bundles, data)
    else:
        run_live(args, bundles)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nXAI sandbox stopped.")
