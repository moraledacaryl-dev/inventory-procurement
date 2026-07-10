# Hidden Oasis Inventory & Procurement

Passes 1–4 establish a production-oriented inventory and procurement application.

## Current capabilities

- Item, category, unit, and storage-location masters
- Immutable stock ledger, balances, receipts, issues, transfers, adjustments, and counts
- Suppliers, requisitions, approvals, quotations, comparison, purchase orders, partial receiving, rejection, and returns
- Audit activity, notifications, CSV import/export, durable integration event monitoring, backups, checksums, and production preflight
- JWT authentication, RBAC, PostgreSQL migrations, responsive UI, tests, and CI security gates

## Run

```bash
cp .env.example .env
docker compose up --build
```

## Verify

```bash
cd backend && pytest && python scripts/production_preflight.py
cd ../frontend && npm run lint && npm run typecheck && npm run build
```

## Operational safety

Inventory quantities change only through posted movement documents. Corrections and returns produce reversing movements. Production restore is a controlled maintenance procedure documented in `docs/PASS_4.md`; the application does not expose a dangerous one-click live restore.
