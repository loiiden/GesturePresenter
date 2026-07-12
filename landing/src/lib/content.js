// Central place for links and copy so the sections stay declarative.

export const REPO = 'https://github.com/loiiden/GesturePresenter';

// Root of your own download server (the VPS behind this domain). Installers are
// served from `${DOWNLOAD_BASE}/latest/<file>` and a small `latest.json`
// manifest lives at `${DOWNLOAD_BASE}/latest.json`. Change this to your domain.
export const DOWNLOAD_BASE = 'https://loiiden.de';

// Stable asset names. These are the fallback links used when the manifest can't
// be fetched, so downloads keep working even before latest.json exists.
export const platforms = [
  {
    id: 'mac',
    name: 'macOS',
    file: 'Gesture-Presenter-macOS.dmg',
    note: 'Universal · macOS 12 or later',
  },
  {
    id: 'windows',
    name: 'Windows',
    file: 'Gesture-Presenter-Windows-Setup.exe',
    note: 'Installer · Windows 10 or later',
  },
  {
    id: 'linux',
    name: 'Linux',
    file: 'Gesture-Presenter-Linux-x86_64.AppImage',
    note: 'AppImage · x86_64',
  },
];

export const gestures = [
  { gesture: 'Point index finger', action: 'Move the on-screen pointer' },
  { gesture: 'Pinch thumb + index', action: 'Left click' },
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
