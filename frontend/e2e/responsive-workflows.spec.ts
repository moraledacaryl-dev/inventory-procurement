import { expect, test } from "@playwright/test";

const email = process.env.E2E_OWNER_EMAIL || "owner@example.com";
const password = process.env.E2E_OWNER_PASSWORD || "password123";

async function signIn(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("mobile workflow pages do not create page-level horizontal overflow", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.includes("mobile"), "Mobile-only responsive regression");
  await signIn(page);
  for (const route of ["/purchasing", "/inventory-operations"] as const) {
    await page.goto(route);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(400);
    const dimensions = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(dimensions.scrollWidth, `${route} should fit the mobile viewport`).toBeLessThanOrEqual(dimensions.clientWidth + 2);
  }
});

test("mobile data tables render labeled card rows", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.includes("mobile"), "Mobile-only responsive regression");
  await signIn(page);
  await page.goto("/inventory-operations");
  const firstDataCell = page.locator(".data-table-shell tbody td[data-label]").first();
  await expect(firstDataCell).toBeVisible();
  const display = await firstDataCell.evaluate(node => getComputedStyle(node).display);
  expect(display).toBe("grid");
});
