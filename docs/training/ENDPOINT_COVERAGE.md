# Endpoint coverage inventory

Extracted from the current source, not README claims. Supporting reads do not imply complete workflow mastery. The 26-module planning matrix is in COVERAGE.md. Unimplemented changes remain required work; they are not certified or silently excluded. Service delivery is disabled intentionally for isolation.

| Endpoint | Source | Permission | Current coverage |
|---|---|---|---|
| `GET /integrations/accounting/workspace` | `accounting_integration.py` | integrations.read | Supporting UI / record inspection |
| `POST /integrations/accounting/receipts` | `accounting_integration.py` | Service/session boundary | Disabled in training; sandbox adapter or separate onboarding applies |
| `POST /integrations/accounting/events/{event_id}/requeue` | `accounting_integration.py` | integrations.* | Disabled in training; sandbox adapter or separate onboarding applies |
| `GET /assets` | `assets.py` | inventory.read | Supporting UI / record inspection |
| `POST /assets` | `assets.py` | inventory.* | Further practical lesson required |
| `POST /assets/{asset_id}/events` | `assets.py` | inventory.* | Further practical lesson required |
| `GET /depreciation-runs` | `assets.py` | reports.read | Supporting UI / record inspection |
| `POST /depreciation-runs` | `assets.py` | inventory.* | Further practical lesson required |
| `POST /depreciation-runs/{run_id}/post` | `assets.py` | inventory.* | Further practical lesson required |
| `POST /auth/login` | `auth.py` | Service/session boundary | Disabled in training; sandbox adapter or separate onboarding applies |
| `POST /auth/logout` | `auth.py` | Service/session boundary | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /auth/me` | `auth.py` | Service/session boundary | Supporting UI / record inspection |
| `GET /items/{item_id}/configuration` | `catalogue_configuration.py` | items.read | Supporting UI / record inspection |
| `PATCH /supplier-items/{link_id}` | `catalogue_configuration.py` | suppliers.* | Further practical lesson required |
| `DELETE /supplier-items/{link_id}` | `catalogue_configuration.py` | suppliers.* | Further practical lesson required |
| `PATCH /items/{item_id}/barcodes/{barcode_id}` | `catalogue_configuration.py` | items.* | Further practical lesson required |
| `DELETE /items/{item_id}/barcodes/{barcode_id}` | `catalogue_configuration.py` | items.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `PATCH /items/{item_id}/conversions/{conversion_id}` | `catalogue_configuration.py` | items.* | Further practical lesson required |
| `PATCH /item-location-settings/{setting_id}` | `catalogue_configuration.py` | inventory.* | Further practical lesson required |
| `GET /classification/dimensions` | `classification.py` | items.read | Supporting UI / record inspection |
| `GET /classification/bootstrap` | `classification.py` | items.read | Supporting UI / record inspection |
| `POST /classification/dimensions` | `classification.py` | items.* | Further practical lesson required |
| `PATCH /classification/dimensions/{dimension_id}` | `classification.py` | items.* | Further practical lesson required |
| `GET /classification/items` | `classification.py` | items.read | Supporting UI / record inspection |
| `PATCH /classification/items/{item_id}` | `classification.py` | items.* | Further practical lesson required |
| `POST /classification/items/bulk-assign` | `classification.py` | items.* | Further practical lesson required |
| `GET /inventory-controls/adjustments` | `controlled_inventory.py` | inventory.read | Supporting UI / record inspection |
| `POST /inventory-controls/adjustments` | `controlled_inventory.py` | inventory.* | Further practical lesson required |
| `GET /inventory-controls/waste` | `controlled_inventory.py` | inventory.read | Supporting UI / record inspection |
| `POST /inventory-controls/waste` | `controlled_inventory.py` | inventory.* | Assessed business outcome |
| `GET /transfer-orders/workspace` | `controlled_inventory.py` | inventory.read | Supporting UI / record inspection |
| `GET /transfer-orders/{transfer_id}/detail` | `controlled_inventory.py` | inventory.read | Supporting UI / record inspection |
| `POST /transfer-orders/{transfer_id}/dispatch` | `controlled_inventory.py` | inventory.* | Further practical lesson required |
| `POST /transfer-orders/{transfer_id}/receive` | `controlled_inventory.py` | inventory.* | Further practical lesson required |
| `POST /transfer-orders/{transfer_id}/cancel` | `controlled_inventory.py` | inventory.* | Further practical lesson required |
| `POST /transfer-orders/{transfer_id}/receive` | `controlled_inventory_compat.py` | inventory.* | Further practical lesson required |
| `GET /dashboard/summary` | `dashboard.py` | inventory.read | Supporting UI / record inspection |
| `GET /dashboard/valuation-history` | `dashboard.py` | inventory.read | Supporting UI / record inspection |
| `GET /dashboard/exceptions` | `dashboard_exceptions.py` | inventory.read | Supporting UI / record inspection |
| `GET /reports/final-assurance` | `final_assurance.py` | reports.read | Supporting UI / record inspection |
| `POST /reports/final-assurance/record` | `final_assurance.py` | reports.read | Further practical lesson required |
| `GET /reports/final-assurance.csv` | `final_assurance.py` | reports.read | Supporting UI / record inspection |
| `GET /counts/workspace` | `guided_counts.py` | counts.read | Supporting UI / record inspection |
| `GET /counts/locations` | `guided_counts.py` | counts.read | Supporting UI / record inspection |
| `GET /counts/{count_id}/detail` | `guided_counts.py` | counts.read | Supporting UI / record inspection |
| `PUT /counts/{count_id}/entries` | `guided_counts.py` | counts.create | Assessed business outcome |
| `POST /counts/{count_id}/submit` | `guided_counts.py` | counts.submit | Assessed business outcome |
| `POST /counts/{count_id}/recount` | `guided_counts.py` | counts.approve | Further practical lesson required |
| `POST /counts/{count_id}/approve-guided` | `guided_counts.py` | counts.approve | Assessed business outcome |
| `POST /counts/{count_id}/cancel-guided` | `guided_counts.py` | counts.approve | Further practical lesson required |
| `GET /health` | `health.py` | Service/session boundary | Supporting UI / record inspection |
| `GET /ready` | `health.py` | Service/session boundary | Supporting UI / record inspection |
| `GET /categories` | `inventory.py` | items.read | Supporting UI / record inspection |
| `POST /categories` | `inventory.py` | items.* | Further practical lesson required |
| `GET /units` | `inventory.py` | items.read | Supporting UI / record inspection |
| `POST /units` | `inventory.py` | items.* | Further practical lesson required |
| `GET /locations` | `inventory.py` | locations.read | Supporting UI / record inspection |
| `POST /locations` | `inventory.py` | locations.* | Further practical lesson required |
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
| `POST /stock/adjustments` | `inventory.py` | inventory.* | Further practical lesson required |
| `POST /counts` | `inventory.py` | counts.create | Further practical lesson required |
| `GET /counts` | `inventory.py` | counts.read | Supporting UI / record inspection |
| `GET /counts/{count_id}/worksheet` | `inventory.py` | counts.read | Supporting UI / record inspection |
| `POST /counts/{count_id}/post` | `inventory.py` | counts.submit | Further practical lesson required |
| `POST /counts/{count_id}/approve` | `inventory.py` | counts.approve | Further practical lesson required |
| `GET /items/barcode/{barcode}` | `inventory_operations.py` | items.read | Supporting UI / record inspection |
| `GET /items/{item_id}/barcodes` | `inventory_operations.py` | items.read | Supporting UI / record inspection |
| `POST /items/{item_id}/barcodes` | `inventory_operations.py` | items.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /items/{item_id}/conversions` | `inventory_operations.py` | items.read | Supporting UI / record inspection |
| `POST /items/{item_id}/conversions` | `inventory_operations.py` | items.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /items/{item_id}/convert` | `inventory_operations.py` | items.read | Supporting UI / record inspection |
| `GET /item-location-settings` | `inventory_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /item-location-settings` | `inventory_operations.py` | inventory.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /lots` | `inventory_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /lots` | `inventory_operations.py` | inventory.* | Further practical lesson required |
| `GET /lot-balances` | `inventory_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /lot-transactions` | `inventory_operations.py` | inventory.* | Further practical lesson required |
| `GET /availability` | `inventory_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /reservations` | `inventory_operations.py` | inventory.* | Further practical lesson required |
| `POST /reservations/{reservation_id}/release` | `inventory_operations.py` | inventory.* | Further practical lesson required |
| `GET /transfer-orders` | `inventory_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /transfer-orders` | `inventory_operations.py` | inventory.* | Further practical lesson required |
| `POST /transfer-orders/{transfer_id}/dispatch` | `inventory_operations.py` | inventory.* | Further practical lesson required |
| `POST /transfer-orders/{transfer_id}/receive` | `inventory_operations.py` | inventory.* | Further practical lesson required |
| `GET /cycle-count-schedules` | `inventory_operations.py` | counts.create | Supporting UI / record inspection |
| `POST /cycle-count-schedules` | `inventory_operations.py` | counts.create | Further practical lesson required |
| `GET /reports/valuation` | `inventory_operations.py` | reports.read | Supporting UI / record inspection |
| `GET /reports/aging` | `inventory_operations.py` | reports.read | Supporting UI / record inspection |
| `GET /reports/expiry` | `inventory_operations.py` | reports.read | Supporting UI / record inspection |
| `GET /reports/waste` | `inventory_operations.py` | reports.read | Supporting UI / record inspection |
| `GET /locations/{location_id}` | `location_controls.py` | locations.read | Supporting UI / record inspection |
| `PATCH /locations/{location_id}` | `location_controls.py` | locations.* | Further practical lesson required |
| `GET /fnb/menu` | `menu.py` | items.read | Supporting UI / record inspection |
| `POST /fnb/menu` | `menu.py` | items.* | Further practical lesson required |
| `PUT /fnb/menu/{item_id}` | `menu.py` | items.* | Further practical lesson required |
| `POST /integrations/operations/requests` | `operational_integrations.py` | Service/session boundary | Disabled in training; sandbox adapter or separate onboarding applies |
| `GET /integrations/operations/workspace` | `operational_integrations.py` | integrations.read | Supporting UI / record inspection |
| `POST /integrations/operations/requests/{event_id}/decision` | `operational_integrations.py` | integrations.* | Disabled in training; sandbox adapter or separate onboarding applies |
| `GET /audit-logs` | `operations.py` | reports.read | Supporting UI / record inspection |
| `GET /notifications` | `operations.py` | reports.read | Supporting UI / record inspection |
| `POST /notifications/{notification_id}/read` | `operations.py` | reports.read | Further practical lesson required |
| `GET /integration-events` | `operations.py` | reports.read | Supporting UI / record inspection |
| `POST /integration-events` | `operations.py` | procurement.* | Further practical lesson required |
| `POST /integration-events/{event_id}/retry` | `operations.py` | procurement.* | Further practical lesson required |
| `POST /integration-events/process` | `operations.py` | procurement.* | Disabled in training; sandbox adapter or separate onboarding applies |
| `GET /exports/items.csv` | `operations.py` | reports.read | Supporting UI / record inspection |
| `GET /exports/balances.csv` | `operations.py` | reports.read | Supporting UI / record inspection |
| `POST /imports/items.csv` | `operations.py` | items.* | Further practical lesson required |
| `GET /backups` | `operations.py` | reports.read | Supporting UI / record inspection |
| `GET /maintenance/plans` | `pass5_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /maintenance/plans` | `pass5_operations.py` | inventory.* | Further practical lesson required |
| `GET /maintenance/work-orders` | `pass5_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /maintenance/work-orders` | `pass5_operations.py` | inventory.* | Further practical lesson required |
| `POST /maintenance/work-orders/{work_order_id}/start` | `pass5_operations.py` | inventory.* | Further practical lesson required |
| `POST /maintenance/work-orders/{work_order_id}/complete` | `pass5_operations.py` | inventory.* | Further practical lesson required |
| `GET /purchase-line-treatments` | `pass5_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /purchase-line-treatments` | `pass5_operations.py` | inventory.* | Further practical lesson required |
| `GET /accounting-mappings` | `pass5_operations.py` | reports.read | Supporting UI / record inspection |
| `POST /accounting-mappings` | `pass5_operations.py` | inventory.* | Further practical lesson required |
| `GET /access-scope-users` | `pass6_controls.py` | users.* | Supporting UI / record inspection |
| `GET /access-scopes` | `pass6_controls.py` | users.* | Supporting UI / record inspection |
| `POST /access-scopes` | `pass6_controls.py` | users.* | Further practical lesson required |
| `GET /saved-views` | `pass6_controls.py` | inventory.read | Supporting UI / record inspection |
| `POST /saved-views` | `pass6_controls.py` | inventory.read | Further practical lesson required |
| `GET /reports/operating-summary` | `pass6_controls.py` | reports.read | Supporting UI / record inspection |
| `GET /classification/migration-review` | `pass6_controls.py` | inventory.read | Supporting UI / record inspection |
| `GET /fnb/pos-rules` | `pos_rules.py` | items.read | Supporting UI / record inspection |
| `POST /fnb/pos-rules/pricing` | `pos_rules.py` | items.* | Further practical lesson required |
| `PUT /fnb/pos-rules/pricing/{rule_id}` | `pos_rules.py` | items.* | Further practical lesson required |
| `POST /fnb/pos-rules/modifiers` | `pos_rules.py` | items.* | Further practical lesson required |
| `PUT /fnb/pos-rules/modifiers/{template_id}` | `pos_rules.py` | items.* | Further practical lesson required |
| `GET /integrations/pos/catalog` | `pos_sync.py` | Service/session boundary | Supporting UI / record inspection |
| `GET /integrations/pos/workspace` | `pos_sync.py` | integrations.read | Supporting UI / record inspection |
| `POST /pos-mappings/{mapping_id}/activate` | `pos_sync.py` | integrations.* | Further practical lesson required |
| `POST /pos-mappings/{mapping_id}/deactivate` | `pos_sync.py` | integrations.* | Further practical lesson required |
| `GET /suppliers` | `procurement.py` | suppliers.read | Supporting UI / record inspection |
| `POST /suppliers` | `procurement.py` | suppliers.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /suppliers/{supplier_id}/items` | `procurement.py` | suppliers.read | Supporting UI / record inspection |
| `POST /suppliers/{supplier_id}/items` | `procurement.py` | suppliers.* | Assessed real outcome; relevant lifecycle refusals also exercised |
| `GET /supplier-performance` | `procurement.py` | reports.read | Supporting UI / record inspection |
| `GET /reorder-suggestions` | `procurement.py` | procurement.read | Supporting UI / record inspection |
| `POST /reorder-suggestions/requisition` | `procurement.py` | procurement.* | Further practical lesson required |
| `GET /requisitions` | `procurement.py` | procurement.read | Supporting UI / record inspection |
| `POST /requisitions` | `procurement.py` | procurement.* | Further practical lesson required |
| `POST /requisitions/{requisition_id}/approve` | `procurement.py` | procurement.* | Further practical lesson required |
| `POST /requisitions/{requisition_id}/reject` | `procurement.py` | procurement.* | Further practical lesson required |
| `GET /quotations` | `procurement.py` | procurement.read | Supporting UI / record inspection |
| `POST /quotations` | `procurement.py` | procurement.* | Further practical lesson required |
| `GET /requisitions/{requisition_id}/quotation-comparison` | `procurement.py` | procurement.read | Supporting UI / record inspection |
| `GET /purchase-orders` | `procurement.py` | procurement.read | Supporting UI / record inspection |
| `POST /purchase-orders` | `procurement.py` | procurement.* | Assessed business outcome |
| `POST /purchase-orders/{po_id}/approve` | `procurement.py` | procurement.* | Assessed business outcome |
| `POST /purchase-orders/{po_id}/receipts` | `procurement.py` | receiving.* | Further practical lesson required |
| `GET /goods-receipts` | `procurement.py` | receiving.read | Supporting UI / record inspection |
| `POST /purchase-orders/{po_id}/returns` | `procurement.py` | receiving.* | Further practical lesson required |
| `GET /procurement/planning` | `procurement_planning.py` | procurement.read | Supporting UI / record inspection |
| `POST /procurement/planning/requisitions` | `procurement_planning.py` | procurement.* | Assessed business outcome |
| `GET /procurement/requisitions/workspace` | `procurement_planning.py` | procurement.read | Supporting UI / record inspection |
| `GET /recipes/item-options` | `production.py` | inventory.read | Supporting UI / record inspection |
| `GET /recipes` | `production.py` | inventory.read | Supporting UI / record inspection |
| `POST /recipes` | `production.py` | inventory.* | Further practical lesson required |
| `POST /recipes/{recipe_id}/approve` | `production.py` | inventory.* | Further practical lesson required |
| `GET /recipes/{recipe_id}/cost` | `production.py` | reports.read | Supporting UI / record inspection |
| `GET /production-batches` | `production.py` | inventory.read | Supporting UI / record inspection |
| `POST /production-batches` | `production.py` | inventory.* | Further practical lesson required |
| `POST /production-batches/{batch_id}/complete` | `production.py` | inventory.* | Further practical lesson required |
| `GET /pos-mappings` | `production.py` | integrations.read | Supporting UI / record inspection |
| `POST /pos-mappings` | `production.py` | integrations.* | Further practical lesson required |
| `POST /integrations/pos/events` | `production.py` | Service/session boundary | Disabled in training; sandbox adapter or separate onboarding applies |
| `GET /integrations/reconciliation` | `production.py` | integrations.read | Supporting UI / record inspection |
| `GET /production-batches/{batch_id}/execution-detail` | `production_execution.py` | inventory.read | Supporting UI / record inspection |
| `POST /production-batches/{batch_id}/start` | `production_execution.py` | inventory.* | Assessed business outcome |
| `POST /production-batches/{batch_id}/execute` | `production_execution.py` | inventory.* | Assessed business outcome |
| `POST /production-batches/{batch_id}/cancel` | `production_execution.py` | inventory.* | Further practical lesson required |
| `GET /property/balances` | `property_operations.py` | inventory.read | Supporting UI / record inspection |
| `GET /property/movements` | `property_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /property/movements` | `property_operations.py` | inventory.* | Further practical lesson required |
| `GET /hotel/par-profiles` | `property_operations.py` | inventory.read | Supporting UI / record inspection |
| `POST /hotel/par-profiles` | `property_operations.py` | inventory.* | Further practical lesson required |
| `GET /procurement/quotation-workspace` | `quotation_po_workspace.py` | procurement.read | Supporting UI / record inspection |
| `POST /requisitions/{requisition_id}/award-quotation` | `quotation_po_workspace.py` | procurement.* | Further practical lesson required |
| `GET /purchase-orders/{po_id}/detail` | `quotation_po_workspace.py` | procurement.read | Supporting UI / record inspection |
| `PATCH /purchase-orders/{po_id}/amend` | `quotation_po_workspace.py` | procurement.* | Further practical lesson required |
| `POST /purchase-orders/{po_id}/cancel-workspace` | `quotation_po_workspace.py` | procurement.* | Further practical lesson required |
| `POST /migration/imports/{import_type}/validate` | `readiness.py` | inventory.* | Further practical lesson required |
| `GET /migration/imports` | `readiness.py` | reports.read | Supporting UI / record inspection |
| `POST /migration/imports/{job_id}/apply` | `readiness.py` | inventory.* | Further practical lesson required |
| `POST /requisitions/{document_id}/cancel` | `readiness.py` | procurement.* | Further practical lesson required |
| `POST /purchase-orders/{document_id}/cancel` | `readiness.py` | procurement.* | Further practical lesson required |
| `GET /print/purchase-orders/{document_id}` | `readiness.py` | procurement.read | Supporting UI / record inspection |
| `GET /print/goods-receipts/{document_id}` | `readiness.py` | receiving.read | Supporting UI / record inspection |
| `GET /deployment/status` | `readiness.py` | reports.read | Supporting UI / record inspection |
| `POST /acceptance-runs` | `readiness.py` | inventory.* | Further practical lesson required |
| `GET /acceptance-runs` | `readiness.py` | reports.read | Supporting UI / record inspection |
| `GET /receiving/workspace` | `receiving_workspace.py` | receiving.read | Supporting UI / record inspection |
| `POST /receiving/purchase-orders/{po_id}` | `receiving_workspace.py` | receiving.* | Assessed business outcome |
| `POST /receiving/purchase-orders/{po_id}/returns` | `receiving_workspace.py` | receiving.* | Assessed business outcome |
| `GET /recipes/costing/workspace` | `recipe_costing.py` | reports.read | Supporting UI / record inspection |
| `GET /recipes/{recipe_id}/costing-detail` | `recipe_costing.py` | reports.read | Supporting UI / record inspection |
| `POST /recipes/{recipe_id}/margin-scenario` | `recipe_costing.py` | reports.read | Further practical lesson required |
| `POST /recipes/{recipe_id}/revise` | `recipe_costing.py` | inventory.* | Further practical lesson required |
| `POST /recipes/{recipe_id}/retire` | `recipe_costing.py` | inventory.* | Further practical lesson required |
| `GET /shared-identities` | `shared_master_data.py` | users.read | Supporting UI / record inspection |
| `GET /shared-identities/{canonical_user_id}` | `shared_master_data.py` | users.read | Supporting UI / record inspection |
| `GET /shared-identities/resolve/by-email` | `shared_master_data.py` | users.read | Supporting UI / record inspection |
| `GET /master-data/workspace` | `shared_master_data.py` | integrations.read | Supporting UI / record inspection |
| `POST /master-data/publish` | `shared_master_data.py` | integrations.* | Disabled in training; sandbox adapter or separate onboarding applies |
| `POST /feedback` | `stabilization.py` | inventory.read | Further practical lesson required |
| `GET /feedback` | `stabilization.py` | reports.read | Supporting UI / record inspection |
| `PATCH /feedback/{feedback_id}` | `stabilization.py` | reports.read | Further practical lesson required |
| `POST /incidents` | `stabilization.py` | reports.read | Further practical lesson required |
| `GET /incidents` | `stabilization.py` | reports.read | Supporting UI / record inspection |
| `PATCH /incidents/{incident_id}` | `stabilization.py` | reports.read | Further practical lesson required |
| `GET /rollout/summary` | `stabilization.py` | reports.read | Supporting UI / record inspection |
| `POST /rollout/smoke-test` | `stabilization.py` | reports.read | Further practical lesson required |
| `POST /integrations/staff/employees` | `staff_identity_integration.py` | Service/session boundary | Disabled in training; sandbox adapter or separate onboarding applies |
| `GET /staff-meals` | `staff_meals.py` | inventory.read | Supporting UI / record inspection |
| `GET /staff-meals/{meal_id}` | `staff_meals.py` | inventory.read | Supporting UI / record inspection |
| `POST /staff-meals/preview` | `staff_meals.py` | inventory.read | Further practical lesson required |
| `POST /staff-meals` | `staff_meals.py` | inventory.* | Assessed business outcome |
| `POST /staff-meals/{meal_id}/reverse` | `staff_meals.py` | inventory.* | Further practical lesson required |
| `GET /stock/ledger` | `stock_ledger.py` | inventory.read | Supporting UI / record inspection |
| `GET /stock/documents/{document_id}` | `stock_ledger.py` | inventory.read | Supporting UI / record inspection |
| `GET /suppliers/{supplier_id}/detail` | `supplier_360.py` | suppliers.read | Supporting UI / record inspection |
| `PATCH /suppliers/{supplier_id}` | `supplier_360.py` | suppliers.* | Assessed real outcome; relevant lifecycle refusals also exercised |
