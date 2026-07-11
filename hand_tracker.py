import os
import threading
import urllib.request
import time
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import Quartz
import pyautogui

from gestures import (
    Gesture, GestureClassifier, GestureStateMachine, PinchTracker, PalmSwipeTracker,
    INDEX_TIP, is_open_palm, is_fist,
)
import actions
from speech import SpeechRecognizer

pyautogui.FAILSAFE = False

MODEL_PATH = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")
MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)

TARGET_DISPLAY     = 1     # change to 1 for external display
SMOOTH             = 0.35  # used only in precision mode
PRECISION_DIVISOR  = 2     # cursor movement scale in precision mode
PALM_HOLD_FRAMES   = 24    # deliberate left-palm hold toggles presentation controls
FIST_HOLD_FRAMES   = 15    # left-hand frames needed to start/stop recording

# Acceleration curve for normal cursor mode (delta-based, like a mouse)
# scale = ACCEL_BASE + ACCEL_GAIN * (speed / ACCEL_NORM)²
ACCEL_BASE  = 0.4   # multiplier at near-zero speed (slow = precise)
ACCEL_GAIN  = 1.0   # how aggressively fast movements are amplified
ACCEL_NORM  = 0.04  # reference speed (normalised units/frame) for the gain
MAX_DELTA   = 0.08  # cap per-frame hand delta to absorb re-detection jumps
CURSOR_DEADZONE = 0.0015  # suppress landmark shimmer while holding still
CURSOR_FILTER = 0.45      # low-pass filter for hand deltas

# Fraction of the camera frame (each side) that is ignored.
# 0.2 means only the central 60% of the camera maps to the full screen.
# Increase to raise sensitivity (less hand movement needed).
CAM_MARGIN_X = 0.3
CAM_MARGIN_Y = 0.3

HAND_CONNECTIONS = [
    (0,1),(0,5),(0,9),(0,13),(0,17),(5,9),(9,13),(13,17),
    (1,2),(2,3),(3,4),(5,6),(6,7),(7,8),(9,10),(10,11),(11,12),
    (13,14),(14,15),(15,16),(17,18),(18,19),(19,20),
]
FINGERTIP_IDS = {4, 8, 12, 16, 20}

GESTURE_COLORS = {
    Gesture.PINCH:            (0, 140, 255),
    Gesture.PINCH_DRAG:       (0, 200, 255),
    Gesture.PINCH_RIGHT:      (100, 0, 255),
    Gesture.POINT:            (0, 80, 255),
    Gesture.V_SIGN:           (255, 120, 40),
    Gesture.OPEN_PALM:        (0, 255, 140),
    Gesture.FIST:             (0, 60, 255),
    Gesture.FIST_THUMB_LEFT:  (255, 200, 0),
    Gesture.FIST_THUMB_RIGHT: (255, 200, 0),
    Gesture.FIST_THUMB_UP:    (0, 255, 80),
}


def get_display_rect(index: int) -> tuple[int, int, int, int]:
    _, display_ids, _ = Quartz.CGGetActiveDisplayList(16, None, None)
    print("Detected displays:")
    for i, did in enumerate(display_ids):
        b = Quartz.CGDisplayBounds(did)
        tag = " [main]" if Quartz.CGDisplayIsMain(did) else ""
        print(f"  [{i}]  {int(b.size.width)}x{int(b.size.height)}"
              f"  origin=({int(b.origin.x)},{int(b.origin.y)}){tag}")
    if not display_ids:
        raise RuntimeError("No active display detected")
    if index >= len(display_ids):
        print(f"Display [{index}] is unavailable; using the main display.")
        index = next((i for i, did in enumerate(display_ids)
                      if Quartz.CGDisplayIsMain(did)), 0)
    did = display_ids[index]
    b   = Quartz.CGDisplayBounds(did)
    return int(b.origin.x), int(b.origin.y), int(b.size.width), int(b.size.height)


def cam_to_screen(nx: float, ny: float, disp_x, disp_y, scr_w, scr_h) -> tuple[float, float]:
    """Map normalised camera coords to screen coords using the active margin window."""
    sx = (nx - CAM_MARGIN_X) / (1 - 2 * CAM_MARGIN_X)
    sy = (ny - CAM_MARGIN_Y) / (1 - 2 * CAM_MARGIN_Y)
    sx = max(0.0, min(1.0, sx))
    sy = max(0.0, min(1.0, sy))
    return disp_x + sx * scr_w, disp_y + sy * scr_h


