# Inventory training coverage plan — 26 November 2026

Source of truth: Inventory main `07c651d0111be2840cac81b66bb1d7b97fd4c616` (22 November); Operations main `63a9e7c011ecfa140f7ae3e75612c2d5d6e4fa86` (17 November). Both fetched directly from GitHub, not inferred from an existing working tree. This matrix was written before curriculum implementation. It is a plan; release evidence must distinguish planned from working coverage.

## Architecture decision

Keep the current Next.js screens, FastAPI routes, SQLAlchemy models and business services in this repository. A separate training entry point fails closed before importing application configuration. Each participant and practice attempt has its own SQLite database, populated with fictional records. A separate training registry retains attempts and progress when practice is reset. Production entry point, migrations and deployment are separate. Browser practice opens the actual routes with contextual guidance; the server checks stock documents and workflow outcomes. No duplicate stock engine. Six real roles are used without adding department-based authorization.

Reuse the Operations approach of the actual module UI, an isolated SQLite database, first-launch setup, stable contextual guidance and standalone Next output. Improve local-only completion evidence by verifying outcomes on the server. Preserve immutable attempt history across resets. Do not reuse its Operations-specific lesson content, identities, room-state logic or API adapter. Operations provides Swift/macOS and .NET/Windows launchers with optional signing; equivalent Inventory packages require platform builds and separate evidence. Browser delivery is the first distribution path.

## Feature-to-lesson matrix

| Module | Lessons / workflows | Actual UI | Authoritative implementation | Roles that may perform changes |
|---|---|---|---|---|
| A | Physical, reserved, available; choose issue vs purchase | /stock | inventory_operations availability; inventory posting | inventory_manager, owner |
| B | Home, search, filters, scope, pagination, alerts | /dashboard, /items | dashboard, dashboard_exceptions, modules, AppShell | visibility follows role |
| C | Catalogue, classification, barcodes, conversions, supplier links, item-location controls, deactivation | /items, /items/{id}, /settings/classification | inventory, catalogue_configuration, classification | inventory_manager, owner; supplier links procurement_officer, owner |
| D | Opening stock, ledger, quantity vs value, correction | /stock, /stock/documents/{id} | inventory, stock_ledger, services/inventory | inventory_manager, owner |
| E | Issue stock, shortages, reservations, references | /stock | inventory stock/issues, services/inventory | inventory_manager, owner |
| F | Direct transfer; controlled dispatch/receipt, discrepancy; reserve/release | /stock, /inventory-operations | controlled_inventory, inventory_operations | inventory_manager, owner |
| G | Blind count, zero, incomplete, interrupted, variance, independent approval/recount, schedule/history | /counts, /counts/{id} | guided_counts, inventory, count_requires_approval | counter entry/submit; inventory_manager/owner approval |
| H | Adjustments, spoilage, expiry, damage, reasons, valuation | /inventory-operations | controlled_inventory, services/inventory | inventory_manager, owner |
| I | Supplier profiles, links, preferred supplier, performance and 360 | /suppliers, /suppliers/{id} | procurement, supplier_360 | procurement_officer, owner |
| J | Planning, stock/on-order checks, requisitions, review status | /purchasing | procurement_planning, procurement | procurement_officer, owner |
| K | Quotation comparison, award, approval limits and segregation | /purchasing | quotation_po_workspace, operational_authorization | procurement_officer with scope/limit, owner; creator cannot approve self |
| L | PO draft, approve, amend, print, outstanding, cancel | /purchasing, /purchasing/orders/{id} | procurement, quotation_po_workspace, readiness | procurement_officer with scope/limit, owner |
| M | Full/partial/damaged/expired/rejected/wrong delivery, later delivery, interruption | /receiving | receiving_workspace | receiver, owner |
| N | Return only accepted stock, duplicate protection, payable effect | /receiving | receiving_workspace, integration_worker | receiver, owner |
| O | Lots, expiry, aging, physical rotation vs automatic allocation | /inventory-operations, /reports | inventory_operations, controlled_inventory | inventory_manager, owner |
| P | Ingredients, recipe yield, waste factor, costing, revision | /production, /production/recipes/{id} | production, recipe_costing | inventory_manager, owner |
| Q | Planned/start/execute/cancel batch, actual material/yield effects | /production, /production/batches/{id} | production_execution | inventory_manager, owner |
| R | Menu, product mapping, price/selling rules, modifiers, sync | /fnb/menu, /fnb/selling-rules, /integrations/pos | menu, pos_rules, pos_sync | inventory_manager item rules; owner integration mapping |
| S | Sale consumption, mapping failures, duplicate protection, refund disposition | /integrations/pos | production POS event processing, integration_auth | owner review; service actor for events |
| T | Staff meal preview/post/reverse, cost/shortage/duplicate | /fnb/staff-meals | staff_meals service and routes | inventory_manager, owner |
| U | Rooms, reusable linen conditions, par/replenishment, issue amenities | /hotel, /hotel/property | property_operations | inventory_manager, owner |
| V | Assets, lifecycle, maintenance, treatments/depreciation | /assets, /assets/maintenance | assets, pass5_operations | inventory_manager, owner |
| W | Outbox vs intake vs accepted vs verified journal; requeue | /integrations/accounting | accounting_integration, integration_worker | owner integration controls; reports reviewers read as allowed |
| X | Operations requests/decisions, shared Staff identities, notifications | /integrations/operations, /integrations/master-data | operational_integrations, shared_master_data, staff_identity_integration | owner; service actors for inbound |
| Y | Balances, ledger, valuation/aging/expiry/waste, assurance/operating summary | /reports, /reports/operations, /reports/final-assurance | inventory_operations, final_assurance, pass6_controls | inventory_manager, procurement_officer, viewer, owner, subject to scope |
| Z | Access, monetary limits, classifications, migration, readiness/rollout, incidents, backup awareness | /settings/access-scopes, /settings/classification, /readiness, /rollout | pass6_controls, readiness, stabilization, operations | owner for access; specific route permissions elsewhere |

