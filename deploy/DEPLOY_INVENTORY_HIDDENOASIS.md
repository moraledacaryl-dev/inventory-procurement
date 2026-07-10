# Deploy to inventory.hiddenoasis.app

The repository is prepared to run behind the existing server reverse proxy using:

- Frontend: `127.0.0.1:3300`
- API: `127.0.0.1:8800`
- Public URL: `https://inventory.hiddenoasis.app`
- Public API: `https://inventory.hiddenoasis.app/api/v1`

The PostgreSQL database is not exposed publicly.

## 1. DNS action required

In the DNS control panel for `hiddenoasis.app`, create:

| Type | Name | Value | Proxy |
|---|---|---|---|
| A | inventory | SERVER_PUBLIC_IPV4 | DNS only initially |

If the server has IPv6, an AAAA record may also be added. Wait until the record resolves to the server before requesting the certificate.

Check from a computer:

```bash
dig +short inventory.hiddenoasis.app
```

## 2. Connect to the server

```bash
ssh root@SERVER_IP
```

Choose a deployment directory:

```bash
mkdir -p /opt/hiddenoasis
cd /opt/hiddenoasis
```

Clone the private repository if it is not present:

```bash
git clone git@github.com:moraledacaryl-dev/inventory-procurement.git
cd inventory-procurement
```

For an existing clone:

```bash
cd /opt/hiddenoasis/inventory-procurement
git fetch origin
git checkout main
git pull --ff-only origin main
```

## 3. Create production secrets

```bash
cp .env.production.example .env.production
nano .env.production
```

Replace every `REPLACE_WITH...` value.

Generate secure values on the server:

```bash
openssl rand -hex 32
openssl rand -base64 36
```

Use a URL-safe password for `POSTGRES_PASSWORD`, because it is included in `DATABASE_URL`. The password in `POSTGRES_PASSWORD` and `DATABASE_URL` must be identical.

Required deployed values:

```env
APP_ENV=production
CORS_ORIGINS=["https://inventory.hiddenoasis.app"]
TRUSTED_HOSTS=["inventory.hiddenoasis.app"]
```

Do not commit `.env.production`.

## 4. Start the application locally on the server

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

The script:

1. Rejects placeholder secrets.
2. Validates the Compose file.
3. Builds production images.
4. Runs production preflight.
5. Runs database migrations.
6. Creates the owner account.
7. Starts PostgreSQL, API, worker, backups, and frontend.
8. Verifies local frontend and API health.

Confirm manually:

```bash
curl -I http://127.0.0.1:3300/login
curl http://127.0.0.1:8800/api/v1/ready
```

## 5. Configure Nginx and HTTPS

The supplied final Nginx configuration is:

```text
deploy/inventory.hiddenoasis.app.nginx.conf
```

### When Certbot and Nginx are already installed

First create a temporary HTTP-only site so Certbot can issue the certificate:

```bash
cat >/etc/nginx/sites-available/inventory.hiddenoasis.app <<'NGINX'
server {
    listen 80;
    listen [::]:80;
    server_name inventory.hiddenoasis.app;

    location /api/ {
        proxy_pass http://127.0.0.1:8800;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:3300;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX

ln -sfn /etc/nginx/sites-available/inventory.hiddenoasis.app /etc/nginx/sites-enabled/inventory.hiddenoasis.app
nginx -t
systemctl reload nginx
```

Request the certificate:

```bash
certbot --nginx -d inventory.hiddenoasis.app
```

Then install the hardened final config:

```bash
cp deploy/inventory.hiddenoasis.app.nginx.conf /etc/nginx/sites-available/inventory.hiddenoasis.app
nginx -t
systemctl reload nginx
```

## 6. Verify the public deployment

```bash
curl -I https://inventory.hiddenoasis.app/login
curl https://inventory.hiddenoasis.app/api/v1/ready
```

Open in a browser:

```text
https://inventory.hiddenoasis.app/login
```

Sign in using the owner email and password placed in `.env.production`.

## 7. Run release checks

Inside the app:

1. Open **Production Readiness**.
2. Confirm database and deployment status.
3. Confirm a backup is recorded.
4. Run acceptance checks.
5. Open **Rollout & Stabilization**.
6. Run the operational smoke test.
7. Do not begin broad staff rollout unless both pass.

## Updating later

```bash
cd /opt/hiddenoasis/inventory-procurement
git fetch origin
git checkout main
git pull --ff-only origin main
./deploy/deploy.sh
```

## Logs and status

```bash
docker compose --env-file .env.production -f docker-compose.production.yml ps
docker compose --env-file .env.production -f docker-compose.production.yml logs -f --tail=200 api
docker compose --env-file .env.production -f docker-compose.production.yml logs -f --tail=200 web
docker compose --env-file .env.production -f docker-compose.production.yml logs -f --tail=200 worker
```

## Rollback

Application rollback:

```bash
git log --oneline -10
git checkout PREVIOUS_GOOD_COMMIT
./deploy/deploy.sh
```

Database migrations should not be downgraded casually. Restore a verified backup into an isolated database first and assess migration compatibility before any database rollback.
