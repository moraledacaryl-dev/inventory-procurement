# Curriculum expansion following the verified milestone

The tested milestone at `334d0aa6735603addc4600dc80cf8d2fb4f2a7fd` remains available as a draft package. All eight GitHub workflows passed, including real workflow tests on the macOS and Windows native builds. This is not the full definition of done.

The next implementation pass addresses the endpoint matrix's assessed-workflow gaps in this order:

| Area | Concrete practice to add | Required authority | Evidence |
|---|---|---|---|
| C: Catalogue | Create an item with classification and base unit; edit reorder defaults; add a barcode; define a conversion; deactivate a zero-stock item; recognize blocked deactivation with stock | Item-maintenance permission and explicitly global operational access | Saved real item/configuration, unchanged stock/ledger and intended lifecycle status |
| I: Suppliers | Create a supplier; edit contact/payment terms; link an item and preferred supplier; deactivate safely | Supplier-maintenance permission and global operational access | Actual supplier record/link, no invented purchasing obligation |
| F/G: Controls | Reservations and release, controlled transfer dispatch/receipt/discrepancy, scheduled and multi-item counts, recount and stale-snapshot recovery | Source-defined role and location scopes | Real movements/reservations/count states and independent approvals |
| J–L: Procurement | Request review/rejection, quotations/comparison/award, PO amendments/cancellation | Source-defined approval segregation and monetary limits | Real requisition/quote/PO relationships and statuses |
| P–T: Food workflows | Recipe authoring/revision, production exceptions, menu and modifiers, synthetic POS consumption/refund and staff meal reversal | Real UI/endpoint permissions | Actual ingredient movements, recipe links and explicit financial-handoff states |
| U/V/W/Z | Linen/par, asset and maintenance mutations, sandbox integration decisions/recovery, restricted master controls | Source-defined permission boundaries | Actual isolated records and disabled external delivery |
| Capstones | Six linked business scenarios with one evolving sandbox, deterministic authorized counterparties and independent final outcomes | Never escalate a trainee's role to cover another person's responsibilities | Linked record IDs and end-to-end state; separate task attempts do not count as capstones |
| Assessments | Role-level multi-objective practical assessments and diagnostic results | Only completed applicable role paths | Calibrated knowledge/practical scores and 100% critical transaction objectives |

The meaningful-scenario target remains at least 100, subject to supported features. Changing only quantities, item names or guidance mode does not create an additional scenario. Each new workflow requires source inspection, concrete curriculum content, deterministic setup, read-only validation, correction, reset/recovery and desktop/mobile real-control tests before it is reported as implemented.

## First expansion evidence

The catalogue/supplier pass adds 16 distinct action exercises, bringing the course to 53 lessons (40 action exercises, including three expected control refusals, and 13 record inspections). All three modes of each new action exercise pass real backend checks. Local verification: 121 training backend tests and 108 desktop/mobile browser tests passed. New recovery tests verify item-draft checkpoints, supplier reset isolation and two-tab mutation protection. The course now fingerprints 183 operational sources. This is source-build evidence; fresh native CI remains separate. The other expansion rows above remain required work.