The complete current definition-to-role matrix is in [CURRICULUM.md](CURRICULUM.md), including all 14 duty courses.

## Role and location mapping

- Stockroom / kitchen / café / bar / housekeeping / maintenance operators: `inventory_manager` only when their actual duties need posting. Department assignment does not confer this role. Apply location scopes.
- Purchasing: `procurement_officer`. Purchase approval also needs an active matching operational scope and sufficient monetary limit; a role alone is insufficient.
- Receiving: `receiver`, restricted to authorized delivery locations. It cannot create purchase orders.
- Stock counter: `counter`. It can enter/submit counts, cannot view hidden blind quantities or approve variances.
- Department supervisor / manager: map to `inventory_manager` for stock/count controls; purchasing and integration responsibilities require separate authorized paths.
- Accounting reviewer: `viewer` for authorized read access; Inventory integration controls require owner. Training does not give Accounting permission.
- Owner / administrator: `owner`. Certification never grants production access.

## Verified rules that affect instruction

1. Controlled receiving increments PO received quantity by **arrived quantity**, including rejected goods; stock increases by **accepted quantity only**. A fully rejected delivery can therefore close an order without adding stock. Do not teach that rejected goods remain outstanding automatically.
2. Receiving requires accepted + rejected = arrived. Rejection requires a reason. Delivery references are unique per PO; idempotency keys are bound to the payload.
3. Open blind counts hide snapshots even from approvers. Pending blind counts disclose quantities only to approvers. Every nonzero counter variance requires review. A creator cannot approve their own variance. Stock movement after snapshot requires a fresh count.
4. Role permissions and operational location scopes both apply. Inactive scopes deny access; they do not revert to unrestricted access. Non-owner purchase approval requires explicit monetary authorization.
5. Direct issues and transfers cannot consume stock reserved for another operation. Quantity and monetary valuation are separate.
6. Accounting outbox completed means delivered to intake. Review acceptance and source-linked journal proof are separate. Neither proves supplier payment.
7. POS reversal and refunds need the actual inventory disposition rules. Do not automatically restore consumed food.
8. Staff-meal preview uses physical stock, so reservations require a separate allocation check. A shortage must not be bypassed with invented supplies.
9. The source accepts expiry metadata but does not guarantee physical food inspection or automatic FEFO selection. Employees must inspect and rotate real goods.

## Verification boundaries

Production browser inspection was attempted but the browser access host was unavailable. No production write is authorized or needed. Cross-app delivery must stay disabled in training, including loopback destinations. Desktop installers, signing/notarization, external Accounting journals and production fidelity require separate observed evidence; never infer them from a successful build.
