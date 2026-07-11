# Presentation Hand Controller

A macOS presentation controller built with MediaPipe. It favors large semantic
actions over mouse-like precision and includes a safety lock for live speaking.

## Controls

| Hand | Gesture | Action |
|---|---|---|
| Right | Point with index finger | Move presentation pointer |
| Right | Thumb + index pinch and release | Left click |
| Right | Thumb + middle pinch, index kept away | Right click |
| Right | Open palm, swipe left/right | Next/previous slide |
| Right | Fist, held briefly | Toggle black screen |
| Right | Thumb left/right | Previous/next slide fallback |
| Right | Thumb up | Play/pause embedded media |
| Left | Open palm, hold about one second | Lock/unlock all presentation controls |
| Left | Hold fist, then speak; open to stop | Dictate text |
| Right | Thumb up after transcription | Paste dictated text |
| Right | Fist after transcription | Cancel dictated text |

Press `L` to lock/unlock controls. Press `Q` or Escape to quit.

## Setup

The app requires macOS Camera, Microphone, and Accessibility permissions for
your terminal or Python application. Create a virtual environment, install the
imports used by the source files, then run:

```bash
python hand_tracker.py
```

`TARGET_DISPLAY` in `hand_tracker.py` selects the display. If that display is
not connected, the app automatically uses the main display.

## Recognition tips

- Use even front lighting and keep the complete hand inside the camera image.
- Keep the pointing hand roughly 40–80 cm from the camera.
- Pinch cleanly, pause for a fraction of a second, then release to click.
- Begin an open-palm swipe near the center of the camera image and move clearly
  sideways. Close the hand before making another swipe.
- Keep the index finger clearly separated during a middle-finger right click.
