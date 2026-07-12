# --- Stage 1: build the static site ---------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# --- Stage 2: serve it with Caddy (static site + downloads + auto HTTPS) ----
FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv/site
# Installers are provided at runtime via a read-only volume at /srv/downloads.
