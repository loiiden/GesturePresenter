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
need Python.

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

The result is `dist\installer\Gesture-Presenter-Windows-Setup.exe`.

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
