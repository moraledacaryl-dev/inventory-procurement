"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DataTable } from "../../components/DataTable";
import { FeedbackBanner, FeedbackTone } from "../../components/FeedbackBanner";
import { FormField, FormSection } from "../../components/FormField";
import { StatusBadge } from "../../components/StatusBadge";
import { useFormDraft } from "../../hooks/useFormDraft";
import { useUnsavedChanges } from "../../hooks/useUnsavedChanges";
import { api } from "../../lib/api";
import { formatQuantity } from "../../lib/formatters";

type Supplier = {
  id: string;
  code: string;
  name: string;
  contact_name: string | null;
  phone: string | null;
  payment_terms_days: number;
  is_active: boolean;
};

type SupplierDraft = {
  code: string;
  name: string;
  contact: string;
  phone: string;
  terms: string;
};

type Feedback = { tone: FeedbackTone; title: string; message?: string } | null;
type FieldErrors = Partial<Record<keyof SupplierDraft, string>>;

const EMPTY_DRAFT: SupplierDraft = { code: "", name: "", contact: "", phone: "", terms: "0" };

export default function Page() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const { draft, setDraft, clearDraft, restored } = useFormDraft<SupplierDraft>("inventory:supplier-draft", EMPTY_DRAFT);

  const isDirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(EMPTY_DRAFT), [draft]);
  useUnsavedChanges(isDirty && !saving);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      setSuppliers(await api<Supplier[]>("/suppliers"));
    } catch (error) {
      setLoadError((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function update<K extends keyof SupplierDraft>(key: K, value: SupplierDraft[K]) {
    setDraft(current => ({ ...current, [key]: value }));
    setFieldErrors(current => ({ ...current, [key]: undefined }));
    setFeedback(null);
  }

  function validate(): FieldErrors {
    const errors: FieldErrors = {};
    if (!draft.code.trim()) errors.code = "Enter a supplier code.";
    else if (!/^[A-Za-z0-9._-]+$/.test(draft.code.trim())) errors.code = "Use letters, numbers, periods, underscores, or hyphens only.";
    if (!draft.name.trim()) errors.name = "Enter the supplier name.";
    const terms = Number(draft.terms || 0);
    if (!Number.isInteger(terms) || terms < 0 || terms > 3650) errors.terms = "Enter payment terms from 0 to 3650 days.";
    if (draft.phone.trim() && draft.phone.trim().length < 7) errors.phone = "Enter a complete phone number or leave this blank.";
    return errors;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors = validate();
    if (Object.keys(errors).length) {
      setFieldErrors(errors);
      setFeedback({ tone: "error", title: "Check the highlighted fields", message: "The supplier was not saved because some information is missing or invalid." });
      return;
    }

    setSaving(true);
    setFeedback(null);
    try {
      await api("/suppliers", {
        method: "POST",
        body: JSON.stringify({
          code: draft.code.trim(),
          name: draft.name.trim(),
          contact_name: draft.contact.trim() || null,
          phone: draft.phone.trim() || null,
          payment_terms_days: Number(draft.terms || 0),
        }),
      });
      clearDraft();
      setFieldErrors({});
      setFeedback({ tone: "success", title: "Supplier added", message: `${draft.name.trim()} is now available for purchasing records.` });
      await load();
    } catch (error) {
      setFeedback({ tone: "error", title: "Supplier could not be saved", message: (error as Error).message });
    } finally {
      setSaving(false);
    }
  }

  function discardDraft() {
    clearDraft();
    setFieldErrors({});
    setFeedback({ tone: "info", title: "Draft cleared", message: "The unsaved supplier details were removed." });
    setConfirmDiscard(false);
  }

  return (
    <AppShell title="Suppliers" description="Maintain supplier contacts and purchasing terms.">
      <section className="card">
        <div className="topline">
          <div>
            <h2>Add supplier</h2>
            <p>Required fields remain visible, and unfinished details are preserved in this browser.</p>
          </div>
          {restored && isDirty ? <span className="badge warning">Draft saved</span> : null}
        </div>

        <form onSubmit={submit} noValidate>
          <FormSection title="Supplier details" description="Create the master record used by purchase requisitions, orders, receiving, and returns.">
            <FormField label="Supplier code" name="supplier-code" required hint="Use a short, unique code such as ABC-FOODS." error={fieldErrors.code}>
              <input value={draft.code} onChange={event => update("code", event.target.value)} autoComplete="off" />
            </FormField>
            <FormField label="Supplier name" name="supplier-name" required error={fieldErrors.name}>
              <input value={draft.name} onChange={event => update("name", event.target.value)} autoComplete="organization" />
            </FormField>
            <FormField label="Primary contact" name="supplier-contact" optional>
              <input value={draft.contact} onChange={event => update("contact", event.target.value)} autoComplete="name" />
            </FormField>
            <FormField label="Phone number" name="supplier-phone" optional error={fieldErrors.phone}>
              <input value={draft.phone} onChange={event => update("phone", event.target.value)} inputMode="tel" autoComplete="tel" />
            </FormField>
            <FormField label="Payment terms" name="supplier-terms" required hint="Number of days after invoicing. Enter 0 for due on receipt." error={fieldErrors.terms}>
              <input value={draft.terms} onChange={event => update("terms", event.target.value)} type="number" min="0" max="3650" step="1" inputMode="numeric" />
            </FormField>
          </FormSection>

          <div className="form-actions">
            <button type="button" className="secondary" disabled={!isDirty || saving} onClick={() => setConfirmDiscard(true)}>Clear draft</button>
            <button className="primary" disabled={saving}>{saving ? "Saving supplier…" : "Add supplier"}</button>
          </div>
        </form>

        {feedback ? <FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message} /> : null}
      </section>

      <section className="card section-gap">
        <h2>Supplier directory</h2>
        <DataTable
          columns={["Code", "Name", "Contact", "Phone", "Terms", "Status"]}
          rows={suppliers.map(supplier => [
            supplier.code,
            supplier.name,
            supplier.contact_name || "—",
            supplier.phone || "—",
            `${formatQuantity(supplier.payment_terms_days, 0)} days`,
            <StatusBadge key={`${supplier.id}-status`} status={supplier.is_active ? "active" : "inactive"} />,
          ])}
          rowIds={suppliers.map(supplier => supplier.id)}
          loading={loading}
          error={loadError}
          onRetry={() => void load()}
          searchPlaceholder="Search suppliers, contacts, phone numbers, or terms"
          exportFileName="hidden-oasis-suppliers"
          caption="Hidden Oasis supplier directory"
          emptyTitle="No suppliers yet"
          emptyMessage="Add the first supplier to begin creating purchase orders."
        />
      </section>

      <ConfirmDialog
        open={confirmDiscard}
        title="Clear this supplier draft?"
        description="All unsaved supplier information in this form will be removed from this browser."
        confirmLabel="Clear draft"
        tone="danger"
        onConfirm={discardDraft}
        onCancel={() => setConfirmDiscard(false)}
      />
    </AppShell>
  );
}
