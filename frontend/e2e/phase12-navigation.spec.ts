import { expect, test } from "@playwright/test";

const email = process.env.E2E_OWNER_EMAIL || "owner@example.com";
const password = process.env.E2E_OWNER_PASSWORD || "password123";

test("dashboard links open real inventory workspaces rather than ignored filters", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  const pendingPO = page.locator(".metric-card-link").filter({ hasText: "Pending POs" });
  await expect(pendingPO).toHaveAttribute("href", "/purchasing?view=source");
  await pendingPO.click();
  await expect(page).toHaveURL(/\/purchasing\?view=source$/);
  await expect(page.getByRole("heading", { name: "Quotation comparison" })).toBeVisible();

  await page.goto("/purchasing?view=plan");
  await expect(page.getByRole("heading", { name: "Reorder planning" })).toBeVisible();
});
