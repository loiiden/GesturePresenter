from __future__ import annotations

import importlib.util
import multiprocessing as mp
import time

import cv2
import numpy as np

from config import APP_NAME, AppConfig


WINDOW = APP_NAME
WIDTH, HEIGHT = 680, 590
BG = (30, 30, 34)
PANEL = (45, 45, 51)
TEXT = (242, 242, 247)
MUTED = (160, 160, 170)
ACCENT = (240, 135, 40)
GREEN = (85, 190, 100)
RED = (80, 90, 230)


def _tracking_process(config: AppConfig, stop_event) -> None:
    from hand_tracker import run
    run(config, stop_event)


class Launcher:
    """Dependency-free launcher rendered by OpenCV's native window backend."""

    def __init__(self):
        self.config = AppConfig.load()
        self.process = None
        self.stop_event = None
        self.status = "Ready — camera is off"
        self.voice_available = all(
            importlib.util.find_spec(name) is not None
            for name in ("faster_whisper", "sounddevice")
        )
        if not self.voice_available:
            self.config.voice_enabled = False
        self.hitboxes: dict[str, tuple[int, int, int, int]] = {}
        self._open_window()

    def _open_window(self) -> None:
        cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(WINDOW, self._on_mouse)

    @staticmethod
    def _text(image, value, x, y, scale=.62, color=TEXT, thickness=1) -> None:
        cv2.putText(image, value, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, color, thickness, cv2.LINE_AA)

    def _button(self, image, key, label, rect, enabled=True, active=False) -> None:
        x1, y1, x2, y2 = rect
        color = ACCENT if active else ((70, 70, 78) if enabled else (52, 52, 58))
        cv2.rectangle(image, (x1, y1), (x2, y2), color, -1, cv2.LINE_AA)
        cv2.rectangle(image, (x1, y1), (x2, y2), (100, 100, 110), 1, cv2.LINE_AA)
        size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, .55, 1)
        tx = x1 + (x2 - x1 - size[0]) // 2
        ty = y1 + (y2 - y1 + size[1]) // 2
        self._text(image, label, tx, ty, .55, TEXT if enabled else MUTED)
        if enabled:
            self.hitboxes[key] = rect

    def _stepper(self, image, key, label, value, y) -> None:
        self._text(image, label, 60, y + 27)
        self._button(image, key + "_minus", "−", (420, y, 465, y + 42))
        self._text(image, str(value), 500, y + 28, .68)
        self._button(image, key + "_plus", "+", (555, y, 600, y + 42))

    def render(self) -> np.ndarray:
        self.hitboxes.clear()
        image = np.full((HEIGHT, WIDTH, 3), BG, dtype=np.uint8)
        self._text(image, APP_NAME, 42, 58, 1.1, TEXT, 2)
        self._text(image, "Configure your session before starting the camera.",
                   43, 88, .52, MUTED)

        cv2.rectangle(image, (35, 115), (645, 365), PANEL, -1)
        self._text(image, "SESSION", 55, 145, .48, MUTED, 1)
        self._text(image, "Mode", 60, 190)
        self._button(image, "mode", "Presentation", (420, 160, 600, 202), active=True)
        self._stepper(image, "camera", "Camera", self.config.camera_index, 220)
        self._stepper(image, "display", "Display", self.config.display_index, 280)

        mirror_label = "Mirror preview: ON" if self.config.mirror_camera else "Mirror preview: OFF"
        self._button(image, "mirror", mirror_label, (55, 315, 285, 350),
                     active=self.config.mirror_camera)
        voice_label = "Voice: ON" if self.config.voice_enabled else "Voice: OFF"
        self._button(image, "voice", voice_label, (305, 315, 535, 350),
                     enabled=self.voice_available, active=self.config.voice_enabled)

        if not self.voice_available:
            self._text(image, "Voice components are not installed; gestures work normally.",
                       45, 397, .45, MUTED)
        else:
            self._text(image, "Voice is optional and Whisper loads only when enabled.",
                       45, 397, .45, MUTED)

        running = self.process is not None and self.process.is_alive()
        if running:
            self._button(image, "stop", "STOP TRACKING", (40, 435, 640, 500), active=False)
        else:
            self._button(image, "start", "START PRESENTATION", (40, 435, 640, 500), active=True)
        status_color = GREEN if running else MUTED
        if "error" in self.status.lower():
            status_color = RED
        self._text(image, self.status, 45, 540, .52, status_color)
        self._text(image, "Q / Esc closes this launcher", 45, 570, .42, MUTED)
        return image

    def _on_mouse(self, event, x, y, _flags, _param) -> None:
        if event != cv2.EVENT_LBUTTONUP:
            return
        key = next((name for name, (x1, y1, x2, y2) in self.hitboxes.items()
                    if x1 <= x <= x2 and y1 <= y <= y2), None)
        if key == "camera_minus":
            self.config.camera_index = max(0, self.config.camera_index - 1)
        elif key == "camera_plus":
            self.config.camera_index = min(9, self.config.camera_index + 1)
        elif key == "display_minus":
            self.config.display_index = max(0, self.config.display_index - 1)
        elif key == "display_plus":
            self.config.display_index = min(9, self.config.display_index + 1)
        elif key == "mirror":
            self.config.mirror_camera = not self.config.mirror_camera
        elif key == "voice" and self.voice_available:
            self.config.voice_enabled = not self.config.voice_enabled
        elif key == "start":
            self.start()
        elif key == "stop":
            self.stop()

    def start(self) -> None:
        if self.process and self.process.is_alive():
            return
        self.config.save()
        self.stop_event = mp.Event()
        self.process = mp.Process(
            target=_tracking_process, args=(self.config, self.stop_event), daemon=True
        )
        self.process.start()
        self.status = "Tracking is running"

    def stop(self) -> None:
        if self.stop_event:
            self.stop_event.set()
            self.status = "Stopping tracking…"

    def _monitor(self) -> None:
        if self.process and not self.process.is_alive():
            code = self.process.exitcode
            self.process.join()
            self.process = None
            self.stop_event = None
            self.status = "Stopped" if code == 0 else "Tracking error — check camera permissions"

    def run(self) -> None:
        while True:
            self._monitor()
            cv2.imshow(WINDOW, self.render())
            key = cv2.waitKey(30) & 0xFF
            if key in (ord("q"), 27):
                break
            try:
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
            except cv2.error:
                break
        self.close()

    def close(self) -> None:
        if self.stop_event:
            self.stop_event.set()
        if self.process:
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.terminate()
        cv2.destroyAllWindows()


def main() -> None:
    mp.freeze_support()
    Launcher().run()


if __name__ == "__main__":
    main()
