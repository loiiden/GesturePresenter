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
Docker image and served from `loiiden.de`.
See [DEPLOY.md](./DEPLOY.md) for the full hosting plan and CI setup.

## How installation works

The install section detects the visitor's operating system and lets them choose the
gesture-only or local-voice edition. It then displays copyable commands to
install `uv`, install the correct application extras, and launch the app. Linux
commands automatically include the required Qt GUI extra. An uninstall
disclosure provides the matching `uv tool uninstall gesture-presenter` command
and explains which local data remains. An update disclosure documents
`uv tool upgrade gesture-presenter`, edition changes, forced
reinstallation, shell-path repair, Linux extras, and unpushed-source behavior.

## How prebuilt downloads work

The site is fully static and makes no network requests of its own: install
commands are generated in the browser from the chosen platform and options, so
there is nothing to host besides the bundle itself.

## Deploying

Two GitHub Actions workflows drive everything (details in `DEPLOY.md`):

- **`deploy-site.yml`** — on pushes under `landing/`, builds the Caddy image and
  ships it to the VPS over SSH.
