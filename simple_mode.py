"""Pinch-only slide navigation, isolated from the full gesture controls."""
from math import hypot, isfinite
from pathlib import Path
import sys

from gesture_model import GestureNetwork, MLGestureClassifier


# Fingertip separation / wrist-to-middle-knuckle length. Training pinch poses
# stay below 0.22; 0.30 leaves tracking tolerance but forces a prompt release.
MAX_PINCH_DISTANCE_RATIO = 0.30


def pinch_distance_ratio(landmarks, aspect=1.0):
    """Aspect-corrected 2-D gap in palm lengths; independent of camera distance."""
    def distance(a, b):
        return hypot((landmarks[a].x - landmarks[b].x) * aspect,
                     landmarks[a].y - landmarks[b].y)
    palm = distance(0, 9)
    gap = distance(4, 8)
    if not isfinite(palm) or not isfinite(gap) or palm < 1e-6:
        return float('inf')
    return gap / palm


class PinchSequence:
    """One event per debounced pinch release, with no double-pinch delay.

    Tracking loss cancels the pinch; an observed open hand is required to arm.
    """
    def __init__(self, debounce_seconds=0.045):
        self.debounce_seconds = debounce_seconds
        self.reset()

    def reset(self):
        self.armed = False
        self.closed = False
        self.candidate = None
        self.candidate_since = 0.0

    def update(self, pinching, now):
        if pinching is None:
            self.reset()
            return None
        if pinching != self.candidate:
            self.candidate = pinching
            self.candidate_since = now
        stable = now - self.candidate_since >= self.debounce_seconds
        if not self.armed:
            if stable and not pinching:
                self.armed = True
            return None
        if stable and pinching != self.closed:
            self.closed = pinching
            if not pinching:
                return 'release'
        return None


class SimpleModeController:
    """Independent per-hand tracking with shared right-hand model weights."""
    def __init__(self, path=None, hand='Right', network=None):
        if hand not in ('Right', 'Left'):
            raise ValueError('hand must be Right or Left')
        self.hand = hand
        self.action = 'next' if hand == 'Right' else 'previous'
        if path is None and network is None:
            candidates = (Path(__file__).parent / 'models/simple_pinch.npz',
                          Path(sys.prefix) / 'gesture_presenter/simple_pinch.npz')
            path = next((p for p in candidates if p.exists()), None)
        if path is None and network is None:
            raise RuntimeError('Simple mode model is missing. Reinstall the app or train research.train_simple.')
        network = network if network is not None else GestureNetwork(path)
        if network.labels != ['none', 'pinch']:
            raise ValueError('Simple mode requires a none/pinch model')
        self.classifier = MLGestureClassifier(network, hand)
        self.classifier.SMOOTHING = 1.0
        self.classifier.ENTER_CONFIDENCE = 0.8
        self.classifier.STAY_CONFIDENCE = 0.35
        self.sequence = PinchSequence()
        self.status = f"{self.hand}: show your hand"

    def update(self, landmarks, world, aspect, now, enabled=True):
        if landmarks is None or not enabled:
            self.status = (f"{self.hand}: show your hand" if enabled
                           else f"{self.hand}: controls locked")
            self.classifier.reset()
            return self.sequence.update(None, now)
        fingers_apart = pinch_distance_ratio(landmarks, aspect) > MAX_PINCH_DISTANCE_RATIO
        if fingers_apart:
            # Geometry overrides even a confident/sticky model prediction.
            # Reset its hysteresis so the old pinch cannot resume on re-entry.
            self.classifier.reset()
            payload = {'label': 'none'}
        else:
            _, payload = self.classifier.classify(landmarks, world, aspect)
        pinching = payload['label'] == 'pinch'
        event = self.action if self.sequence.update(pinching, now) else None
        probability = payload.get('probs', {}).get('pinch')
        confidence = f" · pinch {probability:.0%}" if probability is not None else ""
        if fingers_apart:
            confidence = " · fingers apart"
        if event:
            state = "Next slide" if event == 'next' else "Previous slide"
        elif not self.sequence.armed:
            state = "Release pinch to get ready"
        elif self.sequence.closed:
            state = "Pinch detected — release"
        else:
            state = "Ready — pinch thumb and index"
        self.status = self.hand + ": " + state + confidence
        return event
