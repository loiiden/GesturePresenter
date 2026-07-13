# Gesture Presenter — Landing

A minimal landing page for installing Gesture Presenter. The primary flow
generates platform- and edition-specific `uv` commands; unsigned prebuilt
desktop files remain available as a secondary option. Built with [Svelte 5](https://svelte.dev) and
[Vite](https://vitejs.dev).

## Develop

```bash
cd landing
npm install
npm run dev
```

## Build

```bash
npm run build      # outputs a static site to dist/
npm run preview    # serve the production build locally
```

The output in `dist/` is fully static. In production it's baked into a Caddy
Docker image and served — together with the app installers — from `loiiden.de`.
See [DEPLOY.md](./DEPLOY.md) for the full hosting plan and CI setup.

## How installation works

The installer detects the visitor's operating system and lets them choose the
gesture-only or local-voice edition. It then displays copyable commands to
install `uv`, install the correct application extras, and launch the app. Linux
commands automatically include the required Qt GUI extra. An uninstall
disclosure provides the matching `uv tool uninstall gesture-presenter` command
and explains which local data remains.

## How prebuilt downloads work

The site and the installers share one origin (`loiiden.de`). Download buttons
point at `${DOWNLOAD_BASE}/latest/<asset>` and the site reads a `latest.json`
manifest for the current version and file sizes. The UI labels these builds as
unsigned and recommends the terminal installation. `DOWNLOAD_BASE` and the stable
asset names live in `src/lib/content.js`; the manifest logic is in
`src/lib/downloads.svelte.js`. If the manifest can't be fetched, the buttons fall
back to the stable `/latest/<asset>` links so nothing breaks.

## Deploying

Two GitHub Actions workflows drive everything (details in `DEPLOY.md`):

- **`deploy-site.yml`** — on pushes under `landing/`, builds the Caddy image and
  ships it to the VPS over SSH.
- **`build-app.yml`** — on `v*` tags, builds the installers and rsyncs them plus
  `latest.json` into the server's `/srv/downloads`.
