# Hidden Oasis Inventory & Procurement

Passes 1–10 establish a complete, production-oriented inventory, procurement, recipe, integration, migration, and rollout application for Hidden Oasis.

## Current capabilities

- Item, category, unit, barcode, conversion, and storage-location masters
- Immutable stock ledger, balances, receipts, issues, controlled transfers, adjustments, reservations, and counts
- Lot and expiry tracking, near-expiry reporting, waste and damage posting, valuation, and stock aging
- Item-location minimums, reorder quantities, preferred suppliers, cycle-count schedules, and availability controls
- Blind counts and independent approval for material count variances
- Suppliers, requisitions, approvals, quotations, comparison, purchase orders, partial receiving, rejection, and returns
- Recipes/BOM, ingredient waste factors, recipe costing, production batches, actual yield, and finished-item costing
- POS product mappings, idempotent sale consumption, financial void/refund recording without ingredient restoration, and integration reconciliation
- Accounting outbox events for stock, procurement, production, POS consumption, and reversals
- Staged CSV migration, printable documents, cancellation controls, acceptance runs, deployment health, and backup verification
- Staff feedback, operational incidents, rollout go/hold status, smoke tests, and pilot rollout controls
- Audit activity, notifications, durable integration event monitoring, persistent backups, checksums, and production preflight
- JWT authentication, RBAC, PostgreSQL migrations, responsive and accessible UI, tests, and CI security gates

## Run

```bash
cp .env.example .env
docker compose up --build
```

For a non-production pilot dataset:

```bash
cd backend
python scripts/seed_demo.py
```

## Verify

```bash
cd backend && pytest && python scripts/production_preflight.py
cd ../frontend && npm run lint && npm run typecheck && npm run build
```

## Operational safety

Inventory quantities change only through posted movement documents. Lot transactions, waste, damage, transfer receipt, count variance, opening balances, production, POS consumption, and controlled corrections all reconcile through the same ledger. Reservations affect available stock without rewriting physical stock. Production restore remains a controlled maintenance procedure documented in `docs/PASS_4.md`.

## Rollout

Run the production-readiness acceptance checks and operational smoke test before staff access. Begin with a limited pilot group, resolve all critical feedback and incidents, and expand access only when rollout status is `GO`.

### Operational safety update

POS refunds and voids record financial evidence linked to the original sale. They do not restore raw recipe ingredients or reverse ingredient cost. Physical waste returns remain separate; an unused-sale stock error requires an authorized inventory adjustment after checking the physical ingredients. Historical reversals remain unchanged.

Both integration retry routes accept only failed/dead-letter outbound events. Accounting retries require integration administration permission and refuse accepted receipts, delivered reviews and posted-journal evidence. Existing event identity and payload remain unchanged.

Staff meal previews show unreserved availability. Posting rechecks active, unexpired reservations while holding the shared stock-balance locks. A preview does not reserve stock; an exact retry returns the original meal even when stock has since been consumed.

PO fulfillment counts accepted quantities. Arrivals, rejections and stock history remain intact; rejected quantities remain outstanding for replacement. Migration 0025 reopens previously received POs with rejected, unfulfilled quantities and adds a supporting receipt-line index. Closed/cancelled POs remain unchanged. Procurement, receiving and supplier views use the same fulfillment calculation. A code rollback must not silently close these replacement obligations.
