# Native deployment: inventory.hiddenoasis.app

Verified server convention:

- App: `/opt/inventory-procurement-online`
- User/group: `hiddenoasis:hiddenoasis`
- Backend: `127.0.0.1:8300`
- Frontend: `127.0.0.1:3300`
- Backend env: `/etc/hiddenoasis/inventory-backend.env`
- Frontend env: `/etc/hiddenoasis/inventory-frontend.env`
- Database: `hiddenoasis_inventory_live`
- Database user: `hiddenoasis_inventory_app`
- Nginx site: `/etc/nginx/sites-available/inventory-hiddenoasis`

Do not run the Docker deployment script on this server.

After the database and environment files are created, run:

```bash
cd /opt/inventory-procurement-online
chmod +x deploy/install-native.sh
./deploy/install-native.sh
```

Then issue HTTPS:

```bash
certbot --nginx -d inventory.hiddenoasis.app
```

Verify:

```bash
curl -I https://inventory.hiddenoasis.app/login
curl https://inventory.hiddenoasis.app/api/v1/ready
systemctl status hiddenoasis-inventory-backend hiddenoasis-inventory-frontend hiddenoasis-inventory-worker --no-pager
systemctl list-timers hiddenoasis-inventory-backup.timer --no-pager
```


## Certified GitHub Actions production deployment (preferred)

Workflow: `.github/workflows/deploy-inventory-native.yml` (**Deploy Inventory Native**).

- Runs after successful `CI` on `main`, or manually with an exact release SHA.
- Requires all **five** exact-SHA, push-triggered quality gates to have passed: CI, Browser Acceptance, Resilience Assurance, Deployment Validation, and Native Deployment Validation.
- Requires `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY` secrets accessible to the workflow (and `SERVER_PORT` for a nonstandard SSH port). Configure these in the Inventory repository or an authorized `inventory-production` environment; never commit credentials.
- Uses an immutable SHA of `appleboy/ssh-action`, runs a fetched exact-release script on the native server, and verifies the backend, frontend and public login.
- Server must have a clean tracked Git checkout and passwordless root or `sudo -n` access for the deployment user.
- The native installer blocks release unless it can confirm a writable PostgreSQL primary and at least 2 GiB free, create a **pre-migration** `pg_dump -Fc` of `hiddenoasis_inventory_live`, verify it with `pg_restore --list`, record its SHA-256 checksum, and pass production preflight.
- Backups live under `/var/backups/hiddenoasis/inventory/releases` with private filesystem permissions. Preserve previous good releases and backup logs for audit.
- Any failed gate leaves the production release unverified. Do **not** label a GitHub validation workflow as a deployed release.
- When a schema has been upgraded, never automatically downgrade the production database. Investigate with the verified pre-migration backup available for restoration to an isolated database.

For an explicit emergency on-server release, only after matching all quality gates on a specific `main` SHA:

```bash
sudo bash /opt/inventory-procurement-online/deploy/release-native.sh EXACT_40_CHARACTER_SHA
```

If the server checkout does not yet include this release helper, extract the helper from the requested commit with `git show` and run it, as in the GitHub Actions workflow. Do not replace the current production checkout with an unverified or dirty tree. After activation, save the exact `INVENTORY DEPLOYMENT GATE: PASS` output and the backup filename/checksum.
