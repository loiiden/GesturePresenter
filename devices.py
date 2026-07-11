from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path


def list_cameras() -> list[dict]:
    """Return camera labels without opening devices or requesting permission."""
    names: list[str] = []
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["system_profiler", "SPCameraDataType", "-json"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            data = json.loads(result.stdout or "{}")
            names = _collect_names(data.get("SPCameraDataType", []))
        elif system == "Windows":
            command = "Get-PnpDevice -Class Camera -Status OK | Select-Object -ExpandProperty FriendlyName"
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True, text=True, timeout=5, check=False,
            )
            names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        elif system == "Linux":
            for device in sorted(Path("/sys/class/video4linux").glob("video*")):
                name_file = device / "name"
                names.append(name_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        names = []

    if not names:
        return [{"id": 0, "label": "Camera 1 — System default"}]
    return [
        {"id": index, "label": name if index else f"{name} (Default)"}
        for index, name in enumerate(dict.fromkeys(names))
    ]


def _collect_names(items) -> list[str]:
    names = []
    if isinstance(items, dict):
        if items.get("_name"):
            names.append(str(items["_name"]))
        for value in items.values():
            names.extend(_collect_names(value))
    elif isinstance(items, list):
        for value in items:
            names.extend(_collect_names(value))
    return list(dict.fromkeys(names))


def list_displays() -> list[dict]:
    displays = display_rects()
    return [
        {
            "id": item["id"],
            "label": (
                f"Display {item['id'] + 1} — {item['width']} × {item['height']}"
                + (" (Primary)" if item["primary"] else "")
            ),
        }
        for item in displays
    ]


def display_rects() -> list[dict]:
    if platform.system() == "Darwin":
        try:
            import Quartz
            _, identifiers, _ = Quartz.CGGetActiveDisplayList(16, None, None)
            displays = [
                {
                    "id": index,
                    "x": int((bounds := Quartz.CGDisplayBounds(identifier)).origin.x),
                    "y": int(bounds.origin.y),
                    "width": int(bounds.size.width),
                    "height": int(bounds.size.height),
                    "primary": bool(Quartz.CGDisplayIsMain(identifier)),
                }
                for index, identifier in enumerate(identifiers)
            ]
            if displays:
                return displays
        except Exception:
            pass
    try:
        from screeninfo import get_monitors
        monitors = get_monitors()
        return [
            {
                "id": index,
                "x": monitor.x, "y": monitor.y,
                "width": monitor.width, "height": monitor.height,
                "primary": bool(monitor.is_primary),
            }
            for index, monitor in enumerate(monitors)
        ] or _fallback_display()
    except Exception:
        return _fallback_display()


def _fallback_display() -> list[dict]:
    try:
        import pyautogui
        width, height = pyautogui.size()
    except Exception:
        width = height = 0
    return [{"id": 0, "x": 0, "y": 0,
             "width": width, "height": height, "primary": True}]
