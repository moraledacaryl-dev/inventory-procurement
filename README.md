# Hidden Oasis Inventory & Procurement

Passes 1–7 establish a production-oriented inventory and procurement application for Hidden Oasis.

## Current capabilities

- Item, category, unit, barcode, conversion, and storage-location masters
- Immutable stock ledger, balances, receipts, issues, controlled transfers, adjustments, reservations, and counts
- Lot and expiry tracking, near-expiry reporting, waste and damage posting, valuation, and stock aging
- Item-location minimums, reorder quantities, preferred suppliers, cycle-count schedules, and availability controls
- Blind counts and independent approval for material count variances
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

Inventory quantities change only through posted movement documents. Lot transactions, waste, damage, transfer receipt, and count variance posting reconcile through the same ledger. Reservations affect available stock without rewriting physical stock. Production restore remains a controlled maintenance procedure documented in `docs/PASS_4.md`.
