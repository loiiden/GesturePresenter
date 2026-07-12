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
