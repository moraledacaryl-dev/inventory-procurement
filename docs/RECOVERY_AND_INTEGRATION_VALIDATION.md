# Inventory recovery and integration assurance (Group D)

This is a controlled, **code-only** certification runbook. It does not authorize production test transactions, a database downgrade, replay of financial events, or changes to live stock balances.

## Backup artifacts

- The scheduled backup script creates a timestamped PostgreSQL plain-SQL gzip dump (or a SQLite backup in local development). PostgreSQL output is compressed incrementally, written to a private temporary file, flushed, and atomically published only after `pg_dump` exits successfully.
- A new backup is recorded with its size and SHA-256 **before** previous recovery points can be pruned. If cataloguing fails, prior backup artifacts remain untouched.
- Verify a backup with `python backend/scripts/verify_backup.py /path/to/inventory.sql.gz --sha256 EXPECTED_DIGEST` (working directory/repository imports as configured). The verifier consumes the **complete** gzip stream to check the CRC/trailer, not merely its header. A passing checksum does not substitute for a restore rehearsal.
- The native production release uses its separate `pg_dump -Fc` backup, `pg_restore --list`, checksum gate and exact-commit release verification. Never substitute a local demo database.

## Isolated restore certification

GitHub Actions `Resilience Assurance` provisions an isolated PostgreSQL service, seeds test fixtures, creates a test database backup, restores into a second isolated database, checks table-by-table digests, and verifies readiness. It also runs synthetic stock concurrency, idempotency and outbox tests.

The `scripts/run_resilience_checks.py` test harness is **destructive**: it posts stock documents and changes synthetic integration states. It must never run against the production inventory database.

Required safeguards when running it intentionally in isolation:

1. PostgreSQL database name ends in `_resilience` or `_test`, on an isolated test instance.
2. `APP_ENV` is not `production` or `prod`.
3. `INVENTORY_ALLOW_DESTRUCTIVE_RESILIENCE_TESTS=1` is explicitly set for that test process.

GitHub's isolated resilience job sets this opt-in; the production services and deployment workflow do not.

## Integration failure recovery

- Inventory outbox delivery is at-least-once. Retain source event IDs and idempotency keys when investigating retries.
- `completed` on an Accounting outbox event means delivery to Accounting's review intake, **not** a posted journal.
- The read-only Accounting proof poller walks completed deliveries in batches, selects the oldest overdue/unverified source events, and enforces a cooldown. It must not starve older events because more than 600 newer events exist.
- An unverified, rejected, missing or inconsistent Accounting journal proof must not be presented as GL-posted. Investigate through the authorized Accounting review workflow; do not manually rewrite Inventory source event identity or force a delivery status.
- Monitor retry/dead-letter counts, reconciliation errors, and stuck claims using the Owner-only integration and assurance views. Do not use a test-runner script as a live monitoring mechanism.

## Release gate

Only merge a patch after the exact PR-head quality gates pass. After merge, require five independent successful workflows for the exact Inventory `main` SHA: CI, Browser Acceptance, Resilience Assurance, Deployment Validation, and Native Deployment Validation. Use native backup-protected deployment and verify backup checksum, exact release SHA, app/backend readiness and public reachability. Remove the temporary Accounting bridge after deployment in a separate CI-gated cleanup PR.

For production restore or schema rollback, require a separate authorized incident procedure and a tested recovery plan. A database downgrade must never be attempted automatically.
