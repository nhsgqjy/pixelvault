# PixelVault production deployment

## Deployment model

One container serves the compiled React application and FastAPI under the same origin. SQLite metadata, originals, thumbnails, upload chunks and recovery quarantine all live in `/app/data`, backed by the `pixelvault-data` Docker volume.

The old PostgreSQL and MinIO services were removed because the application did not use them. This deployment documents the architecture that actually runs rather than advertising inactive infrastructure.

## Prerequisites

- Docker Desktop or Docker Engine with Compose v2
- Enough disk space for originals, thumbnails, backups and temporary upload chunks
- A trusted local machine or HTTPS reverse proxy

## First deployment

1. Copy `.env.example` to `.env`.
2. Replace `PIXELVAULT_PASSWORD` with a long unique password.
3. Keep `PIXELVAULT_COOKIE_SECURE=false` only for direct HTTP on localhost or a trusted LAN. Set it to `true` when an HTTPS reverse proxy is in front of PixelVault.
4. Start the service:

```bash
docker compose up --build -d
docker compose ps
```

Open `http://localhost:8080`. A healthy service reports `{"status":"ok"}` at `http://localhost:8080/api/health`.

The Compose file deliberately refuses to start when `PIXELVAULT_PASSWORD` is missing. The application also refuses production startup when the password remains `demo1234`.

## Render web service

The repository includes `render.yaml` for a reproducible Render Blueprint and
also supports manual Web Service creation from the Render dashboard. Connect
`nhsgqjy/pixelvault`, select the `main` branch and use these values:

| Setting | Value |
| --- | --- |
| Language | `Docker` |
| Region | `Singapore` |
| Root directory | blank |
| Docker build context | `.` |
| Dockerfile path | `./Dockerfile` |
| Docker command | blank |
| Health check path | `/api/health` |
| Auto-deploy | On commit |

Set the following environment variables in the Render dashboard. Never commit
the password value or place it in `render.yaml`:

| Variable | Value |
| --- | --- |
| `PIXELVAULT_DEMO_PASSWORD` | a long unique secret, entered only in Render |
| `PIXELVAULT_COOKIE_SECURE` | `true` |
| `PIXELVAULT_ENV` | `production` |
| `DATA_DIR` | `/app/data` |

Render supplies `PORT` at runtime. The container uses that value automatically
and falls back to port 8000 for local Compose deployments. Render terminates
public TLS and forwards requests to this container, so secure cookies must stay
enabled.

The Free web-service filesystem is ephemeral. It is suitable for validating the
public HTTPS deployment, but uploaded photos and SQLite state can disappear on a
restart or redeploy. Do not treat it as durable storage. A paid Render service
can attach a persistent disk at `/app/data`; the longer-term multi-client design
will instead move metadata to PostgreSQL and media to object storage.

## LAN and HTTPS

The published port is available to the host network. To use a phone on the same trusted Wi-Fi, open `http://<computer-LAN-IP>:8080` and allow TCP 8080 through the host firewall only for the private network profile.

For internet exposure, put a TLS reverse proxy in front of port 8080, set `PIXELVAULT_COOKIE_SECURE=true`, restrict inbound traffic to the proxy and use a real domain certificate. Do not expose an HTTP-only vault directly to the public internet.

## Backup

The application UI can export a portable, checksum-verified ZIP backup. For an infrastructure-level volume backup, stop writes first:

```bash
docker compose stop pixelvault
docker run --rm -v pixelvault_pixelvault-data:/source:ro -v "${PWD}:/backup" alpine \
  tar czf /backup/pixelvault-data.tar.gz -C /source .
docker compose start pixelvault
```

Keep at least one backup outside the host running PixelVault. A backup stored only on the same disk does not protect against disk failure.

## Restore

Prefer the application's merge-only ZIP import for normal migration. To restore an infrastructure backup into an empty volume:

```bash
docker compose down
docker volume create pixelvault_pixelvault-data
docker run --rm -v pixelvault_pixelvault-data:/target -v "${PWD}:/backup:ro" alpine \
  tar xzf /backup/pixelvault-data.tar.gz -C /target
docker compose up -d
```

Verify `/api/health`, log in, run the storage integrity scan and confirm representative originals and thumbnails before deleting the backup.

## Upgrade and rollback

Before upgrading, export or archive the data volume. Then rebuild and recreate the application:

```bash
docker compose build --pull
docker compose up -d
docker compose ps
```

If verification fails, restore the previous application image and data backup together. SQLite schema changes can be forward-only, so reverting only the code is not a complete rollback strategy.

## Operations and troubleshooting

```bash
docker compose ps
docker compose logs --tail=200 pixelvault
docker compose restart pixelvault
```

- `PIXELVAULT_DEMO_PASSWORD must be changed`: set a non-demo password in `.env`.
- Container is unhealthy: inspect logs and check whether the data volume is writable.
- Login works over HTTP but not HTTPS: ensure `PIXELVAULT_COOKIE_SECURE=true` and the proxy forwards HTTPS correctly.
- Phone cannot connect: verify both devices share the network, use the computer's LAN IP, and allow only the private-network firewall rule.
- Photos disappear after container recreation: confirm the `pixelvault-data:/app/data` volume is still attached; do not run `docker compose down -v` unless permanent volume deletion is intended.

## Verification gates

The repository provides `tools/verify_production.py`, which starts the production entrypoint with isolated temporary data and verifies the SPA root, client-side route fallback, static assets, health endpoint, anonymous rejection, authenticated cookie and photo query. The regular backend smoke suite remains the full business-regression gate.
