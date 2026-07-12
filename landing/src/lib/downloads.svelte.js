import { DOWNLOAD_BASE, platforms } from './content.js';

// Reactive release info, populated from the server's latest.json manifest.
// The site works without it (stable filenames), but the manifest lets us show
// the current version and file sizes, and guarantees links match what's live.
export const release = $state({
  loaded: false,
  version: null,
  files: {}, // { mac|windows|linux: { name, size, sha256 } }
});

let started = false;

export async function loadLatest() {
  if (started) return;
  started = true;
  try {
    const res = await fetch(`${DOWNLOAD_BASE}/latest.json`, { cache: 'no-cache' });
    if (!res.ok) return;
    const data = await res.json();
    release.version = data.version ?? null;
    release.files = data.files ?? {};
  } catch {
    // Offline, CORS not set up yet, or manifest missing — fall back silently.
  } finally {
    release.loaded = true;
  }
}

function meta(id) {
  return platforms.find((p) => p.id === id);
}

// Direct download URL for a platform. Prefers the manifest's filename, falls
// back to the stable name baked into content.js.
export function urlFor(id) {
  const name = release.files[id]?.name ?? meta(id)?.file;
  return `${DOWNLOAD_BASE}/latest/${name}`;
}

// Human-readable size like "205 MB", or '' when unknown.
export function sizeFor(id) {
  const bytes = release.files[id]?.size;
  if (!bytes) return '';
  return `${(bytes / 1_048_576).toFixed(0)} MB`;
}
