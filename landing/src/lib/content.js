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

export const simpleGestures = [
  { hand: 'Right hand', gesture: 'Pinch thumb + index, then release', action: 'Next slide' },
  { hand: 'Left hand', gesture: 'Pinch thumb + index, then release', action: 'Previous slide' },
];

export const gestures = [
  { gesture: 'Point with index finger, thumb relaxed', action: 'Move the pointer' },
  { gesture: 'Index straight + thumb out sideways', action: 'Left click on release' },
  { gesture: 'Two fingers together, move up/down', action: 'Scroll' },
  { gesture: 'Open-palm swipe', action: 'Previous / next slide' },
  { gesture: 'Hold a fist', action: 'Toggle black screen' },
  { gesture: 'Thumb up', action: 'Play or pause media' },
  { gesture: 'Hold a V sign', action: 'Open task overview' },
  { gesture: 'Left fist + speak', action: 'Transcribe and paste speech (voice edition)' },
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
    body: 'Pinch with your right hand for next slide, or your left for previous. Full mode adds pointer, click, scroll, and more.',
  },
];
