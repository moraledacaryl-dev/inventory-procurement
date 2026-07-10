# Pass 6 — Operational Procurement Workflows

Completed scope:

- Sequence-backed numbers for purchase requisitions, quotations, purchase orders, goods receipts, and purchase returns
- Duplicate-line validation across procurement documents
- Requisition, quotation, and purchase-order quantity controls
- Purchase-order price controls against selected supplier quotations
- Segregation of duties between document creators and approvers
- Automatic audit records and outbound integration events for approvals, receipts, and returns
- Low-stock reorder suggestions that deduct open purchase-order quantities
- Automatic requisition generation from low-stock suggestions
- Preferred-supplier and minimum-order-quantity support in reorder calculations
- Supplier performance scorecards using actual PO and receipt history
- Multi-line requisition, purchase-order, and goods-receipt screens
- Operational reporting for acceptance rate, on-time rate, and delivery variance

## Reorder calculation

For each active stock-tracked item with a minimum-stock value:

`Suggested quantity = minimum stock - current stock - outstanding purchase-order quantity`

Negative suggestions are treated as zero. When a preferred supplier is assigned, its minimum order quantity is enforced.

## Supplier scorecard

The scorecard reports:

- Purchase-order count
- Completed purchase orders
- Ordered, received, accepted, and rejected value
- Acceptance percentage
- On-time delivery percentage
- Average delivery variance in days

Delivery performance is calculated only for purchase orders with an expected-delivery date and at least one goods receipt.

## Approval control

A user who created a requisition or purchase order cannot approve that same document. Approval actions are recorded in the audit trail and emitted to the relevant integration destination.
