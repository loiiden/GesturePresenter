"""NumPy-only inference for the trained gesture classifier.

The model is a small standardized MLP exported to ``.npz`` by
``research.train``. Loading it needs nothing beyond NumPy, so the packaged
application carries no scikit-learn and no pickle: scikit-learn does not
guarantee that pickled estimators load across versions, which would make the
shipped binary fragile in a way that is invisible until it breaks on a user's
machine.

Beyond the forward pass this adds the three things a raw per-frame classifier
needs before it can drive a real UI:

* **Probability smoothing.** An exponential moving average over frames, so one
  bad frame cannot fire an action.
* **A confidence floor.** Anything below it becomes ``NONE`` rather than the
  best of several bad options — important because ``NONE`` is the class that
  keeps the app from acting while the presenter is just gesturing naturally.
* **Enter/stay hysteresis.** Switching classes requires more confidence than
  holding the current one, which stops flicker at decision boundaries.

The classifier is a drop-in for ``gestures.GestureClassifier``: it returns the
same ``(Gesture, payload)`` pair, so ``PinchTracker``, ``PalmSwipeTracker``,
``ScrollTracker`` and ``GestureStateMachine`` are unaffected.
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

from gesture_features import (
    FEATURE_VERSION, INDEX_TIP, FeatureConfig, extract_features,
)
from gestures import Gesture

_BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", os.path.dirname(__file__)))
MODEL_CANDIDATES = (
    _BUNDLE_DIR / "models" / "gesture_mlp.npz",
    Path(sys.prefix) / "gesture_presenter" / "gesture_mlp.npz",
)


def default_model_path() -> Path | None:
    return next((path for path in MODEL_CANDIDATES if path.exists()), None)


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - values.max()
    exponentiated = np.exp(shifted)
    return exponentiated / exponentiated.sum()


class GestureNetwork:
    """The exported network: standardize, dense+ReLU stack, softmax."""

    def __init__(self, path: Path):
        with np.load(path, allow_pickle=True) as archive:
            self.mean = archive["mean"]
            self.scale = archive["scale"]
            self.labels = [str(label) for label in archive["labels"]]
            count = int(archive["layer_count"])
            self.weights = [archive[f"w{i}"] for i in range(count)]
            self.biases = [archive[f"b{i}"] for i in range(count)]
            self.metadata = json.loads(str(archive["metadata"]))
            self.feature_config = FeatureConfig(**json.loads(str(archive["feature_config"])))
            version = int(archive["feature_version"])
        if version != FEATURE_VERSION:
            raise ValueError(
                f"{path} was trained with feature version {version}, but this "
                f"build computes version {FEATURE_VERSION}. Retrain the model."
            )
        self.gestures = [self._to_gesture(label) for label in self.labels]
        self.none_index = next(
            (i for i, g in enumerate(self.gestures) if g == Gesture.NONE), None
        )

    @staticmethod
    def _to_gesture(label: str) -> Gesture:
        try:
            return Gesture(label)
        except ValueError:
            # A class the runtime has no action for still needs to be
            # predictable, so it can absorb poses instead of them landing on a
            # neighbouring class that does fire an action.
            return Gesture.NONE

    def probabilities(self, features: np.ndarray) -> np.ndarray:
        activations = (features - self.mean) / self.scale
        for weight, bias in zip(self.weights[:-1], self.biases[:-1]):
            activations = np.maximum(activations @ weight + bias, 0.0)
        return _softmax(activations @ self.weights[-1] + self.biases[-1])


class MLGestureClassifier:
    """Frame-by-frame gesture prediction with smoothing and hysteresis."""

    SMOOTHING = 0.5        # EMA weight on the newest frame
    ENTER_CONFIDENCE = 0.62
    STAY_CONFIDENCE = 0.38

    def __init__(self, network: GestureNetwork, hand: str = "Right"):
        self.network = network
        self.hand = hand
        self._smoothed: np.ndarray | None = None
        self._current: int | None = None
        self._warned_missing_world = False

    def reset(self) -> None:
        self._smoothed = None
        self._current = None

    def classify(self, landmarks, world_landmarks=None, aspect: float = 1.0
                 ) -> tuple[Gesture, dict]:
        if (world_landmarks is None and self.network.feature_config.world
                and not self._warned_missing_world):
            # Silently zero-filling a third of the feature vector would look
            # like a mysteriously bad model rather than a missing input.
            self._warned_missing_world = True
            warnings.warn(
                "Gesture model expects MediaPipe world landmarks but received "
                "none; predictions will be unreliable. Ensure the landmarker "
                "result's hand_world_landmarks are passed through.",
                RuntimeWarning, stacklevel=2,
            )
        features = extract_features(
            landmarks, world_landmarks, aspect=aspect, hand=self.hand,
            config=self.network.feature_config,
        )
        probabilities = self.network.probabilities(features)
        self._smoothed = (
            probabilities if self._smoothed is None
            else self.SMOOTHING * probabilities + (1 - self.SMOOTHING) * self._smoothed
        )

        best = int(np.argmax(self._smoothed))
        confidence = float(self._smoothed[best])
        if self._current is not None and self._smoothed[self._current] >= self.STAY_CONFIDENCE:
            if best != self._current and confidence >= self.ENTER_CONFIDENCE:
                self._current = best
        elif confidence >= self.ENTER_CONFIDENCE:
            self._current = best
        else:
            self._current = self.network.none_index

        index = self._current if self._current is not None else self.network.none_index
        gesture = self.network.gestures[index] if index is not None else Gesture.NONE
        tip = landmarks[INDEX_TIP]
        return gesture, {
            "pos": (tip.x, tip.y),
            "confidence": float(self._smoothed[index]) if index is not None else 0.0,
            "label": self.network.labels[index] if index is not None else "none",
            # Callers that need recall more than precision (an open-palm swipe
            # is briefly blurred at speed, and a missed swipe is more annoying
            # than a late one) can threshold a class directly instead of
            # waiting for it to win the argmax.
            "probs": dict(zip(self.network.labels, self._smoothed.tolist())),
        }


def load_classifiers(path: Path | None = None) -> tuple[MLGestureClassifier, MLGestureClassifier] | None:
    """Return (right, left) classifiers, or None if no model is installed.

    Each hand gets its own instance because smoothing and hysteresis are
    per-hand state; sharing one would let the control hand's history leak into
    the lock hand's decisions.
    """
    path = path or default_model_path()
    if path is None:
        return None
    network = GestureNetwork(path)
    return MLGestureClassifier(network, "Right"), MLGestureClassifier(network, "Left")
