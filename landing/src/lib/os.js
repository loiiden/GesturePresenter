// Best-effort guess of the visitor's OS so we can highlight the right download.
// Falls back to null (no platform assumed) when detection is inconclusive.
export function detectOS() {
  if (typeof navigator === 'undefined') return null;

  const ua = `${navigator.userAgent} ${navigator.platform}`.toLowerCase();

  if (/mac|iphone|ipad|ipod/.test(ua)) return 'mac';
  if (/win/.test(ua)) return 'windows';
  if (/linux|x11|cros/.test(ua)) return 'linux';
  return null;
}
