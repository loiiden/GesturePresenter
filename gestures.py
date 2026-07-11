from __future__ import annotations
import math
from enum import Enum
from typing import Optional

# ── Landmark indices ───────────────────────────────────────────────────────────
WRIST      = 0
THUMB_CMC  = 1
THUMB_TIP  = 4
INDEX_MCP  = 5;  INDEX_PIP  = 6;  INDEX_TIP  = 8
MIDDLE_MCP = 9;  MIDDLE_PIP = 10; MIDDLE_TIP = 12
RING_MCP   = 13; RING_PIP   = 14; RING_TIP   = 16
PINKY_MCP  = 17; PINKY_PIP  = 18; PINKY_TIP  = 20


class Gesture(str, Enum):
    NONE             = "none"              # cursor moves freely
    PINCH            = "pinch"             # thumb+index still   → click on release
    PINCH_DRAG       = "pinch_drag"        # thumb+index + move  → scroll
    PINCH_RIGHT      = "pinch_right"       # thumb+middle        → right-click
    OPEN_PALM        = "open_palm"          # all 5 fingers out   → Mission Control
    FIST             = "fist"              # normal fist         → (unassigned)
    FIST_THUMB_LEFT  = "fist_thumb_left"   # fist + thumb left   → Space left
    FIST_THUMB_RIGHT = "fist_thumb_right"  # fist + thumb right  → Space right
    FIST_THUMB_UP    = "fist_thumb_up"     # fist + thumb up     → paste text


# ── Geometry helpers ───────────────────────────────────────────────────────────

def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)

def _hand_size(lms) -> float:
    return _dist(lms[WRIST], lms[MIDDLE_MCP]) or 1e-6

def _pinch_ratio(lms, tip_a: int, tip_b: int) -> float:
    return _dist(lms[tip_a], lms[tip_b]) / _hand_size(lms)

def _is_extended(tip, pip) -> bool:
    return tip.y < pip.y   # image y↓: tip above pip = finger extended

def is_fist(lms) -> bool:
    """All four fingers curled — used for left-hand speech recording trigger."""
    return not any([
        _is_extended(lms[INDEX_TIP],  lms[INDEX_PIP]),
        _is_extended(lms[MIDDLE_TIP], lms[MIDDLE_PIP]),
        _is_extended(lms[RING_TIP],   lms[RING_PIP]),
        _is_extended(lms[PINKY_TIP],  lms[PINKY_PIP]),
    ])

def is_open_palm(lms) -> bool:
    """All four fingers extended — used for left-hand precision mode trigger."""
    return all([
        _is_extended(lms[INDEX_TIP],  lms[INDEX_PIP]),
        _is_extended(lms[MIDDLE_TIP], lms[MIDDLE_PIP]),
        _is_extended(lms[RING_TIP],   lms[RING_PIP]),
        _is_extended(lms[PINKY_TIP],  lms[PINKY_PIP]),
    ])

def _thumb_direction(lms) -> Optional[str]:
    """Returns 'up', 'right', or 'left' if thumb is extended, else None."""
    if _dist(lms[THUMB_TIP], lms[INDEX_MCP]) / _hand_size(lms) < 0.4:
        return None  # thumb tucked
    dx = (lms[THUMB_TIP].x - lms[THUMB_CMC].x) / _hand_size(lms)
    dy = (lms[THUMB_TIP].y - lms[THUMB_CMC].y) / _hand_size(lms)
    # Vertical dominates and tip is above CMC → thumb up
    if abs(dy) > abs(dx) and dy < -0.25:
        return "up"
    if dx > 0.25:
        return "right"
    if dx < -0.25:
        return "left"
    return None


# ── Gesture classifier (pure geometry, one frame) ─────────────────────────────

