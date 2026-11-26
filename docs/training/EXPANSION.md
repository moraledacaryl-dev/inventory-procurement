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

## Controlled stock/count pass: source-reviewed implementation plan

The next distinct scenarios use `/inventory-operations`, `/counts` and `/counts/{id}`: reserve stock; reject over-reservation; create/dispatch/receive/cancel a controlled transfer; receive a shortage with its reason; correct a same-location transfer; handle stock becoming unavailable before dispatch; create a full count; count multiple units; save an intentionally incomplete count without treating blank as zero; request a targeted recount; refuse a stale snapshot; cancel an unused count; post an approved historical correction; create lot metadata; record a tracked opening receipt; issue a specific lot; write off an expired lot; refuse an issue exceeding that lot's balance.

Validators will check source, destination and in-transit balances, exact stock-document kinds/costs, lot quantities, reservation totals, count statuses and independent actor evidence. Blind-count outcomes must not disclose snapshots. Fixture counterparties use real services for pre-existing dispatches and stock changes.

Source limitations are explicit: the current employee Inventory Operations screen has reservation creation and availability, but no release/list control. The release API is therefore excluded from employee GUI practice until the operational application exposes it. Similarly, the cycle-count schedule APIs have no schedule editor in the current Counts or Inventory Operations screens; the existing item-location count interval is a policy and does not itself open a scheduled count. These are source-supported API capabilities, not verified employee UI workflows; no training-only button will pretend otherwise. Training instructions should direct employees to their authorized coordinator without exposing API details.

## Controlled stock/count evidence

The pass implements 22 distinct scenarios, including the explicit in-transit location-scope refusal. The course now has 75 lessons: 62 action exercises (eight expected control refusals) and 13 record inspections. All three practice modes have real backend outcome checks. Verification passed: 169 training backend tests, 307 inherited backend tests (five skipped), 156 desktop/mobile browser tests, TypeScript, source-contract validation and lint (five existing warnings, no errors). Two additional browser runs captured the actual completed transfer variance record on both viewports. The current instruction and target must both remain visible and cannot overlap in guided browser checks.

Recovery resolves newly created count IDs, retains partial blind-count entries and never exposes hidden snapshots in evidence. Expected API refusals retain the entered form. Fixture references now require explicit braces, so a literal stock-document kind cannot accidentally become a record ID. Private registry directories and files are restricted to their local user on POSIX, including directories created before startup. Native packaging evidence remains tied to its separately identified commit until the expanded native builds pass.
