# Hidden Oasis Inventory & Procurement

Passes 1–8 establish a production-oriented inventory, procurement, recipe, and integration application for Hidden Oasis.

## Current capabilities

- Item, category, unit, barcode, conversion, and storage-location masters
- Immutable stock ledger, balances, receipts, issues, controlled transfers, adjustments, reservations, and counts
- Lot and expiry tracking, near-expiry reporting, waste and damage posting, valuation, and stock aging
- Item-location minimums, reorder quantities, preferred suppliers, cycle-count schedules, and availability controls
- Blind counts and independent approval for material count variances
- Suppliers, requisitions, approvals, quotations, comparison, purchase orders, partial receiving, rejection, and returns
- Recipes/BOM, ingredient waste factors, recipe costing, production batches, actual yield, and finished-item costing
- POS product mappings, idempotent sale consumption, sale void/refund reversal, and integration reconciliation
- Accounting outbox events for stock, procurement, production, POS consumption, and reversals
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

Inventory quantities change only through posted movement documents. Lot transactions, waste, damage, transfer receipt, count variance, production, POS consumption, and POS reversals all reconcile through the same ledger. Reservations affect available stock without rewriting physical stock. Production restore remains a controlled maintenance procedure documented in `docs/PASS_4.md`.
