// Central place for links and copy so the sections stay declarative.

export const REPO = 'https://github.com/loiiden/GesturePresenter';

// Supported platforms. There are no prebuilt downloads: the app is installed
// from source with uv, which fetches a compatible Python itself. These entries
// only drive the platform picker and the commands it shows.
export const platforms = [
  { id: 'mac', name: 'macOS', note: 'macOS 12 or later' },
  { id: 'windows', name: 'Windows', note: 'Windows 10 or later' },
  { id: 'linux', name: 'Linux', note: 'x86_64 · Xorg session' },
];

export const gestures = [
  { gesture: 'Point index finger', action: 'Move the on-screen pointer' },
  { gesture: 'Pinch thumb + index', action: 'Left click (either hand)' },
  { gesture: 'Pinch thumb + middle', action: 'Right click' },
  { gesture: 'Two fingers, move up/down', action: 'Scroll the page' },
  { gesture: 'Open-palm swipe', action: 'Previous / next slide' },
  { gesture: 'Hold a fist', action: 'Toggle a black screen' },
  { gesture: 'Thumb up', action: 'Play or pause media' },
  { gesture: 'Hold a V sign', action: 'Open task overview' },
  { gesture: 'Left open palm', action: 'Lock or unlock controls' },
  { gesture: 'Left fist + speak', action: 'Transcribe and paste your voice' },
];

export const steps = [
  {
    n: '01',
    title: 'Pick your camera',
    body: 'Open the app and choose a camera and the display you want to control.',
  },
  {
    n: '02',
    title: 'Press Start',
    body: 'The camera only turns on when you start a session. Nothing runs before that.',
  },
  {
    n: '03',
    title: 'Present hands-free',
    body: 'Point, pinch, swipe, and speak. Step away from the keyboard and command the room.',
  },
];