class GestureClassifier:
    PINCH_THRESHOLD = 0.15

    def classify(self, lms) -> tuple[Gesture, dict]:
        tip_pos = (lms[INDEX_TIP].x, lms[INDEX_TIP].y)

        if _pinch_ratio(lms, THUMB_TIP, INDEX_TIP) < self.PINCH_THRESHOLD:
            return Gesture.PINCH, {"pos": tip_pos}

        if _pinch_ratio(lms, THUMB_TIP, MIDDLE_TIP) < self.PINCH_THRESHOLD:
            return Gesture.PINCH_RIGHT, {}

        ext = [
            _is_extended(lms[INDEX_TIP],  lms[INDEX_PIP]),
            _is_extended(lms[MIDDLE_TIP], lms[MIDDLE_PIP]),
            _is_extended(lms[RING_TIP],   lms[RING_PIP]),
            _is_extended(lms[PINKY_TIP],  lms[PINKY_PIP]),
        ]
        if all(ext):
            return Gesture.OPEN_PALM, {}
        if not any(ext):
            direction = _thumb_direction(lms)
            if direction == "up":
                return Gesture.FIST_THUMB_UP, {}
            if direction == "right":
                return Gesture.FIST_THUMB_RIGHT, {}
            if direction == "left":
                return Gesture.FIST_THUMB_LEFT, {}
            return Gesture.FIST, {}

        return Gesture.NONE, {"pos": tip_pos}


# ── Pinch tracker (click vs drag distinction) ─────────────────────────────────

DRAG_THRESHOLD = 0.03

class PinchTracker:
    """
    Emits high-level events from raw pinch state:
      ("click",)
      ("drag_delta", dx_norm, dy_norm)
      ("drag_end",)
    """
    def __init__(self):
        self._active   = False
        self._dragging = False
        self._start    = (0.0, 0.0)
        self._prev     = (0.0, 0.0)

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    @property
    def is_active(self) -> bool:
        return self._active

    def update(self, pinching: bool, pos: tuple[float, float]) -> list:
        events = []

        if pinching and not self._active:
            self._active   = True
            self._dragging = False
            self._start    = pos
            self._prev     = pos

        elif pinching and self._active:
            dx_total = pos[0] - self._start[0]
            dy_total = pos[1] - self._start[1]
            if not self._dragging and math.hypot(dx_total, dy_total) > DRAG_THRESHOLD:
                self._dragging = True

            if self._dragging:
                dx = pos[0] - self._prev[0]
                dy = pos[1] - self._prev[1]
                events.append(("drag_delta", dx, dy))
                self._prev = pos

        elif not pinching and self._active:
            if self._dragging:
                events.append(("drag_end",))
            else:
                events.append(("click",))
            self._active   = False
            self._dragging = False

        return events


# ── State machine (debounce for static gestures) ──────────────────────────────

HOLD_FRAMES: dict[Gesture, int] = {
    Gesture.PINCH:            3,
    Gesture.PINCH_RIGHT:      3,
    Gesture.OPEN_PALM:        12,
    Gesture.FIST:             12,
    Gesture.FIST_THUMB_LEFT:  10,
    Gesture.FIST_THUMB_RIGHT: 10,
    Gesture.FIST_THUMB_UP:    10,
}

class GestureStateMachine:
    """
    Debounces frame-by-frame raw gestures.
    Returns (entered, active, exited) each call.
    """
    def __init__(self):
        self._candidate       = Gesture.NONE
        self._candidate_count = 0
        self._active          = Gesture.NONE

    def update(
        self,
        raw: Gesture,
    ) -> tuple[Optional[Gesture], Optional[Gesture], Optional[Gesture]]:

        if raw != self._candidate:
            self._candidate       = raw
            self._candidate_count = 0
        else:
            self._candidate_count += 1

        threshold = HOLD_FRAMES.get(raw, 0)

        entered = exited = None
        if self._candidate_count >= threshold and raw != self._active:
            exited       = self._active if self._active != Gesture.NONE else None
            self._active = raw
            entered      = raw if raw != Gesture.NONE else None

        active = self._active if self._active == raw and raw != Gesture.NONE else None
        return entered, active, exited
