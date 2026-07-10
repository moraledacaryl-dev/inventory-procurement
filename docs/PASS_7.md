# Pass 7 — Complete Inventory Operations

Completed scope:

- Item barcodes and direct barcode lookup
- Item-specific unit conversions with reverse conversion support
- Item-location minimums, reorder quantities, maximums, preferred suppliers, and cycle-count intervals
- Inventory lots, manufacture dates, expiry dates, supplier references, and lot balances
- Lot receipts, issues, waste, and damage posting through the authoritative stock ledger
- Physical, reserved, and available stock reporting
- Stock reservations with expiry and release controls
- Transfer orders with draft, dispatched, and received states
- Stock movement only when a dispatched transfer is acknowledged as received
- Cycle-count schedules and due-count filtering
- Blind count worksheets
- Independent approval for count variances above a configurable threshold
- Weighted-average inventory valuation
- Stock aging and active/slow/non-moving classification
- Near-expiry and expired-lot reporting
- Waste and damage quantity/value summaries
- Responsive inventory operations workspace

## Stock authority

`stock_movements` remains the sole authoritative quantity ledger. Lot balances, reservations, and transfer-order states provide operational detail without replacing the ledger.

## Availability

`Available stock = physical stock - active unexpired reservations`

Reservations do not reduce physical stock. Actual issues, transfers, waste, and damage create stock movements.

## Lot and expiry controls

Each lot is unique per item. Lot transactions update the lot balance and the item/location stock ledger in the same database transaction. The expiry report classifies positive lot balances as near-expiry or expired.

## Count governance

Blind worksheets omit system quantities. When the largest absolute variance exceeds the session threshold, the count enters `pending_approval`. The count creator cannot approve their own material variance. Approval recalculates against the current locked balance before posting the adjustment.
