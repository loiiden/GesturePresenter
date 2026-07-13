from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from hand_tracker import MODEL_PATH, draw_hand
from gestures import Gesture
from research.dataset import append_rows
from research.features import SCHEMA_VERSION


def parse_args():
    parser = argparse.ArgumentParser(description="Guided, landmark-only gesture collector")
    parser.add_argument("--participant", required=True, help="Pseudonymous ID, e.g. P001")
    parser.add_argument("--session", required=True, help="Session ID, e.g. S01")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--protocol", type=Path, default=Path(__file__).with_name("protocol.json"))
    parser.add_argument("--output", type=Path, default=Path("research/data/landmarks.csv"))
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args()


def overlay(frame, lines: list[str], color=(255, 255, 255)):
    shade = frame.copy()
    cv2.rectangle(shade, (0, 0), (frame.shape[1], 145), (15, 15, 15), -1)
    cv2.addWeighted(shade, 0.72, frame, 0.28, 0, frame)
    for index, line in enumerate(lines):
        cv2.putText(frame, line, (20, 35 + index * 32), cv2.FONT_HERSHEY_SIMPLEX,
                    0.68, color if index == 0 else (225, 225, 225), 2, cv2.LINE_AA)


def landmark_row(args, trial_id, gesture, frame_index, elapsed_ms, hand_lms, category):
    # Collection uses a selfie-style mirrored frame, which reverses MediaPipe's
    # handedness label. Store the participant's anatomical hand in metadata.
    handedness = {"Left": "Right", "Right": "Left"}.get(
        category.category_name, category.category_name
    )
    row = {
        "schema_version": SCHEMA_VERSION, "participant_id": args.participant,
        "session_id": args.session, "trial_id": trial_id, "gesture": gesture,
        "frame_index": frame_index, "timestamp_ms": elapsed_ms,
        "handedness": handedness, "handedness_score": category.score,
    }
    for index, lm in enumerate(hand_lms):
        row.update({f"x{index}": lm.x, f"y{index}": lm.y, f"z{index}": lm.z})
    return row


def main():
    args = parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    trials = [(gesture, repetition + 1) for gesture in protocol["gestures"]
              for repetition in range(protocol["repetitions"])]
    random.Random(args.seed).shuffle(trials)

    if not Path(MODEL_PATH).exists():
        raise SystemExit(f"MediaPipe model not found: {MODEL_PATH}")
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera {args.camera}")
    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO, num_hands=1,
        min_hand_detection_confidence=0.7, min_tracking_confidence=0.7,
    )
    cv2.namedWindow("Research dataset collector", cv2.WINDOW_AUTOSIZE)
    saved_trials = 0
    try:
        with vision.HandLandmarker.create_from_options(options) as landmarker:
            for trial_number, (gesture, repetition) in enumerate(trials, 1):
                instruction = protocol["instructions"].get(gesture, gesture)
                while True:  # retry loop
                    rows, detected = [], 0
                    phases = [
                        ("GET READY", float(protocol["countdown_seconds"]), False),
                        ("RECORDING", float(protocol["record_seconds"]), True),
                        ("RELAX", float(protocol["rest_seconds"]), False),
                    ]
                    retry = quit_now = False
                    for phase, duration, recording in phases:
                        started = time.monotonic()
                        frame_index = 0
                        while time.monotonic() - started < duration:
                            ok, frame = cap.read()
                            if not ok:
                                raise RuntimeError("Camera stopped returning frames")
                            frame = cv2.flip(frame, 1)
                            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            result = landmarker.detect_for_video(
                                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                                int(time.monotonic() * 1000),
                            )
                            if result.hand_landmarks:
                                detected += int(recording)
                                draw_hand(frame, result.hand_landmarks[0], Gesture.NONE)
                                if recording:
                                    rows.append(landmark_row(
                                        args, f"{args.session}-{trial_number:04d}", gesture,
                                        frame_index, int((time.monotonic() - started) * 1000),
                                        result.hand_landmarks[0], result.handedness[0][0],
                                    ))
                            remaining = max(0.0, duration - (time.monotonic() - started))
                            overlay(frame, [
                                f"{phase}: {gesture.upper()} ({remaining:.1f}s)", instruction,
                                f"Trial {trial_number}/{len(trials)} | q quit | r retry",
                                "LANDMARKS ONLY - VIDEO IS NOT SAVED",
                            ], (80, 220, 120) if recording else (255, 210, 80))
                            cv2.imshow("Research dataset collector", frame)
                            key = cv2.waitKey(1) & 0xFF
                            if key == ord("q"):
                                quit_now = True
                                break
                            if key == ord("r"):
                                retry = True
                                break
                            frame_index += 1
                        if retry or quit_now:
                            break
                    if quit_now:
                        print(f"Stopped after {saved_trials} saved trials.")
                        return
                    if retry or not rows:
                        print(f"Retrying {gesture}: no usable frames or retry requested")
                        continue
                    append_rows(args.output, rows)
                    saved_trials += 1
                    print(f"Saved trial {trial_number}/{len(trials)}: {gesture} ({len(rows)} frames)")
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    print(f"Complete: {saved_trials} trials written to {args.output}")


if __name__ == "__main__":
    main()
