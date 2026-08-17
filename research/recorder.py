"""Guided gesture recorder — a development tool, not a shipped feature.

Run it with::

    uv run --extra research python -m research.recorder --participant P001 --session S01

This module is intentionally excluded from ``pyproject.toml``'s ``py-modules``
and from ``GesturePresenter.spec``, so it cannot end up inside the built
application. It exists only to produce ``research/data/*.csv``.

No video is written to disk. Only landmark coordinates leave the camera loop.

Design notes
------------
*Condition blocking.* Trials are grouped into condition blocks and shuffled
only within a block. Randomising across conditions would ask the recorder to
move nearer and further every few seconds, which is not physically practical
and produces mislabelled distance conditions.

*Quality gating.* Every frame is checked for detection confidence, distance
from the frame edge, and apparent hand size. A trial that does not yield enough
good frames is rejected and re-queued with the reason shown, rather than
quietly entering the dataset — the failure mode that spoiled the first
recording round.
"""
from __future__ import annotations

import argparse
import base64
import json
import queue
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from research.dataset import (
    SCHEMA_VERSION, append_rows, read_rows, rewrite_without_trials, summarize,
)

PROTOCOL_PATH = Path(__file__).with_name("protocol.json")
DEFAULT_OUTPUT = Path("research/data/gestures.csv")

# MediaPipe reports handedness for the image it was given. The recorder mirrors
# the frame (as the product does), which reverses the label, so the anatomical
# hand is the opposite of what MediaPipe reports.
_ANATOMICAL = {"Left": "Right", "Right": "Left"}


@dataclass
class Trial:
    index: int
    gesture: str
    condition: str
    hand: str
    repetition: int
    block: str

    def to_dict(self) -> dict:
        return {
            "index": self.index, "gesture": self.gesture, "condition": self.condition,
            "hand": self.hand, "repetition": self.repetition, "block": self.block,
        }


@dataclass
class FrameQuality:
    ok: bool
    reason: str = ""
    span: float = 0.0
    margin: float = 0.0
    score: float = 0.0


def build_plan(protocol: dict, seed: int | None) -> list[Trial]:
    """Condition-blocked trial order: shuffled inside a block, blocks in order."""
    rng = random.Random(seed)
    trials: list[Trial] = []
    gestures = protocol["gestures"]

    for condition in protocol["conditions"]:
        block = [
            (gesture, repetition + 1)
            for gesture in gestures
            for repetition in range(int(condition["repetitions"]))
        ]
        rng.shuffle(block)
        for gesture, repetition in block:
            trials.append(Trial(0, gesture, condition["id"], "Right", repetition,
                                f"right:{condition['id']}"))

    left = protocol.get("left_hand", {})
    if left.get("enabled"):
        for condition_id in left["conditions"]:
            block = [
                (gesture, repetition + 1)
                for gesture in left["gestures"]
                for repetition in range(int(left["repetitions"]))
            ]
            rng.shuffle(block)
            for gesture, repetition in block:
                trials.append(Trial(0, gesture, condition_id, "Left", repetition,
                                    f"left:{condition_id}"))

    for position, trial in enumerate(trials, 1):
        trial.index = position
    return trials


def assess(landmarks, score: float, quality: dict) -> FrameQuality:
    points = np.array([[lm.x, lm.y] for lm in landmarks], dtype=np.float64)
    lo, hi = points.min(axis=0), points.max(axis=0)
    span = float(np.hypot(*(hi - lo)))
    margin = float(min(lo.min(), (1.0 - hi).min()))
    if score < quality["min_handedness_score"]:
        return FrameQuality(False, "Low detection confidence", span, margin, score)
    if margin < quality["min_edge_margin"]:
        return FrameQuality(False, "Hand too close to the frame edge", span, margin, score)
    if span < quality["min_hand_span"]:
        return FrameQuality(False, "Hand too far from the camera", span, margin, score)
    if span > quality["max_hand_span"]:
        return FrameQuality(False, "Hand too close to the camera", span, margin, score)
    return FrameQuality(True, "", span, margin, score)


