# Pass 9 — Production Readiness, Migration, and Acceptance

Completed scope:

- Controlled CSV validation and staged application for items, suppliers, and opening balances
- Import job history with row counts, validation errors, status, and audit records
- Safe cancellation rules for requisitions, purchase orders, and planned production batches
- Printable purchase-order and goods-receipt payloads
- Deployment readiness status for database, integration backlog, dead letters, and backup age
- Repeatable release-acceptance runs with stock-ledger reconciliation
- Persistent acceptance history and results
- Production security headers, trusted-host enforcement, request-size limits, and stricter CORS
- Stronger production preflight validation
- Daily backup container with persistent backup volume
- Backup checksum and format verification command
- Responsive production-readiness and migration console
- Automated regression tests for imports, cancellations, printable data, deployment checks, acceptance, and security headers

## Migration sequence

1. Validate item CSV.
2. Correct all reported errors.
3. Apply item import.
4. Validate and apply supplier import.
5. Configure locations.
6. Validate opening balances.
7. Apply opening balances before any live stock transactions.
8. Run acceptance checks and reconcile all differences before staff rollout.

Imports are staged. Validation never changes live master or stock data. Only a validated job can be applied, and each job can be applied once.

## Release acceptance

Acceptance runs check:

- Database connectivity
- Stock balance versus immutable movement ledger
- Dead-letter integration events
- Presence of a recorded backup

A failed acceptance run remains in history with detailed results. Staff rollout should require the latest run to pass.

## Backup verification

```bash
python scripts/verify_backup.py /backups/inventory-YYYYMMDDTHHMMSSZ.sql.gz --sha256 <recorded-checksum>
```

Verification confirms the checksum and validates that the decompressed file resembles a PostgreSQL dump. This is not a substitute for a scheduled restoration drill into an isolated database.

## Production deployment order

1. Configure PostgreSQL, HTTPS, deployed hostnames, and secrets.
2. Run `python scripts/production_preflight.py`.
3. Run Alembic migrations.
4. Start API, worker, backup, and frontend services.
5. Confirm API and database health checks.
6. Apply staged migration data.
7. Run acceptance checks.
8. Test POS and Accounting event delivery and reversal.
9. Complete a backup restoration drill.
10. Roll out to a limited user group before full staff adoption.
