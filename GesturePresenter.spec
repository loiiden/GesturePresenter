# PyInstaller recipe for a native windowed application.
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = collect_submodules("mediapipe") + collect_submodules("webview")
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
    excludes=[],
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
)
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Gesture Presenter.app",
        icon=None,
        bundle_identifier="com.gesturepresenter.app",
    )
