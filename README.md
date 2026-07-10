# Hidden Oasis Inventory & Procurement

Pass 2 implements the operational inventory core on top of the Pass 1 application framework.

## Completed

- Categories, units of measure, item master, and storage locations
- Immutable stock documents and movement lines
- Materialized balances by item and location
- Receipts, issues, transfers, and signed adjustments
- Negative-stock protection with per-item override
- Weighted-average cost updates on inbound stock
- Idempotency keys for safe repeated posting
- Physical count sessions and variance-generated adjustments
- Balance, low-stock, and movement-history APIs
- Working login, item, location, stock, and count screens
- Alembic migration and transaction tests

## Run

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:3000`. API documentation is available at `http://localhost:8000/docs` outside production.

## Verification

```bash
cd backend && pytest
cd ../frontend && npm run typecheck && npm run build
```

The backend suite covers authentication, health, receipt idempotency, balanced transfers, issues, negative-stock blocking, balances, and count variance posting. Procurement requisitions, quotations, purchase orders, goods receiving against POs, and supplier workflows remain Pass 3.
