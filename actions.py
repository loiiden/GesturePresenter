"""Cross-platform action dispatcher used by the tracking engine."""
from __future__ import annotations

import platform
import subprocess

import pyautogui
import pyperclip


SYSTEM = platform.system()
SCROLL_SCALE = 120
_scroll_remainder = 0.0

# Mission Control ships as a launchable application, so the feature can be
# invoked by identity instead of by keyboard shortcut. See mission_control().
_MACOS_OVERVIEW_BUNDLE = "com.apple.exposelauncher"
_MACOS_OPEN = "/usr/bin/open"


def move_cursor(x: int, y: int) -> None:
    pyautogui.moveTo(x, y, duration=0)


def left_click() -> None:
    pyautogui.click()


def next_slide() -> None:
    pyautogui.press("right")


def previous_slide() -> None:
    pyautogui.press("left")


def toggle_black_screen() -> None:
    pyautogui.press("b")


def toggle_media() -> None:
    pyautogui.press("space")


def scroll(dy_norm: float) -> None:
    global _scroll_remainder
    scaled = -dy_norm * SCROLL_SCALE + _scroll_remainder
    amount = int(scaled)
    _scroll_remainder = scaled - amount
    if amount:
        pyautogui.scroll(amount)


def mission_control() -> None:
    """Open the platform's overview/task-switching surface.

    macOS launches Mission Control by bundle identifier rather than sending its
    keyboard shortcut, because that shortcut belongs to the user: it may sit on
    Control+Up, on Option+Tab, or be disabled entirely, so no fixed combination
    is correct for everyone. Launching the application invokes the feature
    itself and is unaffected by whatever the machine is configured to use.

    Doing so also avoids synthesizing a modifier at all. A simulated shortcut
    has to post a separate key-down and key-up for the modifier, and the key-up
    can be lost when the overview takes over the display — leaving the modifier
    logically held down. That matters here because the slide actions send bare
    arrow keys, and on a typical Mac the Spaces shortcuts are the same arrows
    with a modifier: one stuck modifier silently turns the next slide change
    into a Space switch.

    Windows and Linux keep their keyboard shortcuts. Windows' Win+Tab cannot be
    remapped through the normal interface, so it is stable across machines, and
    the Linux overview varies so much between desktop environments that a
    single direct invocation would not be more portable than the key.
    """
    if SYSTEM == "Darwin":
        try:
            completed = subprocess.run(
                [_MACOS_OPEN, "-b", _MACOS_OVERVIEW_BUNDLE],
                capture_output=True, timeout=5, check=False,
            )
            if completed.returncode == 0:
                return
        except (OSError, subprocess.SubprocessError):
            pass
        # Only reached if Mission Control cannot be launched. Control+Up is the
        # macOS factory default; a machine that has both lost the bundle and
        # remapped the shortcut is beyond what can be detected here.
        pyautogui.hotkey("ctrl", "up")
    elif SYSTEM == "Windows":
        pyautogui.hotkey("win", "tab")
    else:
        # GNOME overview; other Linux desktops can remap this at OS level.
        pyautogui.press("win")


def paste_text(text: str) -> None:
    pyperclip.copy(text)
    pyautogui.hotkey("command" if SYSTEM == "Darwin" else "ctrl", "v")
