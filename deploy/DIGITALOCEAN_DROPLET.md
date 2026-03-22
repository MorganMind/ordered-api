# Deploy ordered-api on a DigitalOcean droplet (VPS)

This app is a Django ASGI API served with **Gunicorn** + **UvicornWorker**, static files via **WhiteNoise**, and Postgres (typically **Supabase** via `DATABASE_URL`). TLS and HTTP/2 are expected to terminate at **nginx** (or another reverse proxy) in front of the container or process.

## 1. Droplet and firewall

- Ubuntu 22.04/24.04 LTS, at least 1 GB RAM (2 GB recommended for Docker + nginx).
- Firewall: allow SSH (22), HTTP (80), HTTPS (443). Do not expose Postgres from the droplet if you use Supabase.

## 2. Install Docker (recommended path)

Follow Docker’s official docs for Ubuntu (Engine + Compose plugin). Then:

```bash
git clone <your-repo-url> ordered-api
cd ordered-api
cp .env.example .env
```

Edit `.env` for production:

- `DEBUG=False`
- `SECRET_KEY` — long random string (required when `DEBUG=False`)
- `DATABASE_URL` — Supabase pooler URI (or discrete `SUPABASE_DB_*` vars per `ordered_api/db_config.py`)
- `ALLOWED_HOSTS` — comma-separated, e.g. `api.example.com,203.0.113.10`
- `CSRF_TRUSTED_ORIGINS` — e.g. `https://api.example.com`
- `CORS_ALLOWED_ORIGINS` — comma-separated frontend origins (e.g. your operator app)
- Supabase keys / JWT secret as already documented in `.env.example`

First-time database:

```bash
docker compose -f deploy/docker-compose.droplet.yml run --rm web python manage.py migrate
docker compose -f deploy/docker-compose.droplet.yml up -d --build
```

The compose file binds the app to **127.0.0.1:8000** so only the host (and nginx) can reach it.

Optional tuning via environment (see `.env.example`): `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`.

## 3. nginx + Let’s Encrypt

- Adapt `deploy/nginx-ordered-api.conf.example` (replace `api.example.com`, uncomment SSL paths after Certbot).
- Proxy to `127.0.0.1:8000` so Django sees `X-Forwarded-Proto: https` (already configured in `ordered_api/settings.py` via `SECURE_PROXY_SSL_HEADER`).

If you see redirect loops with `SECURE_SSL_REDIRECT`, confirm nginx sends `X-Forwarded-Proto` or temporarily set `SECURE_SSL_REDIRECT=False` in `.env` (only if you fully trust the proxy).

## 4. Alternative: no Docker

On the droplet, use Python 3.12+, a virtualenv, `pip install -r requirements.txt`, same `.env`, then:

```bash
python manage.py collectstatic --noinput
python manage.py migrate
gunicorn ordered_api.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Run Gunicorn under **systemd** and keep it bound to `127.0.0.1:8000` if nginx is on the same machine.

## 5. Deploy updates

```bash
cd ordered-api
git pull
docker compose -f deploy/docker-compose.droplet.yml up -d --build
docker compose -f deploy/docker-compose.droplet.yml run --rm web python manage.py migrate
```

The image runs `collectstatic` at build time; a new build picks up static file changes.

## 6. Auto-deploy from GitHub (Actions)

The repo includes [`.github/workflows/deploy-droplet.yml`](../.github/workflows/deploy-droplet.yml). On every push to **`main`** (or when you run the workflow manually under **Actions**), GitHub SSHs into your droplet, fast-forwards the clone to `origin/main`, rebuilds the container, and runs **`migrate`**.

### One-time: droplet can `git pull` from GitHub

1. On the droplet, go to the deploy directory (or clone the repo there):

   ```bash
   mkdir -p ~/ordered-api && cd ~/ordered-api
   git clone https://github.com/YOUR_ORG/ordered-api.git .
   # or use SSH: git clone git@github.com:YOUR_ORG/ordered-api.git .
   ```

2. For a **private** repo, use either:
   - **Deploy key** (recommended): on the droplet, `ssh-keygen -t ed25519 -f ~/.ssh/github_ordered_api -N ""`, add **`~/.ssh/github_ordered_api.pub`** in GitHub → repo **Settings → Deploy keys** (read-only is enough). Then `git remote set-url origin git@github.com:YOUR_ORG/ordered-api.git` and configure `~/.ssh/config` to use that key for `github.com`, **or**
   - A **personal access token** with repo scope for HTTPS (less ideal on a shared server).

3. Ensure production **`.env`** exists next to `manage.py` (never commit it). Run an initial deploy manually once (section 2) so Docker and DB are OK.

### One-time: GitHub Secrets

In the GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Example |
|--------|---------|
| `DROPLET_HOST` | `203.0.113.50` or `api.example.com` |
| `DROPLET_USER` | `root` or `deploy` |
| `DROPLET_SSH_KEY` | Full private key PEM (the key whose **public** half is in the droplet’s `~/.ssh/authorized_keys` for that user) |
| `DROPLET_DEPLOY_PATH` | `/root/ordered-api` or `/home/deploy/ordered-api` (must match `cd` path on the server) |

Use a **dedicated** SSH key pair for GitHub → droplet (do not reuse your laptop’s personal key if others manage the repo).

### Firewall

Allow **inbound SSH (22)** from **GitHub Actions** IPs if you use a strict firewall. GitHub publishes [ranges of IP addresses](https://api.github.com/meta) used by hosted runners (`actions`). Alternatively, allow SSH from anywhere on 22 only if you rely on key-based auth and `PermitRootLogin`/`PasswordAuthentication` hardening.

### Branch and triggers

- Default trigger: **push to `main`**. To use another branch, edit `branches` in the workflow file.
- **Actions** tab → **Deploy to droplet** → **Run workflow** for a manual deploy.

### After adding the workflow

Commit and push `.github/workflows/deploy-droplet.yml` to `main`. The first run should appear under **Actions**; fix any secret/path errors from the job log.
