# Endpoint coverage inventory

Extracted from the current source, not README claims. Supporting reads do not imply complete workflow mastery. The 26-module planning matrix is in COVERAGE.md. Unimplemented changes remain required work; they are not certified or silently excluded. Service delivery is disabled intentionally for isolation.

| Endpoint | Source | Permission | Current coverage |
|---|---|---|---|
| `GET /integrations/accounting/workspace` | `accounting_integration.py` | integrations.read | Supporting UI / record inspection |
| `POST /integrations/accounting/receipts` | `accounting_integration.py` | Service/session boundary | Disabled in training; sandbox adapter or separate onboarding applies |
| `POST /integrations/accounting/events/{event_id}/requeue` | `accounting_integration.py` | integrations.* | Assessed: reviewed failed-event retry preserves identity/amount; local pending state, no delivery worker |
| `GET /assets` | `assets.py` | inventory.read | Supporting UI / record inspection |
| `POST /assets` | `assets.py` | inventory.* | Assessed: unique physical tag, classification, location, dates, cost and useful life |
| `POST /assets/{asset_id}/events` | `assets.py` | inventory.* | Excluded from employee GUI practice: lifecycle API has no event action form in current Assets screen; steward process required |
| `GET /depreciation-runs` | `assets.py` | reports.read | Supporting UI / record inspection |
| `POST /depreciation-runs` | `assets.py` | inventory.* | Assessed: correct period and draft amount; unchanged accumulated depreciation |
| `POST /depreciation-runs/{run_id}/post` | `assets.py` | inventory.* | Assessed: reviewed run posts once with exact book value effect and pending local Accounting handoff |
| `POST /auth/login` | `auth.py` | Service/session boundary | Disabled in training; sandbox adapter or separate onboarding applies |
| `POST /auth/logout` | `auth.py` | Service/session boundary | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /auth/me` | `auth.py` | Service/session boundary | Supporting UI / record inspection |
| `GET /items/{item_id}/configuration` | `catalogue_configuration.py` | items.read | Supporting UI / record inspection |
| `PATCH /supplier-items/{link_id}` | `catalogue_configuration.py` | suppliers.* | Excluded from employee GUI practice: ItemConfigurationPanel exposes create/remove links but no PATCH editor |
| `DELETE /supplier-items/{link_id}` | `catalogue_configuration.py` | suppliers.* | Assessed: remove obsolete sourcing link while retaining supplier, original approved PO and unchanged stock |
| `PATCH /items/{item_id}/barcodes/{barcode_id}` | `catalogue_configuration.py` | items.* | Excluded from employee GUI practice: ItemConfigurationPanel exposes add/remove barcodes but no PATCH editor |
| `DELETE /items/{item_id}/barcodes/{barcode_id}` | `catalogue_configuration.py` | items.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `PATCH /items/{item_id}/conversions/{conversion_id}` | `catalogue_configuration.py` | items.* | Excluded from employee GUI practice: ItemConfigurationPanel exposes conversion creation/read only, no existing-row editor |
| `PATCH /item-location-settings/{setting_id}` | `catalogue_configuration.py` | inventory.* | Excluded from employee GUI practice: ItemConfigurationPanel exposes policy creation/read only, no existing-row editor |
| `GET /classification/dimensions` | `classification.py` | items.read | Supporting UI / record inspection |
| `GET /classification/bootstrap` | `classification.py` | items.read | Supporting UI / record inspection |
| `POST /classification/dimensions` | `classification.py` | items.* | Assessed: approved department master with stable code/workspace; no access or stock grant |
| `PATCH /classification/dimensions/{dimension_id}` | `classification.py` | items.* | Assessed: retire verified unused non-system department while preserving code/history |
| `GET /classification/items` | `classification.py` | items.read | Supporting UI / record inspection |
| `PATCH /classification/items/{item_id}` | `classification.py` | items.* | Assessed: classify original ingredient with derived record class and unchanged SKU, base unit and stock |
| `POST /classification/items/bulk-assign` | `classification.py` | items.* | Excluded from employee GUI practice: Operating Structure saves individual existing items; no bulk-assign control |
| `GET /inventory-controls/adjustments` | `controlled_inventory.py` | inventory.read | Supporting UI / record inspection |
| `POST /inventory-controls/adjustments` | `controlled_inventory.py` | inventory.* | Assessed real business/control outcome |
| `GET /inventory-controls/waste` | `controlled_inventory.py` | inventory.read | Supporting UI / record inspection |
| `POST /inventory-controls/waste` | `controlled_inventory.py` | inventory.* | Assessed business outcome |
| `GET /transfer-orders/workspace` | `controlled_inventory.py` | inventory.read | Supporting UI / record inspection |
| `GET /transfer-orders/{transfer_id}/detail` | `controlled_inventory.py` | inventory.read | Supporting UI / record inspection |
| `POST /transfer-orders/{transfer_id}/dispatch` | `controlled_inventory.py` | inventory.* | Assessed real business/control outcome |
| `POST /transfer-orders/{transfer_id}/receive` | `controlled_inventory.py` | inventory.* | Assessed real business/control outcome |
| `POST /transfer-orders/{transfer_id}/cancel` | `controlled_inventory.py` | inventory.* | Assessed real business/control outcome |
| `POST /transfer-orders/{transfer_id}/receive` | `controlled_inventory_compat.py` | inventory.* | Assessed real business/control outcome |
| `GET /dashboard/summary` | `dashboard.py` | inventory.read | Supporting UI / record inspection |
| `GET /dashboard/valuation-history` | `dashboard.py` | inventory.read | Supporting UI / record inspection |
| `GET /dashboard/exceptions` | `dashboard_exceptions.py` | inventory.read | Supporting UI / record inspection |
| `GET /reports/final-assurance` | `final_assurance.py` | reports.read | Supporting UI / record inspection |
| `POST /reports/final-assurance/record` | `final_assurance.py` | reports.read | Assessed: immutable honest snapshot retains missing-backup failure and reconciled stock evidence |
| `GET /reports/final-assurance.csv` | `final_assurance.py` | reports.read | Supporting UI / record inspection |
| `GET /counts/workspace` | `guided_counts.py` | counts.read | Supporting UI / record inspection |
| `GET /counts/locations` | `guided_counts.py` | counts.read | Supporting UI / record inspection |
| `GET /counts/{count_id}/detail` | `guided_counts.py` | counts.read | Assessed: counter fundamentals, blind observations, saved-line recovery, independent approval and posted history; no invented inventory-read permission |
| `PUT /counts/{count_id}/entries` | `guided_counts.py` | counts.create | Assessed business outcome |
| `POST /counts/{count_id}/submit` | `guided_counts.py` | counts.submit | Assessed business outcome |
| `POST /counts/{count_id}/recount` | `guided_counts.py` | counts.approve | Assessed real business/control outcome |
| `POST /counts/{count_id}/approve-guided` | `guided_counts.py` | counts.approve | Assessed business outcome |
| `POST /counts/{count_id}/cancel-guided` | `guided_counts.py` | counts.approve | Assessed real business/control outcome |
| `GET /health` | `health.py` | Service/session boundary | Supporting UI / record inspection |
| `GET /ready` | `health.py` | Service/session boundary | Supporting UI / record inspection |
| `GET /categories` | `inventory.py` | items.read | Supporting UI / record inspection |
| `POST /categories` | `inventory.py` | items.* | Excluded from employee GUI practice: current item/configuration forms select categories; no standalone category editor |
| `GET /units` | `inventory.py` | items.read | Supporting UI / record inspection |
| `POST /units` | `inventory.py` | items.* | Excluded from employee GUI practice: current item/configuration forms select units; no standalone unit editor |
| `GET /locations` | `inventory.py` | locations.read | Supporting UI / record inspection |
| `POST /locations` | `inventory.py` | locations.* | Assessed: approved stable code, name, type and parent; actual POST and empty new location, no invented creation audit |
| `GET /items` | `inventory.py` | items.read | Supporting UI / record inspection |
| `POST /items` | `inventory.py` | items.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /items/catalogue-workspace` | `inventory.py` | items.read | Supporting UI / record inspection |
| `GET /items/{item_id}` | `inventory.py` | items.read | Supporting UI / record inspection |
| `PATCH /items/{item_id}` | `inventory.py` | items.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /stock/balances` | `inventory.py` | inventory.read | Supporting UI / record inspection |
| `GET /stock/movements` | `inventory.py` | inventory.read | Supporting UI / record inspection |
| `POST /stock/receipts` | `inventory.py` | inventory.* | Assessed business outcome |
| `POST /stock/issues` | `inventory.py` | inventory.* | Assessed business outcome |
| `POST /stock/transfers` | `inventory.py` | inventory.* | Assessed business outcome |
| `POST /stock/adjustments` | `inventory.py` | inventory.* | Assessed additional Stock-screen variant of verified signed correction; exact quantity/cost/reference, not a new stock engine |
| `POST /counts` | `inventory.py` | counts.create | Assessed real business/control outcome |
| `GET /counts` | `inventory.py` | counts.read | Supporting UI / record inspection |
| `GET /counts/{count_id}/worksheet` | `inventory.py` | counts.read | Supporting UI / record inspection |
| `POST /counts/{count_id}/post` | `inventory.py` | counts.submit | Excluded compatibility route: actual blind-count screen uses assessed entries/submit and its governed posting decision |
| `POST /counts/{count_id}/approve` | `inventory.py` | counts.approve | Excluded compatibility route: actual count screen uses assessed approve-guided with independent actor safeguards |
| `GET /items/barcode/{barcode}` | `inventory_operations.py` | items.read | Supporting UI / record inspection |
| `GET /items/{item_id}/barcodes` | `inventory_operations.py` | items.read | Supporting UI / record inspection |
| `POST /items/{item_id}/barcodes` | `inventory_operations.py` | items.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /items/{item_id}/conversions` | `inventory_operations.py` | items.read | Supporting UI / record inspection |
| `POST /items/{item_id}/conversions` | `inventory_operations.py` | items.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /items/{item_id}/convert` | `inventory_operations.py` | items.read | Supporting UI / record inspection |
| `GET /item-location-settings` | `inventory_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /item-location-settings` | `inventory_operations.py` | inventory.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /lots` | `inventory_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /lots` | `inventory_operations.py` | inventory.* | Assessed real business/control outcome |
| `GET /lot-balances` | `inventory_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /lot-transactions` | `inventory_operations.py` | inventory.* | Assessed real business/control outcome |
| `GET /availability` | `inventory_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /reservations` | `inventory_operations.py` | inventory.* | Assessed real business/control outcome |
| `POST /reservations/{reservation_id}/release` | `inventory_operations.py` | inventory.* | API-only; no employee UI in current source. Explicit exclusion until upstream UI exists |
| `GET /transfer-orders` | `inventory_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /transfer-orders` | `inventory_operations.py` | inventory.* | Assessed real business/control outcome |
| `POST /transfer-orders/{transfer_id}/dispatch` | `inventory_operations.py` | inventory.* | Assessed real business/control outcome |
| `POST /transfer-orders/{transfer_id}/receive` | `inventory_operations.py` | inventory.* | Assessed real business/control outcome |
| `GET /cycle-count-schedules` | `inventory_operations.py` | counts.create | Supporting UI / record inspection |
| `POST /cycle-count-schedules` | `inventory_operations.py` | counts.create | API-only; no current employee schedule editor. Item policy interval is taught separately |
| `GET /reports/valuation` | `inventory_operations.py` | reports.read | Supporting UI / record inspection |
| `GET /reports/aging` | `inventory_operations.py` | reports.read | Supporting UI / record inspection |
| `GET /reports/expiry` | `inventory_operations.py` | reports.read | Supporting UI / record inspection |
| `GET /reports/waste` | `inventory_operations.py` | reports.read | Supporting UI / record inspection |
| `GET /locations/{location_id}` | `location_controls.py` | locations.read | Supporting UI / record inspection |
| `PATCH /locations/{location_id}` | `location_controls.py` | locations.* | Assessed: correct original display name while preserving stable code, type, hierarchy and stock |
| `GET /fnb/menu` | `menu.py` | items.read | Supporting UI / record inspection |
| `POST /fnb/menu` | `menu.py` | items.* | Assessed: actual variant, station, availability and optional priced modifier |
| `PUT /fnb/menu/{item_id}` | `menu.py` | items.* | Assessed: conditional target tag/price and reusable group assignment, retaining SKU, recipe link, base price, availability and POS visibility |
| `POST /integrations/operations/requests` | `operational_integrations.py` | Service/session boundary | Disabled in training; sandbox adapter or separate onboarding applies |
| `GET /integrations/operations/workspace` | `operational_integrations.py` | integrations.read | Supporting UI / record inspection |
| `POST /integrations/operations/requests/{event_id}/decision` | `operational_integrations.py` | integrations.* | Assessed: owner accepts with canonical assignee, rejects duplicate or completes evidenced handover; only local pending status outbox |
| `GET /audit-logs` | `operations.py` | reports.read | Supporting UI / record inspection |
| `GET /notifications` | `operations.py` | reports.read | Supporting UI / record inspection |
| `POST /notifications/{notification_id}/read` | `operations.py` | reports.read | Assessed: acknowledge own operational alert without correcting or completing its underlying work |
| `GET /integration-events` | `operations.py` | reports.read | Supporting UI / record inspection |
| `POST /integration-events` | `operations.py` | procurement.* | Excluded from employee GUI practice: event inbox has inspection/retry but no arbitrary event-creation form; real service intake remains disabled |
| `POST /integration-events/{event_id}/retry` | `operations.py` | procurement.* | Assessed only for a reviewed eligible failed inbound POS event; preserve event/payload identity and pending local state. Generic route lacks accepted-financial safeguards; dedicated Accounting controls required |
| `POST /integration-events/process` | `operations.py` | procurement.* | Disabled in training; sandbox adapter or separate onboarding applies |
| `GET /exports/items.csv` | `operations.py` | reports.read | Supporting UI / record inspection |
| `GET /exports/balances.csv` | `operations.py` | reports.read | Supporting UI / record inspection |
| `POST /imports/items.csv` | `operations.py` | items.* | Excluded compatibility route: Readiness uses assessed migration/imports validation plus controlled apply; no direct legacy-upload control |
| `GET /backups` | `operations.py` | reports.read | Supporting UI / record inspection |
| `GET /maintenance/plans` | `pass5_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /maintenance/plans` | `pass5_operations.py` | inventory.* | Assessed: exact asset, interval, checklist and first due date |
| `GET /maintenance/work-orders` | `pass5_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /maintenance/work-orders` | `pass5_operations.py` | inventory.* | Assessed: one-off job, asset, priority and schedule; current UI has no parts entry |
| `POST /maintenance/work-orders/{work_order_id}/start` | `pass5_operations.py` | inventory.* | Assessed: existing actual work enters in_progress |
| `POST /maintenance/work-orders/{work_order_id}/complete` | `pass5_operations.py` | inventory.* | Assessed: completed zero-charge work advances linked plan and local handoff; current button has no non-zero cost/parts editor |
| `GET /purchase-line-treatments` | `pass5_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /purchase-line-treatments` | `pass5_operations.py` | inventory.* | Excluded from employee GUI practice: API exists but no current purchase-treatment form; steward review required |
| `GET /accounting-mappings` | `pass5_operations.py` | reports.read | Supporting UI / record inspection |
| `POST /accounting-mappings` | `pass5_operations.py` | inventory.* | Assessed: reviewer-approved practice debit/credit mapping; no invented external journal or payment |
| `GET /access-scope-users` | `pass6_controls.py` | users.* | Supporting UI / record inspection |
| `GET /access-scopes` | `pass6_controls.py` | users.* | Supporting UI / record inspection |
| `POST /access-scopes` | `pass6_controls.py` | users.* | Assessed: exact approved person, bounded location and monetary limit; unchanged role and stock |
| `GET /saved-views` | `pass6_controls.py` | inventory.read | Supporting UI / record inspection |
| `POST /saved-views` | `pass6_controls.py` | inventory.read | Assessed: own F&B filter definition without default or stock change; current table has no Apply shortcut |
| `GET /reports/operating-summary` | `pass6_controls.py` | reports.read | Supporting UI / record inspection |
| `GET /classification/migration-review` | `pass6_controls.py` | inventory.read | Supporting UI / record inspection |
| `GET /fnb/pos-rules` | `pos_rules.py` | items.read | Supporting UI / record inspection |
| `POST /fnb/pos-rules/pricing` | `pos_rules.py` | items.* | Assessed: approved qualifying/discounted group relationship; unchanged stock and no invented POS synchronization |
| `PUT /fnb/pos-rules/pricing/{rule_id}` | `pos_rules.py` | items.* | Assessed: deactivate expired rule while retaining its groups, priority and history |
| `POST /fnb/pos-rules/modifiers` | `pos_rules.py` | items.* | Assessed: reusable optional multi-select pizza add-ons with exact independent prices |
| `PUT /fnb/pos-rules/modifiers/{template_id}` | `pos_rules.py` | items.* | Assessed: correct approved shared add-on price while preserving option identities and other prices |
| `GET /integrations/pos/catalog` | `pos_sync.py` | Service/session boundary | Supporting UI / record inspection |
| `GET /integrations/pos/workspace` | `pos_sync.py` | integrations.read | Supporting UI / record inspection |
| `POST /pos-mappings/{mapping_id}/activate` | `pos_sync.py` | integrations.* | Assessed: exact product/approved recipe/location; no historical sale consumption; retirement invalidates assessment |
| `POST /pos-mappings/{mapping_id}/deactivate` | `pos_sync.py` | integrations.* | Assessed: disable confirmed stale recipe mapping without reversing old sales |
| `GET /suppliers` | `procurement.py` | suppliers.read | Supporting UI / record inspection |
| `POST /suppliers` | `procurement.py` | suppliers.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /suppliers/{supplier_id}/items` | `procurement.py` | suppliers.read | Supporting UI / record inspection |
| `POST /suppliers/{supplier_id}/items` | `procurement.py` | suppliers.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /supplier-performance` | `procurement.py` | reports.read | Supporting UI / record inspection |
| `GET /reorder-suggestions` | `procurement.py` | procurement.read | Supporting UI / record inspection |
| `POST /reorder-suggestions/requisition` | `procurement.py` | procurement.* | Excluded compatibility route: actual RequisitionWorkspace uses assessed procurement/planning/requisitions; no legacy reorder-submit control |
| `GET /requisitions` | `procurement.py` | procurement.read | Supporting UI / record inspection |
| `POST /requisitions` | `procurement.py` | procurement.* | Excluded compatibility route: actual RequisitionWorkspace uses assessed procurement/planning/requisitions; no separate legacy-create form |
| `POST /requisitions/{requisition_id}/approve` | `procurement.py` | procurement.* | Assessed: independent request approval and self-approval refusal |
| `POST /requisitions/{requisition_id}/reject` | `procurement.py` | procurement.* | Assessed: reject duplicate demand |
| `GET /quotations` | `procurement.py` | procurement.read | Supporting UI / record inspection |
| `POST /quotations` | `procurement.py` | procurement.* | Assessed: actual supplier price, delivery and payment terms |
| `GET /requisitions/{requisition_id}/quotation-comparison` | `procurement.py` | procurement.read | Supporting comparison; deadline-aware offer decision assessed through quotation workspace |
| `GET /purchase-orders` | `procurement.py` | procurement.read | Supporting UI / record inspection |
| `POST /purchase-orders` | `procurement.py` | procurement.* | Assessed business outcome |
| `POST /purchase-orders/{po_id}/approve` | `procurement.py` | procurement.* | Assessed business outcome |
| `POST /purchase-orders/{po_id}/receipts` | `procurement.py` | receiving.* | Excluded compatibility route: current Receiving uses assessed controlled receiving/purchase-orders handler, not this older form |
| `GET /goods-receipts` | `procurement.py` | receiving.read | Supporting UI / record inspection |
| `POST /purchase-orders/{po_id}/returns` | `procurement.py` | receiving.* | Excluded compatibility route: current Receiving uses assessed receiving/purchase-orders return handler |
| `GET /procurement/planning` | `procurement_planning.py` | procurement.read | Supporting UI / record inspection |
| `POST /procurement/planning/requisitions` | `procurement_planning.py` | procurement.* | Assessed business outcome |
| `GET /procurement/requisitions/workspace` | `procurement_planning.py` | procurement.read | Supporting UI / record inspection |
| `GET /recipes/item-options` | `production.py` | inventory.read | Supporting UI / record inspection |
| `GET /recipes` | `production.py` | inventory.read | Supporting UI / record inspection |
| `POST /recipes` | `production.py` | inventory.* | Assessed: base-unit formula, yield, waste allowance and required ingredient |
| `POST /recipes/{recipe_id}/approve` | `production.py` | inventory.* | Assessed: independent formula approval and creator refusal |
| `GET /recipes/{recipe_id}/cost` | `production.py` | reports.read | Supporting UI / record inspection |
| `GET /production-batches` | `production.py` | inventory.read | Supporting UI / record inspection |
| `POST /production-batches` | `production.py` | inventory.* | Assessed: plan from approved recipe without prematurely moving stock |
| `POST /production-batches/{batch_id}/complete` | `production.py` | inventory.* | Excluded compatibility route: actual execution screen uses assessed start/execute with actual materials, yield and waste |
| `GET /pos-mappings` | `production.py` | integrations.read | Supporting UI / record inspection |
| `POST /pos-mappings` | `production.py` | integrations.* | Assessed: exact external product, approved recipe and consumption location |
| `POST /integrations/pos/events` | `production.py` | Service/session boundary | Disabled in training; sandbox adapter or separate onboarding applies |
| `GET /integrations/reconciliation` | `production.py` | integrations.read | Supporting UI / record inspection |
| `GET /production-batches/{batch_id}/execution-detail` | `production_execution.py` | inventory.read | Supporting UI / record inspection |
| `POST /production-batches/{batch_id}/start` | `production_execution.py` | inventory.* | Assessed business outcome |
| `POST /production-batches/{batch_id}/execute` | `production_execution.py` | inventory.* | Assessed business outcome |
| `POST /production-batches/{batch_id}/cancel` | `production_execution.py` | inventory.* | Assessed: planned and started cancellation, required actual material disposition and unchanged stock; dialog retains errors and entries |
| `GET /property/balances` | `property_operations.py` | inventory.read | Supporting UI / record inspection |
| `GET /property/movements` | `property_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /property/movements` | `property_operations.py` | inventory.* | Assessed: clean issue, used-linen laundry handover and verified clean return; conserve condition/location totals |
| `GET /hotel/par-profiles` | `property_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /hotel/par-profiles` | `property_operations.py` | inventory.* | Assessed: approved room standard with location; no physical issuance |
| `GET /procurement/quotation-workspace` | `quotation_po_workspace.py` | procurement.read | Supporting UI / record inspection |
| `POST /requisitions/{requisition_id}/award-quotation` | `quotation_po_workspace.py` | procurement.* | Assessed: justified offer award creates one linked draft PO |
| `GET /purchase-orders/{po_id}/detail` | `quotation_po_workspace.py` | procurement.read | Assessed: linked awarded draft, approval limit, amendment lock and receipt cancellation lock |
| `PATCH /purchase-orders/{po_id}/amend` | `quotation_po_workspace.py` | procurement.* | Assessed: correct draft commercial terms without approval or stock movement |
| `POST /purchase-orders/{po_id}/cancel-workspace` | `quotation_po_workspace.py` | procurement.* | Assessed: authorized pre-receipt cancellation and retained local handoff |
| `POST /migration/imports/{import_type}/validate` | `readiness.py` | inventory.* | Assessed: real multipart fixed-fictional CSV; item/supplier/opening inputs and duplicate-SKU validation errors |
| `GET /migration/imports` | `readiness.py` | reports.read | Supporting UI / record inspection |
| `POST /migration/imports/{job_id}/apply` | `readiness.py` | inventory.* | Assessed: item/supplier import and genuine first opening; invalid/repeated opening refusals; saved original-job recovery |
| `POST /requisitions/{document_id}/cancel` | `readiness.py` | procurement.* | Excluded from employee GUI practice: no requisition-cancellation control in current Purchasing/RequisitionWorkspace; retain approval/rejection guidance |
| `POST /purchase-orders/{document_id}/cancel` | `readiness.py` | procurement.* | Excluded compatibility route: actual order screen uses assessed cancel-workspace with controlled source obligations |
| `GET /print/purchase-orders/{document_id}` | `readiness.py` | procurement.read | Supporting UI / record inspection |
| `GET /print/goods-receipts/{document_id}` | `readiness.py` | receiving.read | Supporting UI / record inspection |
| `GET /deployment/status` | `readiness.py` | reports.read | Supporting UI / record inspection |
| `POST /acceptance-runs` | `readiness.py` | inventory.* | Assessed: actual failed run preserves missing-backup evidence; production-candidate is only the inherited record label |
| `GET /acceptance-runs` | `readiness.py` | reports.read | Supporting UI / record inspection |
| `GET /receiving/workspace` | `receiving_workspace.py` | receiving.read | Supporting UI / record inspection |
| `POST /receiving/purchase-orders/{po_id}` | `receiving_workspace.py` | receiving.* | Assessed business outcome |
| `POST /receiving/purchase-orders/{po_id}/returns` | `receiving_workspace.py` | receiving.* | Assessed business outcome |
| `GET /recipes/costing/workspace` | `recipe_costing.py` | reports.read | Supporting UI / record inspection |
| `GET /recipes/{recipe_id}/costing-detail` | `recipe_costing.py` | reports.read | Supporting UI / record inspection |
| `POST /recipes/{recipe_id}/margin-scenario` | `recipe_costing.py` | reports.read | Assessed: actual latest calculation at assigned location/price with unchanged stock/menu; captures only the two task-specific inputs |
| `POST /recipes/{recipe_id}/revise` | `recipe_costing.py` | inventory.* | Excluded from employee GUI practice: API has no revision editor in current Recipe screens; ask authorized recipe steward |
| `POST /recipes/{recipe_id}/retire` | `recipe_costing.py` | inventory.* | Assessed: authorized retirement retains version/history |
| `GET /shared-identities` | `shared_master_data.py` | users.read | Supporting UI / record inspection |
| `GET /shared-identities/{canonical_user_id}` | `shared_master_data.py` | users.read | Supporting UI / record inspection |
| `GET /shared-identities/resolve/by-email` | `shared_master_data.py` | users.read | Supporting UI / record inspection |
| `GET /master-data/workspace` | `shared_master_data.py` | integrations.read | Supporting UI / record inspection |
| `POST /master-data/publish` | `shared_master_data.py` | integrations.* | Disabled in training; sandbox adapter or separate onboarding applies |
| `POST /feedback` | `stabilization.py` | inventory.read | Assessed: specific non-sensitive usability feedback using actual location-scoped staff form |
| `GET /feedback` | `stabilization.py` | reports.read | Supporting UI / record inspection |
| `PATCH /feedback/{feedback_id}` | `stabilization.py` | reports.read | Assessed: resolve only verified matching feedback and retain original reporter/message |
| `POST /incidents` | `stabilization.py` | reports.read | Excluded from employee GUI practice: Rollout supports incident review/resolution but no incident-creation form |
| `GET /incidents` | `stabilization.py` | reports.read | Supporting UI / record inspection |
| `PATCH /incidents/{incident_id}` | `stabilization.py` | reports.read | Assessed: resolve verified connection interruption with actual original-document evidence; no fabricated backup restore |
| `GET /rollout/summary` | `stabilization.py` | reports.read | Supporting UI / record inspection |
| `POST /rollout/smoke-test` | `stabilization.py` | reports.read | Assessed: actual diagnostic retains failed backup check; GO summary alone is insufficient |
| `POST /integrations/staff/employees` | `staff_identity_integration.py` | Service/session boundary | Disabled in training; sandbox adapter or separate onboarding applies |
| `GET /staff-meals` | `staff_meals.py` | inventory.read | Supporting UI / record inspection |
| `GET /staff-meals/{meal_id}` | `staff_meals.py` | inventory.read | Supporting UI / record inspection |
| `POST /staff-meals/preview` | `staff_meals.py` | inventory.read | Assessed supporting step: actual ingredient/cost preview before staff-meal posting; linked preparation capstone prevents double raw consumption |
| `POST /staff-meals` | `staff_meals.py` | inventory.* | Assessed business outcome |
| `POST /staff-meals/{meal_id}/reverse` | `staff_meals.py` | inventory.* | Assessed: authorized duplicate reversal, linked original and idempotent correction |
| `GET /stock/ledger` | `stock_ledger.py` | inventory.read | Supporting UI / record inspection |
| `GET /stock/documents/{document_id}` | `stock_ledger.py` | inventory.read | Supporting UI / record inspection |
| `GET /suppliers/{supplier_id}/detail` | `supplier_360.py` | suppliers.read | Supporting UI / record inspection |
| `PATCH /suppliers/{supplier_id}` | `supplier_360.py` | suppliers.* | Assessed real outcome; relevant lifecycle refusals also exercised |
