# Inventory Training curriculum and role matrix

Curriculum version: `2026.11.27.1`. Generated from the typed definitions; review alongside source-contract.json and ENDPOINT_COVERAGE.md.

Each row is one definition with guided, assisted and independent variants. Item/quantity variants do not create additional unique business workflows. A check mark means the real source role is assigned the lesson; production location and monetary limits still apply.

| Module | Lesson ID and title | Manager | Purchasing | Receiver | Counter | Viewer | Owner | Evidence |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| A | `available-stock` — How much stock can we use? | ✓ | ✓ | ✓ |  | ✓ | ✓ | Source record inspection |
| A | `counter-foundations` — Check your count, unit and responsibility |  |  |  | ✓ |  | ✓ | Source record inspection |
| B | `find-your-work` — Find a record and check your role | ✓ | ✓ | ✓ |  | ✓ | ✓ | Source record inspection |
| C | `add-item-barcode` — Add a scan code to the intended item | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| C | `catalogue-scope-required` — Recognize when your assignment is insufficient | ✓ |  |  |  |  |  | Source protective refusal |
| C | `catalogue-units` — Read item units and conversions | ✓ | ✓ | ✓ |  | ✓ | ✓ | Source record inspection |
| C | `create-item` — Create a correctly classified item | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| C | `deactivate-empty-item` — Retire an item without erasing history | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| C | `define-unit-conversion` — Configure the direction of a unit conversion | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| C | `edit-item-reorder` — Change a minimum without changing stock | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| C | `reactivate-item` — Bring a retired item back into use | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| C | `remove-item-barcode` — Remove an obsolete scan code | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| C | `set-location-policy` — Set a stockroom-specific replenishment policy | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| C | `stock-blocks-deactivation` — Recognize why an item cannot be retired | ✓ |  |  |  |  | ✓ | Source protective refusal |
| D | `interpret-period-issues` — Filter movement history and distinguish it from closing stock | ✓ | ✓ |  |  | ✓ | ✓ | Source record inspection |
| D | `opening-stock` — Record an opening balance | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| E | `issue-bar-volume` — Measure bar syrup in the configured volume unit | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| E | `issue-cafe-case` — Convert a café case into the stock base unit | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| E | `issue-kitchen` — Issue chicken to the kitchen | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| F | `cancel-draft-transfer` — Cancel a transfer that never left | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| F | `correct-transfer-destination` — Correct a same-location transfer | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| F | `create-controlled-transfer` — Prepare a transfer without moving stock | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| F | `dispatch-controlled-transfer` — Hand over stock into in-transit control | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| F | `receive-controlled-transfer` — Acknowledge stock received from transit | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| F | `reservation-shortage` — Recognize a reservation shortage | ✓ |  |  |  |  | ✓ | Source protective refusal |
| F | `reserve-event-stock` — Set aside stock for an event | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| F | `transfer-receipt-variance` — Record a difference during transfer receipt | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| F | `transfer-stock` — Move stock to another location | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| F | `transfer-stock-became-unavailable` — Handle stock committed after a draft was prepared | ✓ |  |  |  |  | ✓ | Source protective refusal |
| F | `transfer-transit-scope-required` — Recognize a missing in-transit assignment | ✓ |  |  |  |  |  | Source protective refusal |
| G | `approve-count` — Review a colleague's count variance | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| G | `blind-count` — Count what is physically there | ✓ |  |  | ✓ |  | ✓ | Source business/master outcome |
| G | `cancel-unused-count` — Cancel a duplicate count safely | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| G | `cap-monthly-count` — Close a blind monthly count with independent review | ✓ |  |  | ✓ |  | ✓ | Linked source outcomes in one database |
| G | `count-multiple-units` — Count kilograms and individual kits correctly | ✓ |  |  | ✓ |  | ✓ | Source business/master outcome |
| G | `count-zero` — Record zero stock and save your work | ✓ |  |  | ✓ |  | ✓ | Source business/master outcome |
| G | `interpret-posted-count` — Read an independently posted count difference | ✓ |  |  |  | ✓ | ✓ | Source record inspection |
| G | `request-count-recheck` — Return a questionable line for recount | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| G | `save-incomplete-count` — Save an unfinished count without inventing zeros | ✓ |  |  | ✓ |  | ✓ | Source business/master outcome |
| G | `stale-count-snapshot` — Stop when stock moved after counting began | ✓ |  |  | ✓ |  | ✓ | Source protective refusal |
| G | `start-full-count` — Start and complete a new blind count | ✓ |  |  | ✓ |  | ✓ | Source business/master outcome |
| H | `approved-opening-correction` — Correct a documented opening-entry overstatement | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| H | `expired-lot-writeoff` — Write off expired stock from its specific batch | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| H | `interpret-waste-value` — Trace the quantity and value of recorded waste | ✓ | ✓ |  |  | ✓ | ✓ | Source record inspection |
| H | `record-waste` — Record spoiled supplies | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| H | `stock-screen-signed-correction` — Record an authorized signed balance correction | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| I | `create-supplier` — Add a fictional supplier with clear terms |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| I | `deactivate-unused-supplier` — Retire a supplier after checking open orders |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| I | `edit-supplier-terms` — Update approved contact and payment terms |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| I | `link-supplier-item` — Link an item to its preferred supplier |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| I | `open-orders-block-deactivation` — Handle a supplier with outstanding obligations |  | ✓ |  |  |  | ✓ | Source protective refusal |
| I | `reactivate-supplier` — Reactivate an approved supplier identity |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| I | `supplier-profile` — Find a supplier and check its history | ✓ | ✓ | ✓ |  | ✓ | ✓ | Source record inspection |
| I | `unlink-obsolete-supplier-item` — Remove an obsolete supplier-item link |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| J | `approve-purchase-request` — Review and approve another person's request |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| J | `reject-duplicate-request` — Reject an unnecessary purchase request |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| J | `request-purchase` — Check stock before requesting a purchase |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| J | `request-self-approval` — Recognize independent request approval |  | ✓ |  |  |  | ✓ | Source protective refusal |
| K | `award-timely-quotation` — Compare price with the required delivery time |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| K | `cap-busy-weekend` — Source weekend demand and follow the linked delivery |  | ✓ |  |  |  | ✓ | Linked source outcomes in one database |
| K | `inspect-awarded-order` — Find the order already created from an offer |  | ✓ |  |  |  | ✓ | Source record inspection |
| K | `purchase-approval` — Review purchasing authority and quotations |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| K | `record-supplier-quotation` — Record a supplier's actual offer |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| L | `amend-draft-order` — Correct a draft before independent approval |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| L | `cancel-unreceived-order` — Cancel an order before any receipt |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| L | `inspect-approved-order-lock` — Recognize that an approved order is controlled |  | ✓ |  |  |  | ✓ | Source record inspection |
| L | `inspect-received-order-lock` — Recognize that receipts prevent cancellation |  | ✓ |  |  |  | ✓ | Source record inspection |
| L | `order-supplies` — Create an order without receiving stock |  | ✓ |  |  |  | ✓ | Source business/master outcome |
| L | `purchase-approval-limit` — Recognize an approval above your limit |  | ✓ |  |  |  |  | Source protective refusal |
| M | `cap-delivery-recovery` — Handle a damaged delivery and a later supplier return |  |  | ✓ |  |  | ✓ | Linked source outcomes in one database |
| M | `check-order` — Check the order before posting |  |  | ✓ |  |  | ✓ | Source business/master outcome |
| M | `damaged-delivery` — Reject damaged goods at the door |  |  | ✓ |  |  | ✓ | Source business/master outcome |
| M | `expired-delivery` — Reject expired goods |  |  | ✓ |  |  | ✓ | Source business/master outcome |
| M | `full-delivery` — Receive a complete delivery |  |  | ✓ |  |  | ✓ | Source business/master outcome |
| M | `fully-rejected` — Record a fully rejected delivery |  |  | ✓ |  |  | ✓ | Source business/master outcome |
| M | `later-delivery` — Receive the remaining order later |  |  | ✓ |  |  | ✓ | Source business/master outcome |
| M | `partial-delivery` — Receive only what arrived |  |  | ✓ |  |  | ✓ | Source business/master outcome |
| M | `quantity-discrepancy` — Record a delivery quantity difference |  |  | ✓ |  |  | ✓ | Source business/master outcome |
| M | `resume-delivery` — Continue an interrupted receipt |  |  | ✓ |  |  | ✓ | Source business/master outcome |
| M | `wrong-item` — Handle an incorrect item |  |  | ✓ |  |  | ✓ | Source business/master outcome |
| N | `supplier-return` — Return previously accepted goods |  |  | ✓ |  |  | ✓ | Source business/master outcome |
| O | `create-traceable-lot` — Identify a batch before recording its quantity | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| O | `expiry-rotation` — Check lots and expiry before use | ✓ | ✓ |  |  | ✓ | ✓ | Source record inspection |
| O | `issue-specific-lot` — Issue from the batch actually used | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| O | `lot-quantity-shortage` — Respect a batch-specific shortage | ✓ |  |  |  |  | ✓ | Source protective refusal |
| O | `tracked-opening-receipt` — Record an approved opening quantity against a lot | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| P | `approve-colleague-recipe` — Independently approve a checked formula | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| P | `calculate-food-margin` — Compare food cost, gross profit and margin | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| P | `create-governed-recipe` — Create a recipe with explicit units and preparation waste | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| P | `recipe-cost` — Check a recipe's ingredients and yield | ✓ |  |  |  | ✓ | ✓ | Source record inspection |
| P | `recipe-self-approval` — Keep recipe creation and approval independent | ✓ |  |  |  |  | ✓ | Source protective refusal |
| P | `retire-obsolete-recipe` — Retire a formula without deleting history | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| Q | `batch-production` — Record actual batch yield | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| Q | `cancel-started-production` — Cancel started preparation with material accountability | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| Q | `cancel-unstarted-production` — Cancel a plan before ingredients are used | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| Q | `cap-restaurant-service` — Trace raw ingredients into prepared portions, sales and staff meals | ✓ |  |  |  |  | ✓ | Linked source outcomes in one database |
| Q | `interpret-actual-yield-cost` — Follow actual production output to its posted cost | ✓ |  |  |  | ✓ | ✓ | Source record inspection |
| Q | `plan-production-batch` — Plan output before recording actual production | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| R | `assign-menu-selling-controls` — Assign approved selling rules and shared add-ons | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| R | `correct-reusable-add-on-price` — Correct an approved reusable add-on price | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| R | `create-conditional-price-rule` — Define a conditional selling rule | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| R | `create-menu-with-modifier` — Create a menu variant and a priced optional choice | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| R | `create-reusable-add-ons` — Create reusable multiple-choice pizza add-ons | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| R | `deactivate-conditional-price-rule` — Retire an expired promotion without deleting it | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| R | `menu-mapping` — Understand menu and POS product links | ✓ |  |  |  |  | ✓ | Source record inspection |
| S | `activate-verified-pos-mapping` — Activate a checked product-recipe mapping |  |  |  |  |  | ✓ | Source business/master outcome |
| S | `disable-stale-pos-mapping` — Stop a mapping that points to a retired formula |  |  |  |  |  | ✓ | Source business/master outcome |
| S | `inspect-cooked-sale-return` — Review discarded prepared food without restoring raw ingredients |  |  |  |  | ✓ | ✓ | Source record inspection |
| S | `inspect-pos-duplicate-delivery` — Verify that a repeated POS event did not deduct twice |  |  |  |  | ✓ | ✓ | Source record inspection |
| S | `inspect-unmapped-pos-refusal` — Recognize a refused unmapped sale without inventing a failed row |  |  |  |  | ✓ | ✓ | Source record inspection |
| S | `inspect-unused-sale-void` — Trace a verified unused-sale correction to its linked reversal |  |  |  |  | ✓ | ✓ | Source record inspection |
| S | `map-pos-product` — Link a POS product to its approved recipe |  |  |  |  |  | ✓ | Source business/master outcome |
| S | `retry-eligible-inbound-event` — Requeue one reviewed failed POS event |  |  |  |  |  | ✓ | Source business/master outcome |
| S | `sale-consumption` — Trace a made-to-order POS sale to four ingredients |  |  |  |  | ✓ | ✓ | Source record inspection |
| T | `reverse-duplicate-staff-meal` — Reverse a duplicate meal that never consumed stock | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| T | `staff-meal` — Record supplies used for staff meals | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| T | `staff-meal-shortage` — Stop an unprepared meal when ingredients are short | ✓ |  |  |  |  | ✓ | Source protective refusal |
| U | `cap-housekeeping` — Prepare rooms and trace the same linen through laundry | ✓ |  |  |  |  | ✓ | Linked source outcomes in one database |
| U | `configure-room-par` — Set a room standard without issuing stock | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| U | `housekeeping-supplies` — Prepare guest rooms with the right supplies | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| U | `issue-clean-linen` — Issue clean towels without treating them as consumed | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| U | `return-clean-linen` — Return verified clean towels to availability | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| U | `send-used-linen-to-laundry` — Hand used towels into laundry control | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| V | `asset-maintenance` — Distinguish assets from consumable supplies | ✓ |  |  |  |  | ✓ | Source record inspection |
| V | `complete-maintenance-work` — Close completed work and advance its schedule | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| V | `create-maintenance-plan` — Schedule preventive work for a specific asset | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| V | `create-maintenance-work-order` — Record a specific maintenance job | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| V | `post-reviewed-depreciation` — Post a reviewed depreciation run once | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| V | `prepare-depreciation-run` — Prepare a monthly value allocation for review | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| V | `register-fixed-asset` — Register one identifiable asset | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| V | `start-maintenance-work` — Record that authorized work has begun | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| W | `accounting-proof` — Read Accounting delivery and journal evidence |  |  |  |  | ✓ | ✓ | Source record inspection |
| W | `create-accounting-mapping` — Record a reviewer-approved Accounting mapping |  |  |  |  |  | ✓ | Source business/master outcome |
| W | `requeue-failed-accounting-handoff` — Retry a failed handoff without claiming a posted journal |  |  |  |  |  | ✓ | Source business/master outcome |
| X | `accept-accountable-operations-work` — Accept connected work with an accountable assignee |  |  |  |  |  | ✓ | Source business/master outcome |
| X | `acknowledge-operational-alert` — Read an alert without treating it as completed work | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| X | `cap-owner-review` — Follow accountable work through handover and local financial retry |  |  |  |  |  | ✓ | Linked source outcomes in one database |
| X | `complete-evidenced-operations-work` — Complete work after its real handover |  |  |  |  |  | ✓ | Source business/master outcome |
| X | `connected-work` — Know where connected work belongs |  |  |  |  |  | ✓ | Source record inspection |
| X | `reject-duplicate-operations-work` — Reject a connected request without inventing a transaction |  |  |  |  |  | ✓ | Source business/master outcome |
| X | `submit-workflow-feedback` — Report a specific workflow problem | ✓ |  |  |  |  | ✓ | Source business/master outcome |
| Y | `interpret-assurance-evidence` — Separate stock reconciliation from recovery readiness | ✓ | ✓ |  |  | ✓ | ✓ | Source record inspection |
| Y | `interpret-stock-valuation` — Read stock value without mixing physical units | ✓ | ✓ |  |  | ✓ | ✓ | Source record inspection |
| Y | `interpret-supplier-acceptance` — Distinguish arrived goods from usable supplier delivery | ✓ | ✓ |  |  | ✓ | ✓ | Source record inspection |
| Y | `management-review` — Investigate stock and purchasing reports | ✓ | ✓ |  |  | ✓ | ✓ | Source record inspection |
| Y | `save-report-scope` — Save the intended report scope |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `admin-controls` — Check access and recover safely |  |  |  |  |  | ✓ | Source record inspection |
| Z | `assign-location-approval-scope` — Assign a bounded location and approval limit |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `check-isolated-rollout` — Interpret a diagnostic test alongside rollout gates |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `classify-legacy-ingredient` — Classify an existing ingredient deliberately |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `correct-storage-location-label` — Correct a location name without moving stock |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `create-authorized-storage-location` — Create an approved storage location |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `create-operating-department` — Add an approved department classification |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `import-initial-balances` — Establish an initial balance before any movements |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `import-item-catalogue` — Import a verified item catalogue |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `import-supplier-catalogue` — Import verified supplier details |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `record-assurance-review` — Record an honest assurance snapshot |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `refuse-duplicate-opening-import` — Protect an existing ledger from a second opening import |  |  |  |  |  | ✓ | Source protective refusal |
| Z | `reject-invalid-csv` — Keep an invalid migration unapplied |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `resolve-verified-feedback` — Close feedback only after its fix is verified |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `resolve-verified-incident` — Close an operational incident with verified recovery |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `retire-unused-classification` — Retire an unused department without deleting it |  |  |  |  |  | ✓ | Source business/master outcome |
| Z | `run-isolated-acceptance` — Record acceptance failures without hiding them |  |  |  |  |  | ✓ | Source business/master outcome |