class RecorderWorker(threading.Thread):
    """Camera + MediaPipe loop driving the trial state machine."""

    def __init__(self, api: "RecorderApi", camera_index: int):
        super().__init__(daemon=True)
        self.api = api
        self.camera_index = camera_index
        self.stop_event = threading.Event()

    def run(self) -> None:
        try:
            self._loop()
        except Exception as exc:  # surfaced in the UI rather than the console
            self.api.set_error(f"{type(exc).__name__}: {exc}")
        finally:
            self.api.on_worker_finished()

    def _loop(self) -> None:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        from hand_tracker import MODEL_PATH, download_model

        if not Path(MODEL_PATH).exists():
            download_model()

        capture = cv2.VideoCapture(self.camera_index)
        if not capture.isOpened():
            raise RuntimeError(f"Could not open camera {self.camera_index}")

        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.6,
            min_tracking_confidence=0.6,
        )
        api = self.api
        api.set_status("Camera ready")
        frame_counter = 0

        with vision.HandLandmarker.create_from_options(options) as landmarker:
            while not self.stop_event.is_set():
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("Camera stopped returning frames")
                # Mirror to match the product's selfie-style preview, so the
                # recorded distribution matches what the app sees at inference.
                frame = cv2.flip(frame, 1)
                height, width = frame.shape[:2]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                    int(time.monotonic() * 1000),
                )
                api.process(result, width, height)
                self._draw(frame, result, api.snapshot_overlay())
                frame_counter += 1
                if frame_counter % 2 == 0:
                    api.publish_frame(frame)

        capture.release()

    @staticmethod
    def _draw(frame, result, overlay: dict) -> None:
        from hand_tracker import HAND_CONNECTIONS, FINGERTIP_IDS

        height, width = frame.shape[:2]
        colour = overlay.get("colour", (0, 220, 0))
        for landmarks in result.hand_landmarks:
            points = [(int(lm.x * width), int(lm.y * height)) for lm in landmarks]
            for a, b in HAND_CONNECTIONS:
                cv2.line(frame, points[a], points[b], colour, 2, cv2.LINE_AA)
            for index, point in enumerate(points):
                radius = 7 if index in FINGERTIP_IDS else 4
                cv2.circle(frame, point, radius, (255, 220, 0), -1, cv2.LINE_AA)
        if overlay.get("banner"):
            cv2.rectangle(frame, (0, 0), (width - 1, height - 1), colour, 6)


