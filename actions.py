"""Cross-platform action dispatcher used by the tracking engine."""
from __future__ import annotations

import platform

import pyautogui
import pyperclip


SYSTEM = platform.system()
SCROLL_SCALE = 8


def move_cursor(x: int, y: int) -> None:
    pyautogui.moveTo(x, y, duration=0)


def left_click() -> None:
    pyautogui.click()


def right_click() -> None:
    pyautogui.rightClick()


def next_slide() -> None:
    pyautogui.press("right")


def previous_slide() -> None:
    pyautogui.press("left")


def toggle_black_screen() -> None:
    pyautogui.press("b")


def toggle_media() -> None:
    pyautogui.press("space")


def scroll(dy_norm: float) -> None:
    amount = int(-dy_norm * SCROLL_SCALE)
    if amount:
        pyautogui.scroll(amount)


def mission_control() -> None:
    """Open the platform's overview/task-switching surface."""
    if SYSTEM == "Darwin":
        # Preserves the shortcut used by the original prototype/configuration.
        pyautogui.hotkey("option", "tab")
    elif SYSTEM == "Windows":
        pyautogui.hotkey("win", "tab")
    else:
        # GNOME overview; other Linux desktops can remap this at OS level.
        pyautogui.press("win")


def paste_text(text: str) -> None:
    pyperclip.copy(text)
    pyautogui.hotkey("command" if SYSTEM == "Darwin" else "ctrl", "v")
