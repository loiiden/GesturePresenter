from __future__ import annotations

import importlib.util
import multiprocessing as mp
import tkinter as tk
from tkinter import messagebox, ttk

from config import APP_NAME, AppConfig


def _tracking_process(config: AppConfig, stop_event) -> None:
    from hand_tracker import run
    run(config, stop_event)


class Launcher:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("540x470")
        self.root.minsize(500, 440)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.process = None
        self.stop_event = None

        saved = AppConfig.load()
        self.mode = tk.StringVar(value=saved.mode)
        self.voice = tk.BooleanVar(value=saved.voice_enabled)
        self.camera = tk.IntVar(value=saved.camera_index)
        self.display = tk.IntVar(value=saved.display_index)
        self.mirror = tk.BooleanVar(value=saved.mirror_camera)
        self.status = tk.StringVar(value="Ready")

        self._build()
        self.root.after(500, self._monitor)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=APP_NAME, font=("TkDefaultFont", 22, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Configure your controls before the camera starts.",
        ).pack(anchor="w", pady=(4, 22))

        settings = ttk.LabelFrame(outer, text="Session", padding=16)
        settings.pack(fill="x")
        self._row(settings, 0, "Mode", ttk.Combobox(
            settings, textvariable=self.mode, values=("presentation",), state="readonly"
        ))
        self._row(settings, 1, "Camera", ttk.Spinbox(
            settings, from_=0, to=9, textvariable=self.camera, width=8
        ))
        self._row(settings, 2, "Display", ttk.Spinbox(
            settings, from_=0, to=9, textvariable=self.display, width=8
        ))
        ttk.Checkbutton(settings, text="Mirror camera preview", variable=self.mirror).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(10, 2)
        )

        voice_box = ttk.LabelFrame(outer, text="Voice", padding=16)
        voice_box.pack(fill="x", pady=16)
        self.voice_check = ttk.Checkbutton(
            voice_box, text="Enable local speech-to-text (Whisper)", variable=self.voice
        )
        self.voice_check.pack(anchor="w")
        if not self._voice_available():
            self.voice.set(False)
            self.voice_check.configure(state="disabled")
            ttk.Label(
                voice_box,
                text="Voice package not installed. Gesture-only mode is fully available.",
                foreground="#777777",
            ).pack(anchor="w", pady=(5, 0))

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(8, 0))
        self.start_button = ttk.Button(controls, text="Start", command=self.start)
        self.start_button.pack(side="left", fill="x", expand=True)
        self.stop_button = ttk.Button(controls, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", fill="x", expand=True, padx=(10, 0))
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(14, 0))

    @staticmethod
    def _row(parent, row: int, label: str, widget) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        widget.grid(row=row, column=1, sticky="ew", padx=(20, 0), pady=5)
        parent.columnconfigure(1, weight=1)

    @staticmethod
    def _voice_available() -> bool:
        return all(importlib.util.find_spec(name) is not None
                   for name in ("faster_whisper", "sounddevice"))

    def _config(self) -> AppConfig:
        return AppConfig(
            mode=self.mode.get(), voice_enabled=self.voice.get(),
            camera_index=self.camera.get(), display_index=self.display.get(),
            mirror_camera=self.mirror.get(),
        )

    def start(self) -> None:
        if self.process and self.process.is_alive():
            return
        config = self._config()
        config.save()
        self.stop_event = mp.Event()
        self.process = mp.Process(
            target=_tracking_process, args=(config, self.stop_event), daemon=True
        )
        self.process.start()
        self.status.set("Tracking is running. Press Q in the camera window to stop.")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

    def stop(self) -> None:
        if self.stop_event:
            self.stop_event.set()
        self.status.set("Stopping…")

    def _monitor(self) -> None:
        if self.process and not self.process.is_alive():
            exit_code = self.process.exitcode
            self.process.join()
            self.process = None
            self.stop_event = None
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.status.set("Stopped" if exit_code == 0 else "Stopped with an error")
            if exit_code not in (0, None):
                messagebox.showerror(APP_NAME, "Tracking stopped unexpectedly. Check camera permissions.")
        self.root.after(500, self._monitor)

    def close(self) -> None:
        if self.stop_event:
            self.stop_event.set()
        if self.process:
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.terminate()
        self.root.destroy()


def main() -> None:
    mp.freeze_support()
    root = tk.Tk()
    Launcher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
