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
| Left | Held open palm | Lock/unlock gesture controls |
| Left | Hold fist and speak, then release | Transcribe and paste automatically |

Press `L` to lock or unlock controls from the keyboard.

## Run from source

The app needs **Python 3.10–3.12** and several dependencies. The simplest way to
get all of that right — on any OS — is [**uv**](https://docs.astral.sh/uv/),
which downloads a compatible Python for you and manages the environment. You do
**not** need to install Python yourself when using uv.

> **Why uv?** It automatically fetches a supported interpreter (3.10–3.12), so it
> works even on newer distributions such as **Ubuntu 26**, recent Fedora, or
> Arch that ship Python **3.13+** — a version some dependencies (e.g. MediaPipe)
> don't provide wheels for yet. No `pyenv`, no deadsnakes PPA, no version juggling.

### Quick start with uv (recommended)

1. **Install uv** (no admin rights required):

   ```bash
   # macOS / Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   ```powershell
   # Windows (PowerShell)
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   Restart your shell afterwards so `uv` is on the `PATH`.

2. **Install and run** the app straight from GitHub.

   **macOS / Windows** use the built-in system WebView, so nothing extra is
   needed:

   ```bash
   uv tool install git+https://github.com/loiiden/GesturePresenter.git
   gesture-presenter
   ```

   **Linux** also needs a GUI backend — add the `gui-qt` extra (see step 3 for
   why):

   ```bash
   uv tool install "gesture-presenter[gui-qt] @ git+https://github.com/loiiden/GesturePresenter.git"
   gesture-presenter
   ```

   Combine extras as needed, e.g. `[gui-qt,voice]` on Linux or `[voice]`
   elsewhere for local speech-to-text.

   Prefer working from a checkout? Clone it and let uv build the environment on
   the fly — no manual venv, no activation:

   ```bash
   git clone https://github.com/loiiden/GesturePresenter.git
   cd GesturePresenter
   uv run gesture-presenter                    # macOS / Windows
   uv run --extra gui-qt gesture-presenter     # Linux (add ,voice for speech)
   ```

3. **Linux only — system libraries.** A few things aren't Python packages, so
   install them with your package manager:

   ```bash
   sudo apt install libxcb-cursor0      # Qt platform plugin (Ubuntu 24.04+)
   sudo apt install portaudio19-dev     # only if you enabled voice
   ```

   *Why `gui-qt`?* pywebview's usual Linux backend, GTK, relies on the system
   PyGObject (`gi`) and WebKitGTK, which a venv or uv-managed Python **cannot**
   import (`ModuleNotFoundError: No module named 'gi'`). The `gui-qt` extra
   installs a self-contained Qt/WebEngine backend that works inside any
   environment. If you'd rather use the lighter system WebKitGTK, create the venv
   from your **system** Python with `--system-site-packages` and
   `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1`
   — but the venv's Python version must match the system's, so Qt is the simpler,
   more reliable path.

### Manual setup with pip (without uv)

If you already have a working **Python 3.10–3.12**, use a plain virtual
environment. (On distros that only ship Python 3.13+, install 3.12 first — e.g.
via `pyenv` — or just use uv above.)

```bash
git clone https://github.com/loiiden/GesturePresenter.git
cd GesturePresenter
```

**macOS:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .            # or:  pip install -e ".[voice]"
gesture-presenter
```

**Linux** (add the `gui-qt` extra for the GUI backend — see the uv section for why):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[gui-qt]"  # or:  pip install -e ".[gui-qt,voice]"
sudo apt install libxcb-cursor0    # Qt platform plugin (Ubuntu 24.04+)
gesture-presenter
```

**Windows (PowerShell):**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
gesture-presenter
```

Reactivate the environment (`source .venv/bin/activate`, or
`.\.venv\Scripts\Activate.ps1`) each time before running it.

### First launch and permissions

On first launch, grant **camera** and **accessibility / input-control**
permission when the OS prompts for them. On macOS these live in **System
Settings → Privacy & Security → Camera** and **→ Accessibility**. OpenCV handles
camera frames internally and opens no extra windows.

Next time, reactivate the environment (`source .venv/bin/activate`, or
`.\.venv\Scripts\Activate.ps1` on Windows) before running `gesture-presenter`.

## Building and releasing installers

An installer must be built on its target operating system. Do not build a
Windows installer or Linux AppImage from macOS. The recommended approach is the
included GitHub Actions matrix, which runs the same revision on macOS, Windows,
and Linux.

### Build all platforms with GitHub Actions

Before publishing a version, update the version in both:

- `pyproject.toml` (`project.version`)
- `packaging/windows/GesturePresenter.iss` (`AppVersion`)

Commit and push those changes. Then create a new tag; use a version that does not
already exist:

```bash
git status
git push origin desktop-app
git tag -a v0.1.1 -m "Gesture Presenter v0.1.1"
git push origin v0.1.1
```

Pushing a `v*` tag starts `.github/workflows/build-app.yml`. It builds on three
native runners and publishes these files to the matching GitHub Release:

- `Gesture-Presenter-macOS.dmg`
- `Gesture-Presenter-Windows-Setup.exe`
- `Gesture-Presenter-Linux-x86_64.AppImage`

Open the repository's **Actions → Build desktop application** page to monitor the
jobs. Each operating-system package is also available as a workflow artifact.

To test all builds without creating a release, use **Run workflow** on that page,
or run this with the GitHub CLI:

```bash
gh workflow run build-app.yml
gh run list --workflow=build-app.yml --limit=1
gh run watch
```

A manually dispatched workflow uploads artifacts but does not create a public
release. Tagged workflows do both.

### Build locally on macOS

Use Python 3.10–3.12. Build dependencies are developer-only; end users do not
need Python. Work from a clone of the repository (see *Run from source* above),
then from the project directory:

```bash
python3.11 -m venv .build-venv
source .build-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[voice,build]"
pyinstaller --clean --noconfirm GesturePresenter.spec

rm -rf dist/dmg
mkdir -p dist/dmg
cp -R "dist/Gesture Presenter.app" dist/dmg/
ln -s /Applications dist/dmg/Applications
hdiutil create -size 300m -fs HFS+ \
  -volname "Gesture Presenter" \
  -srcfolder dist/dmg \
  -ov -format UDZO \
  "dist/Gesture-Presenter-macOS.dmg"
```

The result is `dist/Gesture-Presenter-macOS.dmg`.

### Build locally on Windows

Install Python 3.11 and [Inno Setup](https://jrsoftware.org/isinfo.php), then run
PowerShell from the project directory:

```powershell
py -3.11 -m venv .build-venv
.\.build-venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install ".[voice,build]"
pyinstaller --clean --noconfirm GesturePresenter.spec
iscc packaging\windows\GesturePresenter.iss
```

The result is `dist\Gesture-Presenter-Windows-Setup.exe`.

### Build locally on Linux

Install Python development tools and the WebKitGTK packages required by
pywebview. Package names vary by distribution. Build the executable first:

```bash
python3.11 -m venv .build-venv
source .build-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[voice,build]"
pyinstaller --clean --noconfirm GesturePresenter.spec
```

The AppImage layout and `appimagetool` commands are defined in the Linux section
of `.github/workflows/build-app.yml`; running the workflow is the supported way
to produce `Gesture-Presenter-Linux-x86_64.AppImage` consistently.

### Icons, signing, and permissions

The source icon is `assets/icon.png`. Generated `icon.icns`, `icon.ico`, and the
512 px Linux icon are committed so CI builds are reproducible.

Current local builds are ad-hoc/unsigned. macOS may invalidate Accessibility
permission after each rebuild because the app's code hash changes. Before public
distribution, sign with an Apple Developer ID and notarize the app and DMG.
Windows releases should likewise be Authenticode-signed to avoid SmartScreen
warnings. Signing certificates and secrets must be configured separately in the
CI environment; they must never be committed to the repository.
