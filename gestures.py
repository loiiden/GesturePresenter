from __future__ import annotations
import math
from collections import deque
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
    NONE             = "none"
    POINT            = "point"             # index only          → laser pointer
    V_SIGN           = "v_sign"            # index + middle held → Mission Control
    TWO_FINGER_SCROLL = "two_finger_scroll" # closed two fingers  → scroll
    PINCH            = "pinch"             # thumb+index still   → click on release
    PINCH_DRAG       = "pinch_drag"
    PINCH_RIGHT      = "pinch_right"       # thumb+middle        → right-click
    OPEN_PALM        = "open_palm"          # horizontal swipe    → change slide
    FIST             = "fist"              # held fist           → black screen
    FIST_THUMB_LEFT  = "fist_thumb_left"   # static fallback     → previous slide
    FIST_THUMB_RIGHT = "fist_thumb_right"  # static fallback     → next slide
    FIST_THUMB_UP    = "fist_thumb_up"     # thumb up            → play / pause


# ── Geometry helpers ───────────────────────────────────────────────────────────

def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)

def _hand_size(lms) -> float:
    return _dist(lms[WRIST], lms[MIDDLE_MCP]) or 1e-6

def _pinch_ratio(lms, tip_a: int, tip_b: int) -> float:
    return _dist(lms[tip_a], lms[tip_b]) / _hand_size(lms)

def _joint_angle(a, b, c) -> float:
    """Angle ABC in degrees. Using angles makes gestures work when tilted."""
    ab = (a.x - b.x, a.y - b.y)
    cb = (c.x - b.x, c.y - b.y)
    denom = math.hypot(*ab) * math.hypot(*cb)
    if denom < 1e-8:
        return 0.0
    cosine = max(-1.0, min(1.0, (ab[0] * cb[0] + ab[1] * cb[1]) / denom))
    return math.degrees(math.acos(cosine))


def _is_extended(lms, mcp: int, pip: int, tip: int) -> bool:
    """A finger is extended when straight and its tip is away from the palm."""
    # MediaPipe's 2-D projection makes a straight finger look moderately bent
    # when the palm is angled. These tolerances accept that perspective without
    # treating a genuinely curled finger as extended.
    straight = _joint_angle(lms[mcp], lms[pip], lms[tip]) > 140
    away = _dist(lms[tip], lms[WRIST]) > _dist(lms[pip], lms[WRIST])
    return straight and away


def _extended_fingers(lms) -> list[bool]:
    return [
        _is_extended(lms, INDEX_MCP, INDEX_PIP, INDEX_TIP),
        _is_extended(lms, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP),
        _is_extended(lms, RING_MCP, RING_PIP, RING_TIP),
        _is_extended(lms, PINKY_MCP, PINKY_PIP, PINKY_TIP),
    ]


def _index_available_for_pinch(lms) -> bool:
    """Reject thumb/index contact caused by making a closed fist."""
    angle = _joint_angle(lms[INDEX_MCP], lms[INDEX_PIP], lms[INDEX_TIP])
    tip_from_wrist = _dist(lms[INDEX_TIP], lms[WRIST])
    pip_from_wrist = _dist(lms[INDEX_PIP], lms[WRIST])
    return angle > 105 and tip_from_wrist > pip_from_wrist * 0.88

def is_fist(lms) -> bool:
    """All four fingers curled — used for left-hand speech recording trigger."""
    return not any(_extended_fingers(lms))

def is_open_palm(lms) -> bool:
    """Palm with the main fingers open; allows one imperfect ring/pinky."""
    ext = _extended_fingers(lms)
    return ext[0] and ext[1] and sum(ext) >= 3

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
    PINCH_CLOSE = 0.20
    PINCH_OPEN = 0.27

    def __init__(self):
        self._index_pinched = False
        self._middle_pinched = False

    def classify(self, lms) -> tuple[Gesture, dict]:
        tip_pos = (lms[INDEX_TIP].x, lms[INDEX_TIP].y)

        index_ratio = _pinch_ratio(lms, THUMB_TIP, INDEX_TIP)
        threshold = self.PINCH_OPEN if self._index_pinched else self.PINCH_CLOSE
        self._index_pinched = (
            index_ratio < threshold and _index_available_for_pinch(lms)
        )
        if self._index_pinched:
            return Gesture.PINCH, {"pos": tip_pos}

        # Right click is deliberately stricter than left click: the index must
        # remain clearly away, preventing an ambiguous three-finger cluster.
        middle_ratio = _pinch_ratio(lms, THUMB_TIP, MIDDLE_TIP)
        middle_threshold = self.PINCH_OPEN if self._middle_pinched else self.PINCH_CLOSE
        index_points = _is_extended(lms, INDEX_MCP, INDEX_PIP, INDEX_TIP)
        self._middle_pinched = (
            middle_ratio < middle_threshold
            and index_ratio > self.PINCH_OPEN
            and index_points
        )
        if self._middle_pinched:
            return Gesture.PINCH_RIGHT, {"pos": tip_pos}

        ext = _extended_fingers(lms)
        if ext[0] and ext[1] and sum(ext) >= 3:
            return Gesture.OPEN_PALM, {}
        if ext[0] and not any(ext[1:]):
            return Gesture.POINT, {"pos": tip_pos}
        if ext[0] and ext[1] and not ext[2] and not ext[3]:
            finger_gap = _pinch_ratio(lms, INDEX_TIP, MIDDLE_TIP)
            if finger_gap < 0.34:
                return Gesture.TWO_FINGER_SCROLL, {"pos": tip_pos}
            if finger_gap > 0.42:
                return Gesture.V_SIGN, {}
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

