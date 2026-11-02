from __future__ import annotations

import os
import sys
import base64
import queue
import threading
import urllib.request
import time
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import pyautogui

from gestures import (
    Gesture, GestureClassifier, GestureStateMachine, ClickTracker, PalmSwipeTracker,
    ScrollTracker,
    INDEX_TIP, is_open_palm,
)
import gesture_model
import actions
from config import AppConfig
from devices import display_rects

pyautogui.FAILSAFE = False

_MODEL_CANDIDATES = (
    os.path.join(os.path.dirname(__file__), "hand_landmarker.task"),
    os.path.join(sys.prefix, "gesture_presenter", "hand_landmarker.task"),
)
MODEL_PATH = next((path for path in _MODEL_CANDIDATES if os.path.exists(path)),
                  _MODEL_CANDIDATES[0])
MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)

SMOOTH             = 0.35  # pointer smoothing
# Open-palm probability accepted by the swipe tracker. Deliberately below the
# model's own decision threshold: swiping favours recall, see the call site.
SWIPE_PALM_CONFIDENCE = 0.35
PALM_HOLD_FRAMES   = 24    # deliberate left-palm hold toggles presentation controls
FIST_HOLD_FRAMES   = 15    # left-hand frames needed to start/stop recording

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
    Gesture.INDEX_THUMB:      (0, 140, 255),
    Gesture.POINT:            (0, 80, 255),
    Gesture.V_SIGN:           (255, 120, 40),
    Gesture.TWO_FINGER_SCROLL:(180, 120, 20),
    Gesture.OPEN_PALM:        (0, 255, 140),
    Gesture.FIST:             (0, 60, 255),
    Gesture.FIST_THUMB_LEFT:  (255, 200, 0),
    Gesture.FIST_THUMB_RIGHT: (255, 200, 0),
    Gesture.FIST_THUMB_UP:    (0, 255, 80),
}


class _RuleClassifier:
    """Adapts the original geometric classifier to the learned one's signature.

    Keeping one call shape means the tracking loop below has a single code path
    whether or not a trained model is installed.
    """

    def __init__(self):
        self._inner = GestureClassifier()
        self.network = None

    def classify(self, landmarks, world_landmarks=None, aspect: float = 1.0):
        return self._inner.classify(landmarks)

    def reset(self) -> None:
        self._inner = GestureClassifier()


def get_display_rect(index: int) -> tuple[int, int, int, int]:
    try:
        displays = display_rects()
        if not displays or displays[0]["width"] == 0:
            raise RuntimeError("No displays detected")
        if index >= len(displays):
            index = next((i for i, display in enumerate(displays)
                          if display["primary"]), 0)
        display = displays[index]
        return display["x"], display["y"], display["width"], display["height"]
    except Exception as exc:
        print(f"Display detection fallback: {exc}")
        width, height = pyautogui.size()
        return 0, 0, width, height


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


