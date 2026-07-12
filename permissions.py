from __future__ import annotations

import platform
import threading


def request_camera_permission() -> tuple[bool, str | None]:
    """Request camera permission explicitly where the OS exposes an API."""
    if platform.system() != "Darwin":
        return True, None
    try:
        import AVFoundation
    except ImportError:
        # Development environments may not have the optional macOS bridge;
        # OpenCV will still request permission when opening the camera.
        return True, None

    media_type = AVFoundation.AVMediaTypeVideo
    status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(media_type)
    if status == AVFoundation.AVAuthorizationStatusAuthorized:
        return True, None
    if status in (
        AVFoundation.AVAuthorizationStatusDenied,
        AVFoundation.AVAuthorizationStatusRestricted,
    ):
        return False, (
            "Camera access is disabled. Open System Settings → Privacy & Security "
            "→ Camera and enable Gesture Presenter."
        )

    completed = threading.Event()
    granted = False

    def callback(value):
        nonlocal granted
        granted = bool(value)
        completed.set()

    AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
        media_type, callback
    )
    if not completed.wait(timeout=60):
        return False, "The camera permission request timed out."
    if not granted:
        return False, (
            "Camera permission was not granted. You can enable it later in "
            "System Settings → Privacy & Security → Camera."
        )
    return True, None


def request_accessibility_permission() -> tuple[bool, str | None]:
    """Check the current executable's input-control permission on macOS."""
    if platform.system() != "Darwin":
        return True, None
    try:
        import ApplicationServices
    except ImportError:
        return False, "The macOS Accessibility permission component is unavailable."

    if ApplicationServices.AXIsProcessTrusted():
        return True, None

    ApplicationServices.AXIsProcessTrustedWithOptions({
        ApplicationServices.kAXTrustedCheckOptionPrompt: True,
    })
    return False, (
        "Gesture Presenter is not trusted to control the keyboard and pointer. "
        "Remove any older Gesture Presenter entry in System Settings → Privacy & "
        "Security → Accessibility, add the current app from Applications, enable "
        "it, then click Start again."
    )
