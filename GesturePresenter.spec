# PyInstaller recipe for a native windowed application.
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = collect_submodules("mediapipe") + collect_submodules("webview")
if sys.platform == "darwin":
    hiddenimports += ["AVFoundation", "ApplicationServices"]
icon = (
    "assets/icon.icns" if sys.platform == "darwin"
    else "assets/icon.ico" if sys.platform == "win32"
    else "assets/icon.png"
)
datas = [
    ("hand_landmarker.task", "."),
    ("frontend", "frontend"),
] + collect_data_files("mediapipe")

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # PyAV is only used by faster-whisper for file decoding. Microphone input is
    # already a NumPy waveform, and excluding it avoids duplicate FFmpeg dylibs
    # colliding with OpenCV in the macOS bundle.
    excludes=["av"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GesturePresenter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon,
)
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Gesture Presenter.app",
        icon="assets/icon.icns",
        bundle_identifier="com.gesturepresenter.app",
        info_plist={
            "NSCameraUsageDescription": "Gesture Presenter uses the camera to recognize presentation gestures.",
            "NSMicrophoneUsageDescription": "Gesture Presenter uses the microphone only when optional voice control is enabled.",
            "NSHighResolutionCapable": True,
        },
    )
