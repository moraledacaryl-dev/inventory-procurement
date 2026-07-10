# Architecture
Inventory & Procurement is the source of truth for physical goods and the operational buying lifecycle.

## Technology
- Next.js/TypeScript frontend
- FastAPI/SQLAlchemy backend
- PostgreSQL production database
- Alembic migrations
- JWT authentication and role/permission authorization

## Design rules
1. Stable immutable IDs.
2. Append-only stock movement ledger.
3. Corrections by reversal, not silent overwrites.
4. Idempotent external events.
5. Audit sensitive state transitions.
6. No direct cross-database writes.
