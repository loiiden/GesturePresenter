from __future__ import annotations

import importlib.util
import multiprocessing as mp
import queue
import sys
from dataclasses import asdict
from pathlib import Path

import webview

from config import APP_NAME, AppConfig
from devices import list_cameras, list_displays


def _tracking_process(config: AppConfig, stop_event, ui_queue) -> None:
    try:
        from hand_tracker import run
        run(config, stop_event, ui_queue)
    except Exception as exc:
        ui_queue.put({"type": "error", "message": str(exc)})
        raise


class AppApi:
    """Small, explicit API exposed to the JavaScript application."""

    def __init__(self):
        self.config = AppConfig.load()
        self.process = None
        self.stop_event = None
        self.ui_queue = None
        self.frame = None
        self.message = "Ready — camera is off"
        self.error = None
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
            "message": self.message,
            "devices": self.refresh_devices(),
        }

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
        if self._running():
            return {"ok": True}
        self.save_config(values)
        self.stop_event = mp.Event()
        self.ui_queue = mp.Queue(maxsize=3)
        self.frame = None
        self.error = None
        self.process = mp.Process(
            target=_tracking_process,
            args=(self.config, self.stop_event, self.ui_queue),
            daemon=True,
        )
        self.process.start()
        self.message = "Starting camera…"
        return {"ok": True}

    def stop_tracking(self) -> dict:
        if self.stop_event:
            self.stop_event.set()
            self.message = "Stopping…"
        return {"ok": True}

    def poll(self) -> dict:
        self._drain_events()
        if self.process and not self.process.is_alive():
            code = self.process.exitcode
            self.process.join()
            self.process = None
            self.stop_event = None
            if code and not self.error:
                self.error = "Tracking stopped unexpectedly. Check camera permissions."
            if not self.error:
                self.message = "Stopped"
        frame, self.frame = self.frame, None
        return {
            "running": self._running(),
            "message": self.message,
            "error": self.error,
            "frame": frame,
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
                elif kind == "status":
                    self.message = event["message"]
                elif kind == "error":
                    self.error = event["message"]
        except queue.Empty:
            pass

    def _running(self) -> bool:
        return bool(self.process and self.process.is_alive())

    def shutdown(self) -> None:
        if self.stop_event:
            self.stop_event.set()
        if self.process:
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.terminate()


def main() -> None:
    mp.freeze_support()
    api = AppApi()
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    page = bundle_dir / "frontend" / "index.html"
    window = webview.create_window(
        APP_NAME, page.as_uri(), js_api=api, width=1100, height=760,
        min_size=(860, 620), background_color="#0b1020",
    )
    window.events.closed += api.shutdown
    webview.start(debug=False)


if __name__ == "__main__":
    main()
