# Gesture Presenter

Gesture Presenter is a desktop presentation controller with a web-technology UI
and a Python/MediaPipe tracking engine.
Opening the application shows configuration first; the camera starts only after
you press **Start**. Voice recognition is optional, and gesture-only mode does
not import or load Whisper.

## Application flow

1. Open Gesture Presenter from your applications menu.
2. Select the camera and display.
3. Optionally enable local speech-to-text if the voice component is installed.
4. Press **Start** to activate the camera and presentation controls.
5. Press **Stop**, `Q`, or Escape to finish the session.

Settings are saved in the standard per-user configuration folder for macOS,
Windows, or Linux and restored the next time the app starts.

## Presentation controls

| Hand | Gesture | Action |
|---|---|---|
| Right | Isolated index finger | Move presentation pointer |
| Right | Thumb + index pinch and release | Left click |
| Right | Thumb + middle pinch | Right click |
| Right | Index + middle held together, move vertically | Scroll |
| Right | Open-palm horizontal swipe | Previous/next slide |
| Right | Held fist | Toggle black screen |
| Right | Thumb up | Play/pause media |
| Right | Held V sign | Mission Control/task overview |
| **Left** | **Thumb + index pinch and release** | **Left click — same as the right hand** |
| Left | Held open palm | Lock/unlock gesture controls |
| Left | Hold fist and speak, then release | Transcribe and paste automatically |

Either hand can click. Pinching with the pointing hand moves the index fingertip
— the landmark the pointer follows — so the cursor drifts as you click.
Pinching with the left hand instead leaves the pointer where you aimed it.
Pinching with both at once is still one click.

A pinch requires the fingertips to actually touch, so bringing the thumb near
the finger without contact does not click.

Press `L` to lock or unlock controls from the keyboard.

## Gesture recognition

Poses are classified by a small neural network trained on recorded hand
landmarks, not by hand-written geometric rules. On a recording session held out
of training entirely it reaches 0.99 trial accuracy, against 0.80 for the rules
it replaced; the largest gains are on "no gesture" and on thumb-out fists, the
two cases where the old rules misfired into unwanted actions.

Recognition is designed to survive a change of room and camera:

- **Camera shape** is corrected, because MediaPipe scales x by frame width and y
  by frame height separately, stretching a hand by ~1.78x on a 16:9 camera.
- **Distance from the camera** cancels out exactly: coordinates are scaled by
  the palm's own size, which does not change as fingers move.
- **Both hands share one model.** A left hand is mirrored into the right hand's
  frame before classification.

The model ships as a 129 KB file read with NumPy, so the application does not
depend on any machine-learning framework at runtime.

Recording your own gestures and retraining are development tasks, documented
separately in [`research/README.md`](research/README.md). Nothing in `research/`
is part of the installed application.

## Install and run (from source)

