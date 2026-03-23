# ordered-api on a DigitalOcean droplet

Django ASGI behind **Gunicorn + UvicornWorker**, static files via **WhiteNoise**, database via **Supabase** (`DATABASE_URL` in `.env`). Put **TLS on nginx** (or another reverse proxy); the app listens on **127.0.0.1:8000** only.

---

## A. Prereqs (one-time)

**Droplet:** Ubuntu 22.04 or 24.04, 1–2 GB RAM. **Firewall:** open 22 (SSH), 80 (HTTP), 443 (HTTPS). Do not open Postgres on the droplet if you use Supabase.

**Docker:** Install Docker Engine and the Compose plugin using Docker’s Ubuntu guide.

**Repo on the server:** Clone into a fixed directory (examples use `~/ordered-api`). Copy `.env.example` to `.env` and fill production values (`DEBUG=False`, `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, Supabase vars — see `.env.example`).

**First run (migrations + container):** if you have not already:

`docker compose -f deploy/docker-compose.droplet.yml run --rm web python manage.py migrate`

`docker compose -f deploy/docker-compose.droplet.yml up -d --build`

If that succeeded, the API is running on the droplet at `127.0.0.1:8000`. Everything below assumes you SSH in and `cd` to the same directory that contains `manage.py` and `deploy/`.

### Browser CORS (operator / Next.js)

With **`DEBUG=False`**, `CORS_ALLOWED_ORIGINS` in `.env` must list every **frontend origin** that calls the API in the browser (scheme + host, no path). Example for Ordered HQ:

`CORS_ALLOWED_ORIGINS=https://operator.orderedhq.com`

Use commas for multiple apps (e.g. `https://operator.orderedhq.com,https://app.orderedhq.com`). Then rebuild/restart the web container. If this is wrong or empty, the browser shows **“CORS header Access-Control-Allow-Origin missing”** even when the API returns **200**; `curl` without an `Origin` header will still look fine.

If nginx adds CORS headers too, avoid conflicting or duplicate `Access-Control-*` headers—usually it is simpler to let **Django** (`django-cors-headers`, already first in `MIDDLEWARE`) emit them.

---

## B. Daily work: SSH in

From your laptop (replace user and host):

`ssh root@YOUR_DROPLET_IP`

or

`ssh deploy@api.yourdomain.com`

Go to the app (adjust path if yours differs):

`cd ~/ordered-api`

---

## C. Put the API on the public internet (nginx + HTTPS)

Do this on the **droplet** after SSH (still in `~/ordered-api` or use absolute paths where noted).

**1. Install nginx**

`sudo apt update`

`sudo apt install -y nginx`

**2. Copy the example site config (HTTP only first)**

The example file only listens on **port 80** until you run Certbot. Nginx will **not** accept a `listen 443 ssl` block until real `ssl_certificate` files exist, so do not paste a full HTTPS config before certificates.

`sudo cp ~/ordered-api/deploy/nginx-ordered-api.conf.example /etc/nginx/sites-available/ordered-api`

Replace `api.example.com` with your hostname:

`sudo sed -i 's/api.example.com/api.yourdomain.com/g' /etc/nginx/sites-available/ordered-api`

(or `sudo nano /etc/nginx/sites-available/ordered-api`)

**3. Enable the site**

`sudo ln -sf /etc/nginx/sites-available/ordered-api /etc/nginx/sites-enabled/ordered-api`

`sudo nginx -t`

`sudo systemctl reload nginx`

**4. TLS with Let’s Encrypt (adds HTTPS to this config)**

`sudo apt install -y certbot python3-certbot-nginx`

`sudo certbot --nginx -d api.yourdomain.com`

Use your real hostname. Certbot edits nginx to add certificates and a TLS listener. After this, browser traffic should be HTTPS and `X-Forwarded-Proto` should be `https` for those requests.

**5. If you already broke `nginx -t` with a hand-made `443 ssl` block**

Overwrite with the repo example (HTTP only), fix `server_name`, then steps 3–4 again:

`sudo cp ~/ordered-api/deploy/nginx-ordered-api.conf.example /etc/nginx/sites-available/ordered-api`

`sudo sed -i 's/api.example.com/api.yourdomain.com/g' /etc/nginx/sites-available/ordered-api`

`sudo nginx -t`

`sudo systemctl reload nginx`

**6. Redirect loops**

If Django keeps redirecting, confirm nginx sends `X-Forwarded-Proto` on HTTPS vhosts (Certbot usually keeps your `location /` block). Only then consider `SECURE_SSL_REDIRECT=False` in `.env`.

---

## D. Ship a new version (manual, on the droplet)

SSH in, then:

`cd ~/ordered-api`

`git pull`

`docker compose -f deploy/docker-compose.droplet.yml up -d --build`

`docker compose -f deploy/docker-compose.droplet.yml run --rm web python manage.py migrate --noinput`

Static assets are collected during the **image build**, so `--build` is what refreshes them.

---

## E. Logs and health checks (on the droplet)

Container logs:

`docker compose -f deploy/docker-compose.droplet.yml logs -f web`

See running services:

`docker compose -f deploy/docker-compose.droplet.yml ps`

Hit the app locally on the server (bypasses nginx):

`curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/`

(Adjust path if you do not serve `/`; use a real health or API path you expose.)

---

## F. Auto-deploy from GitHub Actions

Workflow: `.github/workflows/deploy-droplet.yml`. On each push to **`main`** or **`master`**, GitHub SSHs into the droplet, `git fetch` / `reset` to that branch, rebuilds Docker, runs `migrate`. **Manual runs** use the branch you pick in the Actions UI.

You need **two different SSH-related things** (do not mix them up):

### F1. GitHub → droplet (so Actions can run commands)

This is **only** for the runner to open an SSH session as your Linux user (e.g. `root`).

On your **laptop** (not on the droplet):

`ssh-keygen -t ed25519 -f ./gha-ordered-api-deploy -N "" -C "github-actions-ordered-api"`

You get `gha-ordered-api-deploy` (private) and `gha-ordered-api-deploy.pub` (public).

On the **droplet**, install the **public** key for the user that will own the repo (example for `root`):

`mkdir -p ~/.ssh`

`chmod 700 ~/.ssh`

`echo 'PASTE_CONTENT_OF_gha-ordered-api-deploy.pub_HERE' >> ~/.ssh/authorized_keys`

`chmod 600 ~/.ssh/authorized_keys`

On **GitHub** → repo **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | What to paste |
|--------|----------------|
| `DROPLET_HOST` | Droplet IP (e.g. `164.92.x.x`) or `api.orderedhq.com` if SSH listens there |
| `DROPLET_USER` | `root` (or whatever user you used above) |
| `DROPLET_SSH_KEY` | **Entire** contents of `gha-ordered-api-deploy` (private file), including `-----BEGIN` / `END` lines |
| `DROPLET_DEPLOY_PATH` | Absolute path to the clone on the server, e.g. `/root/ordered-api` — must be the directory that contains `manage.py` |

Keep the **private** key only in GitHub Secrets (and optionally a password manager). Never commit it.

### F2. Droplet → GitHub (so `git fetch` works)

This is **separate** from F1. The droplet must be able to read the repo from GitHub.

- **Public repo:** if `origin` is HTTPS, `git fetch` usually works with no extra key.
- **Private repo:** add a **Deploy key** (read-only): on the droplet, `ssh-keygen -t ed25519 -f ~/.ssh/github_ordered_api_readonly -N ""`, add **`github_ordered_api_readonly.pub`** under GitHub **Settings → Deploy keys**, check **Allow read access**. Set `git remote` to SSH and use `~/.ssh/config` so `Host github.com` uses `IdentityFile ~/.ssh/github_ordered_api_readonly`.

Test on the droplet:

`cd /root/ordered-api`

`git fetch origin`

### F3. Firewall

If the droplet firewall only allows SSH from your home IP, GitHub’s runners will be blocked. Allow SSH from [GitHub Actions IP ranges](https://api.github.com/meta) (key `"actions"`), or temporarily allow SSH from `0.0.0.0/0` if you rely on key-only auth and a strong setup.

### F4. Commit the workflow and push

The workflow file must exist on the branch you push (`main` or `master`). Then open **Actions** and confirm a run starts (or **Run workflow** manually).

**Run manually:** GitHub → **Actions** → **Deploy to droplet** → **Run workflow** → choose branch.

---

## G. Without Docker (short version)

On the droplet: Python 3.12+, venv, `pip install -r requirements.txt`, same `.env`, then:

`python manage.py collectstatic --noinput`

`python manage.py migrate`

`gunicorn ordered_api.asgi:application -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000`

Run that last command under **systemd** in production. Nginx still proxies to `127.0.0.1:8000`.

---

## H. Optional Gunicorn tuning

Set in `.env` on the server (used by the Docker image): `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`. See `.env.example`.