## Duty courses

| Course | Source role | Assigned definitions | Fresh duty-final tasks |
|---|---|---:|---|
| Stock and department supplies (`role-inventory_manager`) | `inventory_manager` | 93 | `cap-monthly-count`, `cap-restaurant-service`, `reservation-shortage` |
| Purchasing (`role-procurement_officer`) | `procurement_officer` | 33 | `cap-busy-weekend`, `request-self-approval`, `purchase-approval-limit` |
| Receiving deliveries (`role-receiver`) | `receiver` | 16 | `cap-delivery-recovery`, `check-order` |
| Physical stock counts (`role-counter`) | `counter` | 8 | `cap-monthly-count`, `count-zero`, `stale-count-snapshot` |
| Reports and review (`role-viewer`) | `viewer` | 20 | `available-stock`, `management-review` |
| Owner and administration (`role-owner`) | `owner` | 160 | `cap-owner-review`, `cap-busy-weekend`, `cap-monthly-count` |
| Stockroom and inventory (`stockroom`) | `inventory_manager` | 51 | `cap-monthly-count`, `transfer-receipt-variance`, `reservation-shortage` |
| Kitchen preparation (`kitchen`) | `inventory_manager` | 23 | `cap-restaurant-service`, `record-waste` |
| Cafe supplies and service (`cafe`) | `inventory_manager` | 20 | `transfer-receipt-variance`, `staff-meal`, `available-stock` |
| Bar supplies and service (`bar`) | `inventory_manager` | 19 | `transfer-receipt-variance`, `record-waste`, `available-stock` |
| Housekeeping and linen (`housekeeping`) | `inventory_manager` | 11 | `cap-housekeeping`, `available-stock` |
| Maintenance and assets (`maintenance`) | `inventory_manager` | 10 | `create-maintenance-work-order`, `complete-maintenance-work`, `asset-maintenance` |
| Department supervision (`department-supervisor`) | `inventory_manager` | 19 | `cap-monthly-count`, `recipe-self-approval`, `request-count-recheck` |
| Accounting-related inventory review (`accounting-review`) | `viewer` | 20 | `available-stock`, `management-review` |

Viewer reviews use the actual permitted reporting endpoints. Integration writes require separately authorized owner responsibility. Neither a training path, synthetic counterpart nor certificate grants production authority.
