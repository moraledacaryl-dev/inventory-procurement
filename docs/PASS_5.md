# Pass 5 — Integrations and Control Plane

Completed scope:

- Sequence-backed stock document numbering under database row locks
- Automatic stock-document audit entries
- Automatic accounting outbox events created in the same transaction as stock movements
- Integration worker with row claiming, stale-lock recovery, HTTP delivery, idempotency headers, exponential retry backoff, maximum attempts, and dead-letter state
- Operator retry and controlled one-shot processing APIs
- Dead-letter notifications and audit records
- Per-user notification read receipts for global and targeted notifications
- Docker worker service and integration endpoint configuration
- Regression tests for delivery, failure, dead-letter, manual retry, idempotency, and per-user notification state

## Delivery contract

Outbound requests include:

- `Idempotency-Key` HTTP header
- event ID
- event type
- aggregate type and ID
- structured payload

A destination must return a successful HTTP response only after durably accepting or idempotently recognizing the event.

## Operational rules

- The outbox event is written in the same transaction as its source stock document.
- Workers claim rows with database locks and recover claims older than ten minutes.
- Failed events retry with exponential backoff up to one hour.
- Events move to `dead_letter` after exhausting `max_attempts`.
- Manual retry resets attempts and clears worker locks.
