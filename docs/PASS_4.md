# Pass 4 — Production Hardening

Completed:

- Audit log query API
- User notifications and read state
- Durable integration event inbox/outbox records with idempotency and retry state
- CSV item import and item/balance exports
- Database backup records, checksums, backup script, and production preflight
- Security headers, strict production configuration checks, and RBAC-protected operations endpoints
- Search/filter/limit controls across operational APIs
- CI security audit and migration checks

Restore remains an explicit operator procedure: stop writers, verify backup checksum, restore into a new database, run migrations, validate counts and balances, then switch service configuration. Automatic in-place restore is intentionally excluded because it is unsafe for a live financial inventory system.