def download_model():
    print("Downloading hand landmarker model (~9 MB)…")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Done.")


def draw_hand(frame, lms, active_gesture: Gesture):
    h, w = frame.shape[:2]
    pts  = [(int(lm.x * w), int(lm.y * h)) for lm in lms]
    conn_color = GESTURE_COLORS.get(active_gesture, (0, 220, 0))

    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], conn_color, 2, cv2.LINE_AA)

    for i, (x, y) in enumerate(pts):
        r = 8 if i in FINGERTIP_IDS else 5
        c = (0, 80, 255) if i in FINGERTIP_IDS else (255, 220, 0)
        cv2.circle(frame, (x, y), r, c, -1, cv2.LINE_AA)


def draw_hud(frame, gesture: Gesture, pinch_dragging: bool,
             controls_enabled: bool, last_action: str):
    h, w = frame.shape[:2]
    mode_color = (0, 220, 120) if controls_enabled else (80, 80, 255)
    mode_text = "PRESENTATION READY" if controls_enabled else "CONTROLS LOCKED"
    cv2.rectangle(frame, (0, 0), (w - 1, h - 1), mode_color, 3)
    cv2.putText(frame, mode_text, (20, h - 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, mode_color, 2, cv2.LINE_AA)
    if last_action:
        (tw, _), _ = cv2.getTextSize(last_action, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
        cv2.putText(frame, last_action, ((w - tw) // 2, h - 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 220, 255), 2, cv2.LINE_AA)
    label = gesture.value.replace("_", " ").upper()
    if gesture == Gesture.PINCH and pinch_dragging:
        label = "PINCH DRAG"
    if gesture not in (Gesture.NONE,):
        cv2.putText(frame, label, (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                    GESTURE_COLORS.get(gesture, (255, 255, 255)), 2, cv2.LINE_AA)


def _wrap_text(text: str, font, scale, thickness, max_w: int) -> list[str]:
    """Greedy word-wrap so a line never exceeds max_w pixels."""
    if not text:
        return []
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        (tw, _), _ = cv2.getTextSize(trial, font, scale, thickness)
        if tw <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_speech_overlay(frame, state: str, text: str, dot_on: bool):
    """Render speech feedback as a centred banner on the camera frame.

    state: "idle" | "recording" | "transcribing" | "overlay"
    """
    if state == "idle":
        return

    h, w = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    bw   = int(w * 0.9)
    x0   = (w - bw) // 2
    y0   = 15

    if state == "recording":
        status = "REC  " + ("●" if dot_on else " ")
        status_col = (80, 80, 255)
        body_lines = []
    elif state == "transcribing":
        status = "Transcribing..."
        status_col = (0, 200, 255)
        body_lines = []
    else:  # overlay (result)
        status = "Thumb up = paste    Fist = cancel"
        status_col = (180, 180, 180)
        body_lines = _wrap_text(text or "(nothing heard)", font, 0.7, 2, bw - 30)

    bh = 40 + len(body_lines) * 28 + (10 if body_lines else 0)

    # Semi-transparent dark banner
    band = frame.copy()
    cv2.rectangle(band, (x0, y0), (x0 + bw, y0 + bh), (28, 28, 28), -1)
    cv2.addWeighted(band, 0.8, frame, 0.2, 0, frame)
    cv2.rectangle(frame, (x0, y0), (x0 + bw, y0 + bh), status_col, 1, cv2.LINE_AA)

    cv2.putText(frame, status, (x0 + 15, y0 + 28),
                font, 0.7, status_col, 2, cv2.LINE_AA)
    for i, line in enumerate(body_lines):
        cv2.putText(frame, line, (x0 + 15, y0 + 58 + i * 28),
                    font, 0.7, (255, 255, 255), 2, cv2.LINE_AA)


def main():
    if not os.path.exists(MODEL_PATH):
        download_model()

    # ── Speech state (shared between main loop and speech callbacks) ──────────
    # "idle" | "recording" | "transcribing" | "overlay"
    # The camera loop runs on the MAIN thread (macOS requires cv2.imshow there);
    # speech callbacks fire from background threads, so the shared state needs a
    # lock. Feedback is drawn straight onto the camera frame — no second window.
    speech_state = "idle"
    pending_text = ""
    speech_lock  = threading.Lock()

    def _on_transcribing():
        nonlocal speech_state
        with speech_lock:
            speech_state = "transcribing"

    def _on_result(text):
        nonlocal speech_state, pending_text
        with speech_lock:
            speech_state = "overlay"
            pending_text = text

    recognizer = SpeechRecognizer(on_result=_on_result, on_transcribing=_on_transcribing)

    disp_x, disp_y, scr_w, scr_h = get_display_rect(TARGET_DISPLAY)
    print(f"Mapping to display [{TARGET_DISPLAY}]  "
          f"origin=({disp_x},{disp_y})  size={scr_w}x{scr_h}\n")

    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.7,
        min_tracking_confidence=0.7,
    )

    classifier  = GestureClassifier()
    state_m     = GestureStateMachine()
    pinch_track = PinchTracker()
    swipe_track = PalmSwipeTracker()

    cap          = cv2.VideoCapture(0)
    frame_idx    = 0
    cx           = disp_x + scr_w / 2
    cy           = disp_y + scr_h / 2
    last_space_t = 0.0

    presentation_enabled = True
    left_palm_count    = 0
    left_palm_held     = False
    last_action        = ""
    last_action_until  = 0.0

    left_fist_count = 0
    left_fist_held  = False

    prev_pos_norm = None
    filtered_delta = (0.0, 0.0)
    lost_right_frames = 0

    cv2.namedWindow("Hand Tracker", cv2.WINDOW_AUTOSIZE)

    with vision.HandLandmarker.create_from_options(options) as landmarker:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break

            frame  = cv2.flip(frame, 1)
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            # Camera timestamps can stall or jump backwards. MediaPipe requires
            # strictly increasing timestamps in VIDEO mode.
            ts_ms = int(time.monotonic() * 1000)
            result = landmarker.detect_for_video(mp_img, ts_ms)

            # ── Separate hands by handedness ──────────────────────────
            right_lms = left_lms = None
            for i, hand_lms in enumerate(result.hand_landmarks):
                label = result.handedness[i][0].category_name
                if label == "Left":
                    right_lms = hand_lms
                else:
                    left_lms = hand_lms

            # ── Left hand: deliberate safety lock ─────────────────────
            if left_lms and is_open_palm(left_lms):
                left_palm_count = min(left_palm_count + 1, PALM_HOLD_FRAMES)
            else:
                left_palm_count = max(left_palm_count - 1, 0)

            palm_held = left_palm_count >= PALM_HOLD_FRAMES
            if palm_held and not left_palm_held:
                presentation_enabled = not presentation_enabled
                last_action = "CONTROLS ON" if presentation_enabled else "CONTROLS LOCKED"
                last_action_until = time.monotonic() + 1.5
            left_palm_held = palm_held

            # ── Left hand: fist → start/stop speech recording ─────────
            if left_lms and is_fist(left_lms):
                left_fist_count = min(left_fist_count + 1, FIST_HOLD_FRAMES)
            else:
                left_fist_count = max(left_fist_count - 1, 0)

            should_fist = left_fist_count >= FIST_HOLD_FRAMES
            with speech_lock:
                cur_speech = speech_state
            if should_fist != left_fist_held:
                left_fist_held = should_fist
                if left_fist_held and cur_speech == "idle":
                    with speech_lock:
                        speech_state = "recording"
                    recognizer.start_recording()
                elif not left_fist_held and cur_speech == "recording":
                    recognizer.stop_recording()

            # ── Right hand: gestures + cursor ──────────────────────────
            if right_lms:
                lost_right_frames = 0
                lms = right_lms
                raw_gesture, payload = classifier.classify(lms)
                entered, active, exited = state_m.update(raw_gesture)

                is_pinching  = (raw_gesture == Gesture.PINCH)
                pos_norm     = payload.get("pos", (lms[INDEX_TIP].x, lms[INDEX_TIP].y))
                pinch_events = pinch_track.update(is_pinching, pos_norm)
                palm_pos = (lms[9].x, lms[9].y)
                # Use palm geometry directly and let the swipe tracker bridge
                # brief classification gaps caused by motion blur.
                swipe = swipe_track.update(is_open_palm(lms), palm_pos)

                for ev in pinch_events if presentation_enabled else ():
                    # In presentation mode a pinch has no drag/scroll meaning;
                    # always turn its release into one click. This makes normal
                    # landmark movement during a pinch harmless.
                    if ev[0] in ("click", "drag_end"):
                        actions.left_click()
                        last_action, last_action_until = "CLICK", time.monotonic() + 1.0

                if presentation_enabled and entered == Gesture.PINCH_RIGHT:
                    actions.right_click()

                now = time.time()
                with speech_lock:
                    cur_speech = speech_state

                if cur_speech == "overlay":
                    if entered == Gesture.FIST_THUMB_UP:
                        actions.paste_text(pending_text)
                        with speech_lock:
                            speech_state = "idle"
                    elif entered == Gesture.FIST:
                        with speech_lock:
                            speech_state = "idle"
                elif presentation_enabled:
                    if swipe == "left":
                        actions.next_slide()
                        last_action, last_action_until = "NEXT SLIDE", time.monotonic() + 1.2
                    elif swipe == "right":
                        actions.previous_slide()
                        last_action, last_action_until = "PREVIOUS SLIDE", time.monotonic() + 1.2
                    if entered == Gesture.FIST:
                        actions.toggle_black_screen()
                        last_action, last_action_until = "BLACK SCREEN", time.monotonic() + 1.2
                    elif entered == Gesture.V_SIGN:
                        actions.mission_control()
                        last_action, last_action_until = "MISSION CONTROL", time.monotonic() + 1.5
                    elif entered == Gesture.FIST_THUMB_UP:
                        actions.toggle_media()
                        last_action, last_action_until = "PLAY / PAUSE", time.monotonic() + 1.2
                    elif entered in (Gesture.FIST_THUMB_LEFT, Gesture.FIST_THUMB_RIGHT) \
                            and now - last_space_t > 1.0:
                        last_space_t = now
                        if entered == Gesture.FIST_THUMB_LEFT:
                            actions.previous_slide()
                            last_action = "PREVIOUS SLIDE"
                        else:
                            actions.next_slide()
                            last_action = "NEXT SLIDE"
                        last_action_until = time.monotonic() + 1.2

                # An isolated index finger behaves as a laser pointer. Normal
                # conversational hand movement never moves the cursor.
                if presentation_enabled and raw_gesture == Gesture.POINT:
                    tx, ty = cam_to_screen(pos_norm[0], pos_norm[1], disp_x, disp_y, scr_w, scr_h)
                    cx += SMOOTH * (tx - cx)
                    cy += SMOOTH * (ty - cy)
                    actions.move_cursor(int(cx), int(cy))

                prev_pos_norm = pos_norm
            else:
                swipe_track.update(False, (0.0, 0.0))
                lost_right_frames += 1
                if lost_right_frames >= 3:
                    prev_pos_norm = None
                    filtered_delta = (0.0, 0.0)
                    pinch_track.reset()

            # ── Draw overlays and show the window ──────────────────────
            active_gesture = active or (entered if entered else Gesture.NONE) \
                if right_lms else Gesture.NONE
            if right_lms:
                draw_hand(frame, right_lms, active_gesture)
            if left_lms:
                draw_hand(frame, left_lms, Gesture.NONE)
            visible_action = last_action if time.monotonic() < last_action_until else ""
            draw_hud(frame, active_gesture, pinch_track.is_dragging,
                     presentation_enabled, visible_action)

            with speech_lock:
                cur_speech, cur_text = speech_state, pending_text
            draw_speech_overlay(frame, cur_speech, cur_text, dot_on=(frame_idx // 8) % 2 == 0)

            cv2.imshow("Hand Tracker", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("l"):
                presentation_enabled = not presentation_enabled
                last_action = "CONTROLS ON" if presentation_enabled else "CONTROLS LOCKED"
                last_action_until = time.monotonic() + 1.5
            if key in (27, ord("q")):   # Esc or q
                break

            frame_idx += 1

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
