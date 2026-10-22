import { expect, test } from "@playwright/test";

const email = process.env.E2E_OWNER_EMAIL || "owner@example.com";
const password = process.env.E2E_OWNER_PASSWORD || "password123";

test("Accounting worklist does not format invalid source evidence as zero", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.route("**/api/v1/integrations/accounting/workspace*", route =>
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        summary: {
          pending: 2, completed: 0, failed: 0, dead_letter: 0,
          unmapped: 0, queued_value: "30", ready_for_review: 0,
          review_rejected: 0, unverified_delivery: 0,
          posted_journals_verified: 0, verification_unavailable: 0,
          financial_evidence_errors: 1, total_events: 3,
          displayed_events: 2, has_more: true, event_metrics_scope: "displayed_rows",
        },
        rules: [],
        events: [
          {
            id: "financial-invalid", event_type: "inventory.stock_document.posted",
            aggregate_type: "stock_document", aggregate_id: "invalid-1",
            idempotency_key: "financial-invalid", status: "pending",
            attempts: 0, max_attempts: 8, last_error: null,
            created_at: "2026-01-10T08:00:00Z", processed_at: null,
            amount: null, financial_evidence_error: "Financial quantity or amount is not numeric",
            financial_evidence_valid: false, debit_account: "Inventory Asset",
            credit_account: "Inventory Clearing", mapped: true,
            accounting_intake_status: "not_delivered", accounting_review_id: null,
            ledger_posting_confirmed: false, accounting_journal_entry_id: null,
            accounting_journal_status: null, accounting_verified_at: null,
            accounting_verification_error: null,
          },
          {
            id: "financial-good", event_type: "inventory.stock_document.posted",
            aggregate_type: "stock_document", aggregate_id: "valid-1",
            idempotency_key: "financial-good", status: "pending",
            attempts: 0, max_attempts: 8, last_error: null,
            created_at: "2026-01-10T08:01:00Z", processed_at: null,
            amount: "30", financial_evidence_error: null,
            financial_evidence_valid: true, debit_account: "Inventory Asset",
            credit_account: "Inventory Clearing", mapped: true,
            accounting_intake_status: "not_delivered", accounting_review_id: null,
            ledger_posting_confirmed: false, accounting_journal_entry_id: null,
            accounting_journal_status: null, accounting_verified_at: null,
            accounting_verification_error: null,
          },
        ],
      }),
    })
  );

  await page.goto("/integrations/accounting");
  await expect(page.getByRole("heading", { name: "Accounting Integration" })).toBeVisible();
  await expect(page.getByText("Unknown — needs evidence")).toBeVisible();
  await expect(page.getByText("Showing 2 of 3 Accounting events", { exact: false })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence issues (shown)" })).toBeVisible();
  const row = page.getByRole("row").filter({ hasText: "invalid-1" });
  await expect(row).toContainText("Financial quantity or amount is not numeric");
  await expect(row).not.toContainText("₱0.00");
  const good = page.getByRole("row").filter({ hasText: "valid-1" });
  await expect(good).toContainText("₱30.00");
  await test.info().attach("group-f-accounting-invalid-financial-evidence", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
});
