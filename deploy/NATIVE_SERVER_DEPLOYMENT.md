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
