# Inventory → Accounting protected outbox evidence export

This tool supports Accounting [cross-app acceptance issue #334](https://github.com/moraledacaryl-dev/accounting-program-online/issues/334). It is an **offline, source-local, read-only** snapshot of Inventory's outbound Accounting event identities, destination and current status. The exporter scans ALL matching Inventory events, not merely the latest 500 shown in the Accounting Workspace.

```bash
cd /root/repos/inventory-procurement/backend
# With the normal protected Inventory PostgreSQL DATABASE_URL config:
python3 scripts/export_accounting_outbox_snapshot.py \
  --output /root/restricted-inventory-accounting-source.json
```

The exporter starts a PostgreSQL `SET TRANSACTION READ ONLY` transaction and queries only `IntegrationEvent.id`, `destination_system`, `status` for `direction=outbound` and `destination_system=accounting`. It neither reads nor exports purchase/supplier payloads, financial amounts, credentials, locations, stock quantities, or private error details. Invalid event IDs make the entire export fail closed.

It creates only a **new** `0600` local JSON file, rejects existing destinations/symlinks, does not alter source rows, does not queue/replay events, and does not contact Accounting. Keep the generated file off public PRs, issues, chat, CI logs, backups without access controls, and workflow artifacts. Only publish aggregated and reviewed status counts.

The exported JSON can be placed into `producers.inventory` for Accounting's `backend/scripts/audit_source_outbox_parity.py`. Each Inventory `IntegrationEvent.id` is exactly the receiver `source_event_id`, revision **1**, as implemented in `backend/app/services/integration_worker.py`.

The snapshot sets `complete_for_window=false` deliberately. A complete Inventory SQL scan is NOT a coordinated transaction with Accounting's independently exported database. Both sides must be compared using an agreed source window / cutoff and authorized complete exports before making missing-event or sender-orphan claims. Inventory `completed` means intake successfully received the envelope, **not** Accounting journal posting. A true zero row count must be investigated against real producer activity, not interpreted as healthy or broken automatically.

This does not reconcile bank/GCash, payable obligations, Inventory stock or cost-of-goods-sold, and cannot authorize new financial postings. Human acceptance and documentary source evidence remain mandatory.
