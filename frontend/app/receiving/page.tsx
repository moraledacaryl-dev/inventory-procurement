"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { DataTable } from "../../components/DataTable";
import { api } from "../../lib/api";

type POLine = {
  id: string;
  item_id: string;
  ordered_quantity: string;
  received_quantity: string;
  unit_price: string;
};

type PO = {
  id: string;
  purchase_order_number: string;
  status: string;
  lines: POLine[];
};

type GR = {
  id: string;
  goods_receipt_number: string;
  purchase_order_id: string;
  delivery_reference: string | null;
  received_at: string;
  lines: { accepted_quantity: string; rejected_quantity: string }[];
};

export default function Page() {
  const [pos, setPos] = useState<PO[]>([]);
  const [receipts, setReceipts] = useState<GR[]>([]);
  const [selectedPoId, setSelectedPoId] = useState("");
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const [purchaseOrders, goodsReceipts] = await Promise.all([
        api<PO[]>("/purchase-orders"),
        api<GR[]>("/goods-receipts"),
      ]);
      setPos(purchaseOrders);
      setReceipts(goodsReceipts);
    } catch (error) {
      setMsg((error as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function receive(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const po = pos.find((entry) => entry.id === values.get("po"));
    const line = po?.lines.find((entry) => entry.id === values.get("line"));
    if (!po || !line) return;

    const received = Number(values.get("received"));
    const rejected = Number(values.get("rejected") || 0);
    if (rejected > received) {
      setMsg("Rejected quantity cannot exceed received quantity.");
      return;
    }

    try {
      await api(`/purchase-orders/${po.id}/receipts`, {
        method: "POST",
        body: JSON.stringify({
          delivery_reference: values.get("reference") || null,
          lines: [
            {
              purchase_order_line_id: line.id,
              received_quantity: String(received),
              accepted_quantity: String(received - rejected),
              rejected_quantity: String(rejected),
            },
          ],
        }),
      });
      form.reset();
      setSelectedPoId("");
      setMsg("Goods receipt posted.");
      await load();
    } catch (error) {
      setMsg((error as Error).message);
    }
  }

  const selectedPo = pos.find((entry) => entry.id === selectedPoId);

  return (
    <AppShell title="Receiving">
      <section className="card">
        <h2>Receive purchase order</h2>
        <form className="inline-form" onSubmit={receive}>
          <select
            name="po"
            required
            value={selectedPoId}
            onChange={(event) => setSelectedPoId(event.target.value)}
          >
            <option value="">Approved/open PO</option>
            {pos
              .filter((entry) => ["approved", "partially_received"].includes(entry.status))
              .map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.purchase_order_number} — {entry.status}
                </option>
              ))}
          </select>
          <select name="line" required disabled={!selectedPo}>
            <option value="">PO line</option>
            {selectedPo?.lines.map((line) => (
              <option key={line.id} value={line.id}>
                {line.item_id} — outstanding {Number(line.ordered_quantity) - Number(line.received_quantity)}
              </option>
            ))}
          </select>
          <input name="received" type="number" step="0.0001" min="0.0001" placeholder="Received qty" required />
          <input name="rejected" type="number" step="0.0001" min="0" placeholder="Rejected qty" />
          <input name="reference" placeholder="Delivery reference" />
          <button className="primary compact">Post receipt</button>
        </form>
        {msg && <p className="status">{msg}</p>}
      </section>
      <section className="card section-gap">
        <h2>Goods receipts</h2>
        <DataTable
          columns={["GRN", "PO", "Delivery ref", "Accepted", "Rejected", "Received at"]}
          rows={receipts.map((receipt) => [
            receipt.goods_receipt_number,
            pos.find((po) => po.id === receipt.purchase_order_id)?.purchase_order_number || receipt.purchase_order_id,
            receipt.delivery_reference || "",
            receipt.lines.reduce((sum, line) => sum + Number(line.accepted_quantity), 0),
            receipt.lines.reduce((sum, line) => sum + Number(line.rejected_quantity), 0),
            new Date(receipt.received_at).toLocaleString(),
          ])}
        />
      </section>
    </AppShell>
  );
}
