"""
macOS action dispatcher.
Maps gesture events to system actions.
"""
import pyautogui
import pyperclip
import Quartz

SCROLL_SCALE = 800   # normalised Δ → pixels scrolled

# macOS virtual key codes
_VK_TAB   = 0x30
_VK_LEFT  = 0x7B
_VK_RIGHT = 0x7C

# modifier virtual key codes
_VK_OPTION  = 0x3A
_VK_CONTROL = 0x3B
_VK_COMMAND = 0x37

_VK_V = 0x09

# Accessibility zoom — how many scroll units per zoom call.
# Requires: System Settings → Accessibility → Zoom →
#   "Use scroll gesture with modifier keys to zoom" = ON  (modifier = Control)
_ZOOM_AMOUNT = 60


def _cgkey(keycode: int, mod_keycode: int, mod_flag: int):
    """Send a key+modifier combo via CGEvent with clean modifier up/down."""
    tap = Quartz.kCGHIDEventTap

    def post(code, down, flags=0):
        e = Quartz.CGEventCreateKeyboardEvent(None, code, down)
        Quartz.CGEventSetFlags(e, flags)
        Quartz.CGEventPost(tap, e)

    post(mod_keycode, True,  mod_flag)
    post(keycode,     True,  mod_flag)
    post(keycode,     False, mod_flag)
    post(mod_keycode, False, 0)


def move_cursor(x: int, y: int):
    pyautogui.moveTo(x, y, duration=0)


def left_click():
    pyautogui.click()


def right_click():
    pyautogui.rightClick()


def next_slide():
    pyautogui.press("right")


def previous_slide():
    pyautogui.press("left")


def toggle_black_screen():
    """Standard presentation shortcut in Keynote, PowerPoint and web decks."""
    pyautogui.press("b")


def toggle_media():
    pyautogui.press("space")


def scroll(dy_norm: float):
    """dy_norm: normalised Δy (positive = finger moved down = scroll up)."""
    pixels = int(-dy_norm * SCROLL_SCALE)
    if pixels == 0:
        return
    event = Quartz.CGEventCreateScrollWheelEvent(
        None, Quartz.kCGScrollEventUnitPixel, 1, pixels
    )
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def zoom_in():
    """Trigger macOS accessibility zoom in (Ctrl+scroll up)."""
    e = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitPixel, 1, _ZOOM_AMOUNT)
    Quartz.CGEventSetFlags(e, Quartz.kCGEventFlagMaskControl)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)


def zoom_out():
    """Trigger macOS accessibility zoom out (Ctrl+scroll down)."""
    e = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitPixel, 1, -_ZOOM_AMOUNT)
    Quartz.CGEventSetFlags(e, Quartz.kCGEventFlagMaskControl)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)


def mission_control():
    # Preserve the user's configured Mission Control shortcut.
    _cgkey(_VK_TAB, _VK_OPTION, Quartz.kCGEventFlagMaskAlternate)


def switch_space_left():
    _cgkey(_VK_LEFT, _VK_CONTROL, Quartz.kCGEventFlagMaskControl)


def switch_space_right():
    _cgkey(_VK_RIGHT, _VK_CONTROL, Quartz.kCGEventFlagMaskControl)


def paste_text(text: str):
    """Copy text to clipboard and send Cmd+V."""
    pyperclip.copy(text)
    tap  = Quartz.kCGHIDEventTap
    flag = Quartz.kCGEventFlagMaskCommand

    def post(code, down, flags=0):
        e = Quartz.CGEventCreateKeyboardEvent(None, code, down)
        Quartz.CGEventSetFlags(e, flags)
        Quartz.CGEventPost(tap, e)

    post(_VK_COMMAND, True,  flag)
    post(_VK_V,       True,  flag)
    post(_VK_V,       False, flag)
    post(_VK_COMMAND, False, 0)
