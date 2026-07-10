# Pass 10 — Stabilization and Staff Rollout

Completed scope:

- Staff feedback capture with severity, workflow/page context, assignment, and resolution
- Operational incident register with request IDs, acknowledgement, and resolution
- Go/hold rollout summary based on critical feedback, incidents, and dead-letter events
- Repeatable operational smoke test for database, masters, ledger reconciliation, integrations, and backups
- Pilot rollout console for owners and managers
- Idempotent Hidden Oasis demo/pilot data seed
- Accessibility improvements including skip navigation, visible keyboard focus, semantic landmarks, reduced-motion support, and mobile form controls
- Rollout regression coverage and final stabilization runbook

## Pilot rollout

Use a limited pilot group first:

1. Owner or general manager
2. Inventory manager
3. Receiver or storekeeper
4. One café or kitchen user

Operate for at least seven real business days. Review feedback, incidents, integration exceptions, backup status, stock variances, receiving records, and POS consumption daily.

## Go-live decision

The rollout summary returns `GO` only when:

- No open high or critical staff feedback exists
- No unresolved critical incident exists
- No dead-letter integration event exists

The latest acceptance run and smoke test should also pass before broader staff rollout.

## Smoke test

The smoke test verifies:

- Database connectivity
- Item endpoint and location endpoint availability
- Stock balance reconciliation against the immutable movement ledger
- Zero dead-letter events
- Presence of a backup record

## Demo seed

Run after migrations and owner bootstrap in a non-production or pilot environment:

```bash
python scripts/seed_demo.py
```

The script is idempotent and creates sample Hidden Oasis categories, units, locations, inventory items, and suppliers without duplicating existing records.

## Incident handling

Record incidents using the request ID shown in API error responses whenever available. Use this lifecycle:

```text
Open → Acknowledged → Resolved
```

Critical incidents place rollout status on hold until resolved.

## Final rollout sequence

1. Deploy the validated release.
2. Run migrations and production preflight.
3. Confirm automated backups and perform a restoration drill.
4. Import verified real data.
5. Run acceptance and smoke tests.
6. Train the pilot group.
7. Run the pilot for at least seven business days.
8. Resolve all critical feedback and incidents.
9. Confirm rollout status is GO.
10. Expand access by department while monitoring daily.
