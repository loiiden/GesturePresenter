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
| Right | Open-palm horizontal swipe | Previous/next slide |
| Right | Held fist | Toggle black screen |
| Right | Thumb up | Play/pause media |
| Right | Held V sign | Mission Control/task overview |
| Left | Held open palm | Lock/unlock gesture controls |
| Left | Hold fist and speak, then open | Dictate, when voice is enabled |

Press `L` to lock or unlock controls from the keyboard.

## Running from source

Python 3.10–3.12 is supported.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
gesture-presenter
```

To include local voice recognition:

```bash
pip install -e ".[voice]"
```

Camera and accessibility/input-control permission must be granted when requested
by the operating system. Linux installations need a supported pywebview backend
(normally WebKitGTK), and voice installations may also need PortAudio. OpenCV is
used internally for camera frames but creates no application windows.

## Building distributable apps

Install the build dependencies and use the included PyInstaller recipe:

```bash
pip install ".[voice,build]"
pyinstaller --noconfirm GesturePresenter.spec
```

Output is written to `dist/`. Tagged releases and manual workflow runs build
artifacts for macOS, Windows, and Linux through GitHub Actions. Code signing and
platform-specific installers are the next release-engineering phase; unsigned
builds may show an operating-system security warning.

The release workflow produces end-user packages automatically:

- `Gesture-Presenter-macOS.dmg`
- `Gesture-Presenter-Windows-Setup.exe`
- `Gesture-Presenter-Linux-x86_64.AppImage`

To publish them, push a version tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The workflow builds each package on its native operating system and attaches it
to the tagged release. The source icon is `assets/icon.png`; generated `.icns`,
`.ico`, and Linux 512 px assets are committed for reproducible builds. Public
releases should be signed and the macOS build notarized before broad distribution.