def draw_hud(frame, gesture: Gesture,
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

    state: "idle" | "recording" | "transcribing" | "paste_pending"
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
    else:  # paste_pending
        status = "Pasting transcription…"
        status_col = (0, 220, 140)
        body_lines = []

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


def run(app_config: AppConfig | None = None, stop_event=None, ui_queue=None):
    app_config = app_config or AppConfig.load()
    if not os.path.exists(MODEL_PATH):
        download_model()

    # ── Speech state (shared between main loop and speech callbacks) ──────────
    # "idle" | "recording" | "transcribing" | "paste_pending"
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
            pending_text = text.strip()
            speech_state = "paste_pending" if pending_text else "idle"

    recognizer = None
    if app_config.voice_enabled:
        # Keep Whisper and audio libraries completely out of gesture-only mode.
        from speech import SpeechRecognizer
        recognizer = SpeechRecognizer(
            on_result=_on_result, on_transcribing=_on_transcribing
        )

    disp_x, disp_y, scr_w, scr_h = get_display_rect(app_config.display_index)
    print(f"Mapping to display [{app_config.display_index}]  "
          f"origin=({disp_x},{disp_y})  size={scr_w}x{scr_h}\n")

    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.7,
        min_tracking_confidence=0.7,
    )

    # The learned classifier is preferred; the original geometric rules remain
    # as a fallback so a build without a trained model still works.
    classifiers = gesture_model.load_classifiers()
    if classifiers is None:
        right_classifier, left_classifier = _RuleClassifier(), _RuleClassifier()
        print("No trained gesture model found — using the geometric rules.")
    else:
        right_classifier, left_classifier = classifiers
        print(f"Gesture model loaded: {right_classifier.network.metadata.get('created_at', '?')}")

    state_m     = GestureStateMachine()
    click_track = ClickTracker()
    swipe_track = PalmSwipeTracker()
    scroll_track = ScrollTracker()

    cap          = cv2.VideoCapture(app_config.camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open camera {app_config.camera_index}")

    def emit(event: dict) -> None:
        if ui_queue is None:
            return
        try:
            ui_queue.put_nowait(event)
        except queue.Full:
            try:
                ui_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                ui_queue.put_nowait(event)
            except queue.Full:
                pass

    emit({"type": "status", "message": "Camera active — tracking gestures"})
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
    # Either hand can make the click pose; both feed one tracker.
    right_clicking = False
    left_clicking  = False
    was_clicking_right = False
    was_clicking_left  = False

    lost_right_frames = 0

    if ui_queue is None:
        cv2.namedWindow("Hand Tracker", cv2.WINDOW_AUTOSIZE)

    with vision.HandLandmarker.create_from_options(options) as landmarker:
        while cap.isOpened():
            if stop_event is not None and stop_event.is_set():
                break
            ok, frame = cap.read()
            if not ok:
                break

            # Always use a natural, selfie-style preview. Gesture handedness and
            # pointer movement are defined against this mirrored coordinate space.
            frame = cv2.flip(frame, 1)
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            # Camera timestamps can stall or jump backwards. MediaPipe requires
            # strictly increasing timestamps in VIDEO mode.
            ts_ms = int(time.monotonic() * 1000)
            result = landmarker.detect_for_video(mp_img, ts_ms)

            # ── Separate hands by handedness ──────────────────────────
            # Aspect is needed because MediaPipe normalizes x by width and y by
            # height separately; the feature extractor undoes that so the model
            # behaves the same on 16:9 and 4:3 cameras.
            frame_h, frame_w = frame.shape[:2]
            aspect = frame_w / frame_h if frame_h else 1.0
            right_lms = left_lms = None
            right_world = left_world = None
            for i, hand_lms in enumerate(result.hand_landmarks):
                label = result.handedness[i][0].category_name
                world = (result.hand_world_landmarks[i]
                         if i < len(result.hand_world_landmarks) else None)
                # MediaPipe handedness labels reverse in the mirrored frame.
                controls_right_hand = label == "Left"
                if controls_right_hand:
                    right_lms, right_world = hand_lms, world
                else:
                    left_lms, left_world = hand_lms, world

            # ── Left hand: deliberate safety lock ─────────────────────
            left_gesture = Gesture.NONE
            if left_lms:
                left_gesture, _ = left_classifier.classify(left_lms, left_world, aspect)
            else:
                left_classifier.reset()

            if left_gesture == Gesture.OPEN_PALM:
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
            if recognizer is not None and left_gesture == Gesture.FIST:
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

            # Either hand can click; suppress the left click during voice input.
            left_busy = recognizer is not None and (
                left_fist_count > 0 or cur_speech == "recording"
            )
            left_clicking = left_gesture == Gesture.INDEX_THUMB and not left_busy

            # Transcription confirmation is intentionally unnecessary: paste
            # the first non-empty result as soon as Whisper returns it.
            auto_paste = ""
            with speech_lock:
                if speech_state == "paste_pending":
                    auto_paste = pending_text
                    pending_text = ""
                    speech_state = "idle"
            if auto_paste:
                actions.paste_text(auto_paste)
                last_action = "TRANSCRIPTION PASTED"
                last_action_until = time.monotonic() + 1.5

            # ── Right hand: gestures + cursor ──────────────────────────
            if right_lms:
                lost_right_frames = 0
                lms = right_lms
                raw_gesture, payload = right_classifier.classify(lms, right_world, aspect)
                entered, active, exited = state_m.update(raw_gesture)

                right_clicking = (raw_gesture == Gesture.INDEX_THUMB)
                pos_norm     = payload.get("pos", (lms[INDEX_TIP].x, lms[INDEX_TIP].y))
                palm_pos = (lms[9].x, lms[9].y)
                # A swipe is judged on a permissive open-palm probability rather
                # than on the winning class: at swipe speed the palm blurs and
                # briefly loses the argmax, and the swipe tracker already
                # bridges short gaps. Actions that must not misfire (black
                # screen, Mission Control) still go through the strict path.
                probs = payload.get("probs")
                palm_open = (probs.get(Gesture.OPEN_PALM.value, 0.0) >= SWIPE_PALM_CONFIDENCE
                             if probs else is_open_palm(lms))
                swipe = swipe_track.update(palm_open, palm_pos)
                scroll_delta = scroll_track.update(
                    raw_gesture == Gesture.TWO_FINGER_SCROLL, pos_norm[1]
                )

                # Freeze the pointer during the click pose, as before.
                if presentation_enabled and raw_gesture == Gesture.POINT:
                    tx, ty = cam_to_screen(
                        pos_norm[0], pos_norm[1], disp_x, disp_y, scr_w, scr_h
                    )
                    cx += SMOOTH * (tx - cx)
                    cy += SMOOTH * (ty - cy)
                    actions.move_cursor(int(cx), int(cy))

                if presentation_enabled and scroll_delta is not None:
                    actions.scroll(scroll_delta)
                    last_action, last_action_until = "SCROLL", time.monotonic() + 0.35

                now = time.time()
                with speech_lock:
                    cur_speech = speech_state

                if presentation_enabled:
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

            else:
                right_clicking = False
                swipe_track.update(False, (0.0, 0.0))
                lost_right_frames += 1
                if lost_right_frames >= 3:
                    # Drop the smoothed probabilities too, so a gesture held
                    # before the hand left frame cannot resume on re-entry.
                    right_classifier.reset()

            # ── Click pose from either hand → one click ─────────────────────
            # Both hands feed one tracker. Making the pose with both hands
            # at once still produces one click.
            #
            # Losing a hand mid-pose cancels the click: lowering it out of
            # frame is not a deliberate release.
            vanished_mid_click = (
                (was_clicking_right and not right_lms)
                or (was_clicking_left and not left_lms)
            )
            if vanished_mid_click:
                click_track.reset()
            else:
                for ev in click_track.update(right_clicking or left_clicking):
                    if ev[0] == "click" and presentation_enabled:
                        actions.left_click()
                        last_action, last_action_until = "CLICK", time.monotonic() + 1.0
            was_clicking_right, was_clicking_left = right_clicking, left_clicking

            # ── Draw overlays and show the window ──────────────────────
            active_gesture = active or (entered if entered else Gesture.NONE) \
                if right_lms else Gesture.NONE
            if right_lms:
                draw_hand(frame, right_lms, active_gesture)
            if left_lms:
                # Colour the left hand when it is clicking, so the click hand
                # gives the same feedback the pointing hand does.
                draw_hand(frame, left_lms,
                          Gesture.INDEX_THUMB if left_clicking else Gesture.NONE)
            visible_action = last_action if time.monotonic() < last_action_until else ""
            draw_hud(frame, active_gesture, presentation_enabled, visible_action)

            with speech_lock:
                cur_speech, cur_text = speech_state, pending_text
            draw_speech_overlay(frame, cur_speech, cur_text, dot_on=(frame_idx // 8) % 2 == 0)

            if ui_queue is not None:
                # Limit preview traffic while gesture processing continues at
                # full camera speed. JPEG is efficient to display in a WebView.
                if frame_idx % 3 == 0:
                    preview = frame
                    if preview.shape[1] > 800:
                        scale = 800 / preview.shape[1]
                        preview = cv2.resize(preview, None, fx=scale, fy=scale)
                    ok_jpeg, encoded = cv2.imencode(
                        ".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 72]
                    )
                    if ok_jpeg:
                        emit({
                            "type": "frame",
                            "data": base64.b64encode(encoded).decode("ascii"),
                            "message": "Tracking active",
                        })
            else:
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
    if ui_queue is None:
        cv2.destroyAllWindows()
    emit({"type": "status", "message": "Stopped"})


def main():
    run(AppConfig.load())


if __name__ == "__main__":
    main()
