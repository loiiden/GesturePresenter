"""
Floating always-on-top overlay for speech-to-text feedback.
root  = camera debug window (always visible, never withdrawn)
_ovl  = speech overlay Toplevel (shown/hidden per state)
Both live on the main thread; public API is thread-safe via queues.

macOS note: borderless (overrideredirect) Toplevels are broken on macOS Tk —
they render blank/transparent or never appear, and alpha tricks don't help.
So the overlay is a *normal* decorated Toplevel: it has a small title bar but
it reliably shows. withdraw()/deiconify() works correctly on decorated windows
(the re-map bug is specific to borderless ones).
"""
import queue
import tkinter as tk
from PIL import Image, ImageTk

WIDTH  = 640
HEIGHT = 130
BG     = "#1c1c1e"
FG     = "#ffffff"
HINT   = "#8e8e93"


class Overlay:
    def __init__(self):
        self._q     = queue.Queue()
        self._cam_q = queue.Queue(maxsize=2)
        self._dot_state = 0

    # ── Public API (call from any thread) ────────────────────────────────────

    def show_recording(self):
        self._q.put(("recording", None))

    def show_transcribing(self):
        self._q.put(("transcribing", None))

    def show_result(self, text: str):
        self._q.put(("result", text))

    def hide(self):
        self._q.put(("hide", None))

    def push_frame(self, bgr_frame):
        """Camera thread: enqueue a BGR numpy frame. Drops if slow."""
        try:
            self._cam_q.put_nowait(bgr_frame)
        except queue.Full:
            pass

    # ── Main-thread entry point ───────────────────────────────────────────────

    def run(self):
        """Block the calling (main) thread on the tkinter event loop."""
        # Root window = camera feed (must stay visible so macOS keeps the app alive)
        self._root = tk.Tk()
        self._root.title("Hand Tracker")
        self._root.resizable(False, False)
        self._cam_label = tk.Label(self._root, bg="black")
        self._cam_label.pack()
        self._cam_photo = None

        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()

        # Speech overlay = normal decorated Toplevel (reliable on macOS).
        self._ovl = tk.Toplevel(self._root)
        self._ovl.title("Speech")
        self._ovl.resizable(False, False)
        self._ovl.attributes("-topmost", True)
        self._ovl.configure(bg=BG)
        x = (sw - WIDTH)  // 2
        y = (sh - HEIGHT) // 2 - 60
        self._ovl.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")
        # Closing the overlay window should not kill the app — just hide it.
        self._ovl.protocol("WM_DELETE_WINDOW", self._hide_ovl)
        self._ovl.withdraw()

        self._status_var = tk.StringVar()
        self._text_var   = tk.StringVar()

        tk.Label(self._ovl, textvariable=self._status_var,
                 fg=HINT, bg=BG,
                 font=("Helvetica Neue", 12)).pack(pady=(14, 2))

        tk.Label(self._ovl, textvariable=self._text_var,
                 fg=FG, bg=BG,
                 font=("Helvetica Neue", 17),
                 wraplength=WIDTH - 40,
                 justify="center").pack(pady=(2, 14))

        self._root.bind_all("<Escape>", lambda _: self._root.destroy())
        self._root.after(50, self._poll)
        self._root.after(33, self._poll_cam)
        self._root.mainloop()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _show_ovl(self):
        self._ovl.deiconify()
        self._ovl.lift()
        self._ovl.attributes("-topmost", True)

    def _hide_ovl(self):
        self._ovl.withdraw()

    def _poll(self):
        try:
            while True:
                cmd, data = self._q.get_nowait()
                if cmd == "recording":
                    self._status_var.set("● Recording…")
                    self._text_var.set("")
                    self._show_ovl()
                    self._animate_dot()
                elif cmd == "transcribing":
                    self._status_var.set("◌ Transcribing…")
                    self._show_ovl()
                elif cmd == "result":
                    self._status_var.set("Fist+thumb up → paste   ·   Fist → cancel")
                    self._text_var.set(data or "(nothing heard)")
                    self._show_ovl()
                elif cmd == "hide":
                    self._hide_ovl()
        except queue.Empty:
            pass
        self._root.after(50, self._poll)

    def _poll_cam(self):
        try:
            frame = self._cam_q.get_nowait()
            img = Image.fromarray(frame[:, :, ::-1])
            self._cam_photo = ImageTk.PhotoImage(image=img)
            self._cam_label.config(image=self._cam_photo)
        except queue.Empty:
            pass
        except Exception as e:
            print(f"[cam] display error: {e}")
        self._root.after(33, self._poll_cam)

    def _animate_dot(self):
        current = self._status_var.get()
        if "Recording" not in current:
            return
        dots = ["● Recording…", "○ Recording…"]
        self._dot_state = 1 - self._dot_state
        self._status_var.set(dots[self._dot_state])
        self._root.after(500, self._animate_dot)