DRAG_THRESHOLD = 0.035
PINCH_ON_FRAMES = 2
PINCH_OFF_FRAMES = 2

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
        self._on_count = 0
        self._off_count = 0

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    @property
    def is_active(self) -> bool:
        return self._active

    def update(self, pinching: bool, pos: tuple[float, float]) -> list:
        events = []

        if pinching:
            self._on_count += 1
            self._off_count = 0
        else:
            self._off_count += 1
            self._on_count = 0

        stable_on = pinching and (self._active or self._on_count >= PINCH_ON_FRAMES)
        stable_off = not pinching and self._active and self._off_count >= PINCH_OFF_FRAMES

        if stable_on and not self._active:
            self._active   = True
            self._dragging = False
            self._start    = pos
            self._prev     = pos

        elif stable_on and self._active:
            dx_total = pos[0] - self._start[0]
            dy_total = pos[1] - self._start[1]
            if not self._dragging and math.hypot(dx_total, dy_total) > DRAG_THRESHOLD:
                self._dragging = True

            if self._dragging:
                dx = pos[0] - self._prev[0]
                dy = pos[1] - self._prev[1]
                events.append(("drag_delta", dx, dy))
                self._prev = pos

        elif stable_off:
            if self._dragging:
                events.append(("drag_end",))
            else:
                events.append(("click",))
            self._active   = False
            self._dragging = False

        return events

    def reset(self) -> None:
        """Cancel an in-progress gesture after tracking is lost."""
        self._active = self._dragging = False
        self._on_count = self._off_count = 0


# ── State machine (debounce for static gestures) ──────────────────────────────

HOLD_FRAMES: dict[Gesture, int] = {
    Gesture.POINT:            2,
    Gesture.V_SIGN:          18,
    Gesture.TWO_FINGER_SCROLL: 2,
    Gesture.PINCH:            3,
    Gesture.PINCH_RIGHT:      4,
    Gesture.OPEN_PALM:        12,
    Gesture.FIST:             12,
    Gesture.FIST_THUMB_LEFT:  10,
    Gesture.FIST_THUMB_RIGHT: 10,
    Gesture.FIST_THUMB_UP:    10,
}


class ScrollTracker:
    """Smooth vertical motion for a deliberate two-finger scroll pose."""
    WARMUP_FRAMES = 3
    MAX_GAP_FRAMES = 2
    DEADZONE = 0.002
    MAX_DELTA = 0.04

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._frames = 0
        self._gap = 0
        self._previous_y = None
        self._positions = deque(maxlen=3)

    def update(self, active: bool, y: float) -> Optional[float]:
        if not active:
            self._gap += 1
            if self._gap > self.MAX_GAP_FRAMES:
                self.reset()
            return None
        self._gap = 0
        self._frames += 1
        self._positions.append(y)
        smooth_y = sum(self._positions) / len(self._positions)
        if self._frames < self.WARMUP_FRAMES or self._previous_y is None:
            self._previous_y = smooth_y
            return None
        delta = max(-self.MAX_DELTA, min(self.MAX_DELTA, smooth_y - self._previous_y))
        self._previous_y = smooth_y
        return delta if abs(delta) >= self.DEADZONE else None


class PalmSwipeTracker:
    """Recognize one horizontal open-palm swipe per palm presentation."""
    MIN_HOLD_FRAMES = 3
    HORIZONTAL_DISTANCE = 0.09
    MAX_CLOSED_GAP = 4
    MAX_GESTURE_FRAMES = 35
    DIRECTION_DOMINANCE = 1.35

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._frames = 0
        self._closed_frames = 0
        self._start = None
        self._triggered = False
        self._positions = deque(maxlen=3)

    def update(self, open_palm: bool, pos: tuple[float, float]) -> Optional[str]:
        if not open_palm:
            # A moving hand often loses one or two fingers for a frame. Keep
            # the gesture alive through that brief tracking flicker.
            self._closed_frames += 1
            if self._closed_frames > self.MAX_CLOSED_GAP:
                self.reset()
            return None
        self._closed_frames = 0
        self._frames += 1
        self._positions.append(pos)
        smooth_pos = (
            sum(p[0] for p in self._positions) / len(self._positions),
            sum(p[1] for p in self._positions) / len(self._positions),
        )
        if self._start is None and self._frames >= self.MIN_HOLD_FRAMES:
            self._start = smooth_pos
            return None
        if self._start is None or self._triggered:
            return None
        dx = smooth_pos[0] - self._start[0]
        dy = smooth_pos[1] - self._start[1]
        horizontal = abs(dx) >= self.HORIZONTAL_DISTANCE
        direction_is_clear = abs(dx) >= abs(dy) * self.DIRECTION_DOMINANCE
        if horizontal and direction_is_clear:
            self._triggered = True
            return "right" if dx > 0 else "left"
        # Do not let slow drift over many seconds become a swipe.
        if self._frames >= self.MAX_GESTURE_FRAMES:
            self._start = smooth_pos
            self._frames = self.MIN_HOLD_FRAMES
        return None

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
            self._candidate_count = 1
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