Runs on macOS, Windows, and Linux. Decide **what** to install (your
configuration), then copy the command for **your OS**. [**uv**](https://docs.astral.sh/uv/)
is the recommended installer; a plain-`pip` path is given afterwards.

### Step 1 — Choose your configuration

Optional features are installed as *extras*, combined with commas (e.g.
`[gui-qt,voice]`):

| Extra | Adds | Who needs it |
|---|---|---|
| *(none)* | Hand-gesture control | Everyone — this is the baseline |
| `voice` | Local speech-to-text (Whisper) for the fist-and-speak gesture | Optional |
| `gui-qt` | Qt window backend for pywebview | **Required on Linux only** |

- **macOS / Windows:** the OS provides the window backend — use *(none)* for
  gestures only, or `voice` to add speech-to-text.
- **Linux:** always include `gui-qt` (a uv/venv Python can't use the system GTK
  backend — see [Why `gui-qt` on Linux](#why-gui-qt-is-required-on-linux)). Add
  `voice` as well if you want speech.

### Step 2 — Install with uv (recommended)

uv downloads a compatible Python (3.10–3.12) for you, so you never install or
match Python yourself. This is what makes it work on newer distros (**Ubuntu
26**, recent Fedora/Arch) that ship Python **3.13+**, which some dependencies
don't support yet.

**1. Install uv** (no admin rights):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh                                    # macOS / Linux
```
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows
```
Restart your shell so `uv` is on the `PATH`.

**2. Install the app** from GitHub — pick the line for your OS and configuration:

```bash
# ── macOS / Windows ────────────────────────────────────────────────
# Gestures only
uv tool install git+https://github.com/loiiden/GesturePresenter.git
# Gestures + voice
uv tool install "gesture-presenter[voice] @ git+https://github.com/loiiden/GesturePresenter.git"

# ── Linux (always include gui-qt) ──────────────────────────────────
# Gestures only
uv tool install "gesture-presenter[gui-qt] @ git+https://github.com/loiiden/GesturePresenter.git"
# Gestures + voice
uv tool install "gesture-presenter[gui-qt,voice] @ git+https://github.com/loiiden/GesturePresenter.git"
```

**3. Run it:**

```bash
gesture-presenter
```

> **Changing configuration later?** If the tool is already installed, add
> `--force` to reinstall with different extras — e.g.
> `uv tool install --force "gesture-presenter[voice] @ git+…"`.

### Alternative — from a clone (for development)

```bash
git clone https://github.com/loiiden/GesturePresenter.git
cd GesturePresenter

uv run gesture-presenter                               # macOS / Windows, gestures only
uv run --extra voice gesture-presenter                 # macOS / Windows + voice
uv run --extra gui-qt gesture-presenter                # Linux
uv run --extra gui-qt --extra voice gesture-presenter  # Linux + voice
```

### Alternative — plain pip (if you already have Python 3.10–3.12)

```bash
git clone https://github.com/loiiden/GesturePresenter.git
cd GesturePresenter
python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .\.venv\Scripts\Activate.ps1
```

Then install your configuration and run (reactivate the venv each time before
running):

```bash
pip install -e .              # gestures only (macOS / Windows)
pip install -e ".[voice]"     # + voice
pip install -e ".[gui-qt]"    # Linux  (Linux + voice: ".[gui-qt,voice]")
gesture-presenter
```

### System dependencies

- **macOS / Windows:** none. Audio (PortAudio) ships inside the Python wheels and
  the window backend is built into the OS.
- **Linux:** install the non-Python libraries with apt:
  ```bash
  sudo apt install -y libgl1 libglib2.0-0 libxcb-cursor0   # camera + Qt window
  sudo apt install -y portaudio19-dev libportaudio2        # only if using voice
  ```
  Input control uses X11, so run in an **Xorg session**, not Wayland (log out →
  ⚙️ → *"Ubuntu on Xorg"*). Verify with `echo $XDG_SESSION_TYPE` → should print
  `x11`.

### Enabling voice

The `voice` extra installs the packages; the **Whisper model downloads on first
use** (~0.5 GB, cached in `~/.cache/huggingface`). To use it:

1. Launch the app — the speech-to-text toggle appears **only** when the `voice`
   packages are installed.
2. Enable that toggle on the config screen, then press **Start**.
3. Hold a **left-hand fist, speak, and release** — the text is transcribed and
   pasted. The first run prints `[speech] loading Whisper 'small' model…`; later
   runs use the cache.

### First launch and permissions

On first launch, grant **camera** and **accessibility / input-control**
permission when the OS prompts. On macOS these live in **System Settings →
Privacy & Security → Camera** and **→ Accessibility**. OpenCV handles camera
frames internally and opens no extra windows.

### Why `gui-qt` is required on Linux

pywebview's usual Linux backend, GTK, relies on the system PyGObject (`gi`) and
WebKitGTK, which a venv or uv-managed Python **cannot** import
(`ModuleNotFoundError: No module named 'gi'`). The `gui-qt` extra ships a
self-contained Qt/WebEngine backend that works in any environment. To use the
lighter system WebKitGTK instead, create the venv from your **system** Python
with `--system-site-packages` plus
`sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1`
— but the venv's Python must match the system version, so Qt is the simpler path.

## Releasing

There are no prebuilt installers. Users install from the repository with `uv`,
which builds and isolates the environment on their machine, so a release is just
a commit on `main` — no signing, no per-platform packaging, and no version to
keep in step across files.

To publish a change, push to `main`. Existing installations update with:

```bash
uv tool upgrade gesture-presenter
```

Tag a version when you want a fixed reference point:

```bash
git tag -a v0.1.1 -m "Gesture Presenter v0.1.1"
git push origin v0.1.1
```

Users can then pin that tag by appending `@v0.1.1` to the git URL. Keep
`project.version` in `pyproject.toml` in step with any tag you create.

The landing site deploys separately via `.github/workflows/deploy-site.yml`; see
[`landing/DEPLOY.md`](landing/DEPLOY.md).