class RecorderApi:
    """State machine + JS bridge. All mutable state is guarded by ``_lock``."""

    def __init__(self, args, protocol: dict):
        self.args = args
        self.protocol = protocol
        self.quality = protocol["quality"]
        self.timing = protocol["timing"]
        self.output = args.output

        self._lock = threading.RLock()
        self._worker: RecorderWorker | None = None
        self._frame: str | None = None
        self._status = "Idle"
        self._error: str | None = None

        self.plan: list[Trial] = build_plan(protocol, args.seed)
        self.cursor = 0
        self.phase = "idle"          # idle|prompt|countdown|recording|saved|rejected|done
        self.paused = True
        self.phase_deadline = 0.0
        self.record_started = 0.0
        self.buffer: list[dict] = []
        self.good_frames = 0
        self.live_quality = FrameQuality(False, "No hand detected")
        self.last_result = ""
        self.saved_trials: list[dict] = []
        self.completed = 0
        self.commands: queue.Queue = queue.Queue()

    # ── JS API ────────────────────────────────────────────────────────────────

    def initial_state(self) -> dict:
        return {
            "protocol": {
                "gestures": self.protocol["gestures"],
                "instructions": self.protocol["instructions"],
                "actions": self.protocol["actions"],
                "conditions": self.protocol["conditions"],
                "timing": self.timing,
            },
            "participant": self.args.participant,
            "session": self.args.session,
            "output": str(self.output),
            "total": len(self.plan),
            "state": self.poll(),
        }

    def list_cameras(self) -> list[dict]:
        from devices import list_cameras
        return list_cameras()

    def start(self, camera_index: int) -> dict:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return {"ok": True}
            self._error = None
            self.phase = "prompt"
            self.paused = True
            self._worker = RecorderWorker(self, int(camera_index))
            self._worker.start()
            self._status = "Starting camera…"
        return {"ok": True}

    def stop(self) -> dict:
        with self._lock:
            if self._worker:
                self._worker.stop_event.set()
            self.phase = "idle"
        return {"ok": True}

    def command(self, name: str) -> dict:
        """UI actions: resume, pause, skip, redo, delete_last, jump."""
        self.commands.put(name)
        return {"ok": True}

    def delete_trial(self, trial_id: str) -> dict:
        removed = rewrite_without_trials(self.output, {trial_id})
        with self._lock:
            self.saved_trials = [t for t in self.saved_trials if t["trial_id"] != trial_id]
            self.completed = max(0, self.completed - 1)
            self.last_result = f"Deleted {trial_id} ({removed} frames)"
        return {"ok": True, "removed": removed}

    def dataset_summary(self) -> dict:
        try:
            return summarize(read_rows([self.output]))
        except SystemExit:
            return {"frames": 0, "trials": 0, "per_gesture": {}, "per_condition": {},
                    "per_hand": {}, "per_pair": {}, "sessions": []}

    def poll(self) -> dict:
        with self._lock:
            self._pump_commands()
            frame, self._frame = self._frame, None
            trial = self.plan[self.cursor] if self.cursor < len(self.plan) else None
            remaining = max(0.0, self.phase_deadline - time.monotonic())
            return {
                "phase": self.phase,
                "paused": self.paused,
                "status": self._status,
                "error": self._error,
                "frame": frame,
                "remaining": round(remaining, 2),
                "trial": trial.to_dict() if trial else None,
                "instruction": self.protocol["instructions"].get(trial.gesture, "") if trial else "",
                "conditionText": self._condition_text(trial) if trial else "",
                "cursor": self.cursor,
                "total": len(self.plan),
                "completed": self.completed,
                "goodFrames": self.good_frames,
                "quality": {
                    "ok": self.live_quality.ok, "reason": self.live_quality.reason,
                    "span": round(self.live_quality.span, 3),
                    "margin": round(self.live_quality.margin, 3),
                    "score": round(self.live_quality.score, 3),
                },
                "lastResult": self.last_result,
                "recent": self.saved_trials[-8:][::-1],
            }

    def shutdown(self) -> None:
        self.stop()
        if self._worker:
            self._worker.join(timeout=2)

    # ── Worker-facing helpers ────────────────────────────────────────────────

    def set_status(self, message: str) -> None:
        with self._lock:
            self._status = message

    def set_error(self, message: str) -> None:
        with self._lock:
            self._error = message
            self.phase = "idle"

    def on_worker_finished(self) -> None:
        with self._lock:
            self._status = "Camera stopped"
            if self.phase != "idle":
                self.phase = "idle"

    def publish_frame(self, frame) -> None:
        if frame.shape[1] > 720:
            scale = 720 / frame.shape[1]
            frame = cv2.resize(frame, None, fx=scale, fy=scale)
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            with self._lock:
                self._frame = "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")

    def snapshot_overlay(self) -> dict:
        with self._lock:
            if self.phase == "recording":
                colour = (80, 220, 120) if self.live_quality.ok else (60, 60, 235)
                return {"colour": colour, "banner": True}
            if self.phase == "countdown":
                return {"colour": (60, 200, 250), "banner": True}
            return {"colour": (200, 200, 200), "banner": False}

    # ── State machine ────────────────────────────────────────────────────────

    def _condition_text(self, trial: Trial) -> str:
        for condition in self.protocol["conditions"]:
            if condition["id"] == trial.condition:
                return condition["instruction"]
        return self.protocol.get("left_hand", {}).get("note", "")

    def _pump_commands(self) -> None:
        while True:
            try:
                name = self.commands.get_nowait()
            except queue.Empty:
                return
            if name == "resume":
                self.paused = False
                if self.phase in ("prompt", "saved", "rejected"):
                    self._begin_countdown()
            elif name == "pause":
                self.paused = True
                if self.phase in ("countdown", "recording"):
                    self._abort_trial("Paused")
            elif name == "skip":
                self._advance(saved=False)
            elif name == "redo":
                self._abort_trial("Retaking")
                self._begin_countdown()
            elif name == "delete_last" and self.saved_trials:
                self.delete_trial(self.saved_trials[-1]["trial_id"])

    def _begin_countdown(self) -> None:
        self.buffer = []
        self.good_frames = 0
        self.phase = "countdown"
        self.phase_deadline = time.monotonic() + float(self.timing["countdown_seconds"])

    def _abort_trial(self, reason: str) -> None:
        self.buffer = []
        self.good_frames = 0
        self.phase = "prompt"
        self.last_result = reason

    def _advance(self, saved: bool) -> None:
        self.cursor += 1
        self.buffer = []
        self.good_frames = 0
        if self.cursor >= len(self.plan):
            self.phase = "done"
            self.paused = True
            return
        if saved:
            # Hold on "saved" for the rest interval; ``process`` moves on to the
            # next countdown once the deadline passes and recording is running.
            self.phase = "saved"
            self.phase_deadline = time.monotonic() + float(self.timing["rest_seconds"])
        elif self.paused:
            self.phase = "prompt"
        else:
            self._begin_countdown()

    def process(self, result, width: int, height: int) -> None:
        """Called once per camera frame from the worker thread."""
        with self._lock:
            if self.cursor >= len(self.plan):
                self.phase = "done"
                return
            trial = self.plan[self.cursor]
            match = self._select_hand(result, trial.hand)
            self.live_quality = (
                assess(match[0], match[1], self.quality) if match
                else FrameQuality(False, f"No {trial.hand.lower()} hand detected")
            )

            now = time.monotonic()
            if self.phase == "countdown" and now >= self.phase_deadline:
                self.phase = "recording"
                self.record_started = now
                self.phase_deadline = now + float(self.timing["record_seconds"])
                self.buffer = []
                self.good_frames = 0

            if self.phase == "recording":
                if match and self.live_quality.ok:
                    self.buffer.append(self._row(trial, match, width, height, now))
                    self.good_frames += 1
                if now >= self.phase_deadline:
                    self._finish_recording(trial)

            elif self.phase in ("saved", "rejected") and now >= self.phase_deadline:
                if self.paused:
                    self.phase = "prompt"
                else:
                    self._begin_countdown()

    def _select_hand(self, result, wanted: str):
        """Return (landmarks, score, world_landmarks) for the requested anatomical hand."""
        for index, landmarks in enumerate(result.hand_landmarks):
            category = result.handedness[index][0]
            anatomical = _ANATOMICAL.get(category.category_name, category.category_name)
            if anatomical == wanted:
                world = (result.hand_world_landmarks[index]
                         if index < len(result.hand_world_landmarks) else None)
                return landmarks, float(category.score), world
        return None

    def _row(self, trial: Trial, match, width: int, height: int, now: float) -> dict:
        landmarks, score, world = match
        row = {
            "schema_version": SCHEMA_VERSION,
            "participant_id": self.args.participant,
            "session_id": self.args.session,
            "trial_id": f"{self.args.session}-{trial.index:04d}",
            "gesture": trial.gesture,
            "condition": trial.condition,
            "hand": trial.hand,
            "frame_index": len(self.buffer),
            "timestamp_ms": int((now - self.record_started) * 1000),
            "frame_width": width,
            "frame_height": height,
            "mp_handedness": _ANATOMICAL.get(trial.hand, trial.hand),
            "handedness_score": round(score, 4),
            "hand_span": round(self.live_quality.span, 5),
            "edge_margin": round(self.live_quality.margin, 5),
        }
        for index, lm in enumerate(landmarks):
            row[f"x{index}"] = round(lm.x, 6)
            row[f"y{index}"] = round(lm.y, 6)
            row[f"z{index}"] = round(lm.z, 6)
        for index in range(21):
            lm = world[index] if world is not None else None
            row[f"wx{index}"] = round(lm.x, 6) if lm is not None else 0.0
            row[f"wy{index}"] = round(lm.y, 6) if lm is not None else 0.0
            row[f"wz{index}"] = round(lm.z, 6) if lm is not None else 0.0
        return row

    def _finish_recording(self, trial: Trial) -> None:
        minimum = int(self.quality["min_frames"])
        if self.good_frames < minimum:
            # Re-queue rather than accept: a thin trial is exactly the kind of
            # sample that poisons a small dataset.
            self.phase = "rejected"
            self.phase_deadline = time.monotonic() + 1.4
            self.last_result = (
                f"Rejected — only {self.good_frames}/{minimum} usable frames "
                f"({self.live_quality.reason or 'hand lost'}). Repeating."
            )
            self.buffer = []
            return

        append_rows(self.output, self.buffer)
        trial_id = self.buffer[0]["trial_id"]
        self.saved_trials.append({
            "trial_id": trial_id, "gesture": trial.gesture,
            "condition": trial.condition, "hand": trial.hand,
            "frames": len(self.buffer),
        })
        self.completed += 1
        self.last_result = f"Saved {trial.gesture} ({len(self.buffer)} frames)"
        self._advance(saved=True)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Guided gesture dataset recorder")
    parser.add_argument("--participant", required=True, help="Pseudonymous ID, e.g. P001")
    parser.add_argument("--session", required=True, help="Session ID, e.g. S01")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args(argv)


def main(argv=None) -> None:
    import webview

    args = parse_args(argv)
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if int(protocol["schema_version"]) != SCHEMA_VERSION:
        raise SystemExit(
            f"Protocol targets schema v{protocol['schema_version']}, "
            f"recorder writes v{SCHEMA_VERSION}"
        )
    api = RecorderApi(args, protocol)
    page = Path(__file__).with_name("recorder_frontend") / "index.html"
    window = webview.create_window(
        f"Gesture Recorder — {args.participant} / {args.session}",
        page.as_uri(), js_api=api, width=1180, height=820,
        min_size=(940, 700), background_color="#0f1115",
    )
    window.events.closed += api.shutdown
    webview.start()


if __name__ == "__main__":
    sys.exit(main())
