# Hosting the website on loiiden.de

The landing site is served from `loiiden.de` by a single **Caddy** container on
your VPS, which also handles automatic HTTPS.

```
                        ┌─────────────────────── GitHub ───────────────────────┐
  push to landing/  ──► │ deploy-site.yml:  build image ─► ssh ─► docker load   │
                        └───────────────────────────┬──────────────────────────┘
                                                     │  SSH (one deploy key)
                                                     ▼
                    VPS (loiiden.de)  ── Caddy container, ports 80/443
                      └─ /srv/site        static site  (baked into the image)
```

| You do…                       | Workflow          | Result on the VPS                          |
|-------------------------------|-------------------|--------------------------------------------|
| Push changes under `landing/` | `deploy-site.yml` | New site image loaded, container restarted |

The site image is fully self-contained: the static site plus the Caddy config.
There are no installers to host — the app is installed from source with `uv`,
which fetches a compatible Python and builds on the user's machine.

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

# Deploy user that can run docker
sudo adduser --disabled-password --gecos "" deploy
sudo usermod -aG docker deploy
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

## 4. Set the ACME email

Edit `landing/deploy/docker-compose.yml` and set a real `ACME_EMAIL` (used by
Let's Encrypt for expiry notices). `SITE_DOMAIN` is already `loiiden.de`.

## 5. First deploy

Push a change under `landing/` (or run **Deploy landing site** from the Actions
tab). The workflow builds the image, copies it to the VPS over SSH, and runs
`docker compose up -d`. On first boot Caddy fetches the certificate — give it a
few seconds, then open <https://loiiden.de>.

That is the whole deployment. The site shows `uv` install commands rather than
linking to files, so there is nothing else to publish.

---

## How it fits together

- **Static only.** The site is a built Svelte bundle; it makes no network
  requests of its own, so there is no CORS or manifest to keep in step.
- **TLS certs persist** in the `caddy_data` volume across restarts and image
  updates — no re-issuing on every deploy.

## Local preview of the container

```bash
docker build -t gp-site:latest landing
docker run --rm -p 8080:8080 -e SITE_DOMAIN=":8080" gp-site:latest
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
  Prune old ones whenever you like.
- The site's GitHub links (nav/footer) point at the private repo and won't
  resolve publicly — remove or repoint them if the repo stays private.
