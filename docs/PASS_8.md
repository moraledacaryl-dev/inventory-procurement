# Pass 8 — Recipes, Production, POS, and Accounting Integration

Completed scope:

- Versioned recipe/BOM master with ingredient quantities and waste factors
- Independent recipe approval before operational use
- Recipe costing from current location weighted-average costs
- Available-output calculation from ingredient availability
- Planned and completed production batches
- Ingredient consumption and finished-item production in one stock document
- Actual output and yield capture
- Accounting outbox events for completed production
- POS product-to-recipe and consumption-location mapping
- Idempotent completed-sale ingestion
- Automatic recipe ingredient consumption for completed POS sales
- Full stock reversal for voided or refunded sales
- Protection against duplicate sale reversal
- Accounting outbox events for POS consumption and reversal
- Integration reconciliation summary
- Responsive recipe, production, and POS mapping workspace

## Recipe costing

Recipe cost uses the weighted-average stock cost at the selected production or consumption location. Standard item cost is used when a location has no balance record.

`Ingredient requirement = recipe quantity × output factor × (1 + waste factor)`

`Output factor = requested output quantity ÷ recipe yield quantity`

## Production posting

Completing a production batch creates one immutable stock document containing:

- Negative ingredient movements
- Positive finished-item movement
- Finished-item unit cost based on consumed ingredient cost

The batch and stock document are committed together. An accounting event is queued in the same transaction.

## POS consumption

A completed POS sale resolves each external product through its active mapping, expands the approved recipe, and posts ingredient consumption. `external_event_id` and the stock-document idempotency key prevent duplicate consumption.

Voids and refunds reverse the original sale stock movements. A sale can be reversed only once.

## Integration reconciliation

The reconciliation endpoint reports pending, failed, and dead-letter outbox events together with unprocessed POS events and the most recent POS event timestamp.
