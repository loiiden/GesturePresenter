# Hosting the website + builds on loiiden.de

Both the landing site and the app installers are served from **one domain**
(`loiiden.de`) by a single **Caddy** container running on your VPS. Caddy
handles automatic HTTPS. Because everything is same-origin, there is no CORS to
configure.

```
                        ┌─────────────────────── GitHub ───────────────────────┐
  push to landing/  ──► │ deploy-site.yml:  build image ─► ssh ─► docker load    │
                        │                                                       │
  push a v* tag     ──► │ build-app.yml:    build .dmg/.exe/.AppImage           │
                        │                   publish job ─► rsync installers      │
                        └───────────────────────────┬───────────────────────────┘
                                                     │  SSH (one deploy key)
                                                     ▼
                    VPS (loiiden.de)  ── Caddy container, ports 80/443
                      ├─ /srv/site        static site      (baked into image)
                      └─ /srv/downloads   installers        (host dir, mounted ro)
                                          ▲
                          rsync from the build workflow writes here
```

Two independent triggers, one server:

| You do…                     | Workflow          | Result on the VPS                          |
|-----------------------------|-------------------|--------------------------------------------|
| Push changes under `landing/` | `deploy-site.yml` | New site image loaded, container restarted |
| Push a `v*` tag             | `build-app.yml`   | New installers + `latest.json` in `/srv/downloads` |

The site image contains only the static site + Caddy config. Installers are
**not** in the image — they live in the host directory `/srv/downloads`, mounted
read-only, so shipping a new site never disturbs the downloads and vice-versa.

---

## 1. DNS

Point `loiiden.de` (and optionally `www`) at the VPS:

```
A    loiiden.de    <VPS-IP>
```

Caddy needs ports **80 and 443** reachable to obtain and renew the TLS
certificate, so open them in the firewall / security group.

## 2. One-time VPS setup

```bash
# Docker + compose plugin
curl -fsSL https://get.docker.com | sh

# Deploy user that can run docker and owns the downloads dir
sudo adduser --disabled-password --gecos "" deploy
sudo usermod -aG docker deploy
sudo mkdir -p /srv/downloads
sudo chown -R deploy:deploy /srv/downloads
```

Add the CI **public** key to `~deploy/.ssh/authorized_keys`. Generate a fresh
keypair just for deploys and keep the private half in GitHub secrets:

```bash
ssh-keygen -t ed25519 -f deploy_key -N ""
# deploy_key.pub  -> authorized_keys on the VPS
# deploy_key      -> DEPLOY_SSH_KEY secret
```

## 3. GitHub secrets

**Settings → Secrets and variables → Actions.** Both workflows share these:

| Secret | Example | Used by |
|---|---|---|
| `DEPLOY_SSH_KEY` | *(private key contents)* | both |
| `DEPLOY_HOST` | `loiiden.de` | both |
| `DEPLOY_USER` | `deploy` | both |
| `DEPLOY_PATH` | `/srv/downloads` | `build-app.yml` (installer rsync target) |

> `DEPLOY_PATH` **must** be `/srv/downloads` — that's the host directory the
> compose file mounts into Caddy. If you change one, change the other.

## 4. Set the ACME email

Edit `landing/deploy/docker-compose.yml` and set a real `ACME_EMAIL` (used by
Let's Encrypt for expiry notices). `SITE_DOMAIN` is already `loiiden.de`.

## 5. First deploy

Push a change under `landing/` (or run **Deploy landing site** from the Actions
tab). The workflow builds the image, copies it to the VPS over SSH, and runs
`docker compose up -d`. On first boot Caddy fetches the certificate — give it a
few seconds, then open <https://loiiden.de>.

Then cut a release (`git tag -a v0.1.3 && git push origin v0.1.3`) to populate
`/srv/downloads` with installers. Until that runs, the site still works and its
download buttons fall back to stable `/latest/<file>` names.

---

## How it fits together

- **Same origin, no CORS.** `DOWNLOAD_BASE` in `src/lib/content.js` is
  `https://loiiden.de`, so the site fetches `/latest.json` from itself.
- **Caching** (in `Caddyfile`): `latest.json` and `/latest/*` get a 60s cache so
  new releases appear quickly; versioned `/<n>/…` paths are `immutable`.
- **Downloads are forced** with `Content-Disposition: attachment`.
- **TLS certs persist** in the `caddy_data` volume across restarts and image
  updates — no re-issuing on every deploy.

## Local preview of the container

```bash
docker build -t gp-site:latest landing
docker run --rm -p 8080:8080 -e SITE_DOMAIN=":8080" \
  -v "$PWD/some-downloads:/srv/downloads:ro" gp-site:latest
# open http://localhost:8080  (":8080" makes Caddy serve plain HTTP, no ACME)
```

## Notes

- **No registry needed.** The image is streamed to the VPS via
  `docker save | ssh docker load`, which works fine for a private repo. If you'd
  rather use GHCR (for rollback/history), that's a small change to
  `deploy-site.yml`.
- **Architecture must match the server.** The GitHub runner is amd64, so
  `deploy-site.yml` cross-builds the image for the VPS with Buildx + QEMU
  (`--platform linux/arm64`). An amd64 image on an ARM host fails at startup with
  `exec format error`. For a 32-bit ARM host use `linux/arm/v7`; for an x86 host
  set `linux/amd64` (or drop the `--platform` flag).
- **Rollback:** installers keep a versioned copy under `/srv/downloads/<version>/`.
  Prune old ones whenever you like.
- The site's GitHub links (nav/footer) point at the private repo and won't
  resolve publicly — remove or repoint them if the repo stays private.
