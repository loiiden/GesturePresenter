from __future__ import annotations

import importlib.util
import queue
import sys
import threading
from dataclasses import asdict
from pathlib import Path

import webview

from config import APP_NAME, AppConfig
from devices import list_cameras, list_displays
from permissions import request_accessibility_permission, request_camera_permission


def _tracking_worker(config: AppConfig, stop_event, ui_queue) -> None:
    try:
        from hand_tracker import run
        run(config, stop_event, ui_queue)
    except Exception as exc:
        ui_queue.put({"type": "error", "message": str(exc)})


class AppApi:
    """Small, explicit API exposed to the JavaScript application."""

    def __init__(self):
        self.config = AppConfig.load()
        self.worker = None
        self.phase = "idle"
        self.lifecycle_lock = threading.RLock()
        self.stop_event = None
        self.ui_queue = None
        self.frame = None
        self.message = "Ready — camera is off"
        self.error = None
        self.engine_ready = threading.Event()
        self.engine_error = None
        threading.Thread(target=self._preload_engine, daemon=True).start()
        self.voice_available = all(
            importlib.util.find_spec(name) is not None
            for name in ("faster_whisper", "sounddevice")
        )
        if not self.voice_available:
            self.config.voice_enabled = False

    def initial_state(self) -> dict:
        return {
            "config": asdict(self.config),
            "voiceAvailable": self.voice_available,
            "running": self._running(),
            "phase": self.phase,
            "message": self.message,
            "engineReady": self.engine_ready.is_set(),
            "engineError": self.engine_error,
        }

    def _preload_engine(self) -> None:
        try:
            import hand_tracker  # noqa: F401 — warm expensive native imports
            self.engine_ready.set()
        except Exception as exc:
            self.engine_error = f"Tracking engine could not load: {exc}"

    def refresh_devices(self) -> dict:
        return {"cameras": list_cameras(), "displays": list_displays()}

    def save_config(self, values: dict) -> dict:
        allowed = AppConfig.__dataclass_fields__
        current = asdict(self.config)
        current.update({key: value for key, value in values.items() if key in allowed})
        self.config = AppConfig(**current)
        if not self.voice_available:
            self.config.voice_enabled = False
        self.config.save()
        return asdict(self.config)

    def start_tracking(self, values: dict) -> dict:
        with self.lifecycle_lock:
            if self.phase in ("starting", "running"):
                return {"ok": True, "phase": self.phase}
            if self.phase == "stopping":
                return {"ok": False, "phase": self.phase,
                        "error": "Tracking is still stopping. Please wait."}
        if self.engine_error:
            return {"ok": False, "error": self.engine_error}
        if not self.engine_ready.is_set():
            return {"ok": False, "error": "The tracking engine is still preparing. Please try again shortly."}
        try:
            self.save_config(values)
        except Exception as exc:
            self.error = f"Could not save settings: {exc}"
            return {"ok": False, "error": self.error}
        allowed, permission_error = request_camera_permission()
        if not allowed:
            self.error = permission_error
            self.message = "Camera permission required"
            return {"ok": False, "error": permission_error}
        allowed, permission_error = request_accessibility_permission()
        if not allowed:
            self.error = permission_error
            self.message = "Accessibility permission required"
            return {"ok": False, "error": permission_error}
        self.stop_event = threading.Event()
        self.ui_queue = queue.Queue(maxsize=3)
        self.frame = None
        self.error = None
        self.worker = threading.Thread(
            target=_tracking_worker,
            args=(self.config, self.stop_event, self.ui_queue),
            daemon=True,
        )
        self.phase = "starting"
        self.worker.start()
        self.message = "Starting camera…"
        return {"ok": True, "phase": self.phase}

    def stop_tracking(self) -> dict:
        with self.lifecycle_lock:
            if self.phase == "idle":
                return {"ok": True, "phase": self.phase}
            if self.stop_event:
                self.stop_event.set()
            self.phase = "stopping"
            self.message = "Stopping camera…"
            return {"ok": True, "phase": self.phase}

    def poll(self) -> dict:
        self._drain_events()
        if self.worker and not self.worker.is_alive():
            self.worker.join()
            self.worker = None
            self.stop_event = None
            self.phase = "idle"
            if not self.error:
                self.message = "Stopped"
        frame, self.frame = self.frame, None
        return {
            "running": self._running(),
            "phase": self.phase,
            "message": self.message,
            "error": self.error,
            "frame": frame,
            "engineReady": self.engine_ready.is_set(),
            "engineError": self.engine_error,
        }

    def _drain_events(self) -> None:
        if not self.ui_queue:
            return
        try:
            while True:
                event = self.ui_queue.get_nowait()
                kind = event.get("type")
                if kind == "frame":
                    self.frame = "data:image/jpeg;base64," + event["data"]
                    self.message = event.get("message", "Tracking active")
                    if self.phase != "stopping":
                        self.phase = "running"
                elif kind == "status":
                    self.message = event["message"]
                    if event["message"].startswith("Camera active") and self.phase != "stopping":
                        self.phase = "running"
                elif kind == "error":
                    self.error = event["message"]
        except queue.Empty:
            pass

    def _running(self) -> bool:
        return bool(self.worker and self.worker.is_alive())

    def shutdown(self) -> None:
        if self.stop_event:
            self.stop_event.set()
        if self.worker:
            self.worker.join(timeout=2)


def main() -> None:
    api = AppApi()
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    page = bundle_dir / "frontend" / "index.html"
    window = webview.create_window(
        APP_NAME, page.as_uri(), js_api=api, width=1100, height=760,
        min_size=(860, 620), background_color="#f5f5f7",
    )
    window.events.closed += api.shutdown
    webview.start(debug=False)


if __name__ == "__main__":
    main()
