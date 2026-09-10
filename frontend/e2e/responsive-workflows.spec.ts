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
    const dimensions = await page.evaluate(() => {
      const clientWidth = document.documentElement.clientWidth;
      const offenders = Array.from(document.querySelectorAll<HTMLElement>("body *"))
        .map((element) => {
          const rect = element.getBoundingClientRect();
          return {
            tag: element.tagName.toLowerCase(),
            className: typeof element.className === "string" ? element.className : "",
            text: (element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 80),
            left: Math.round(rect.left),
            right: Math.round(rect.right),
            width: Math.round(rect.width),
            scrollWidth: element.scrollWidth,
            clientWidth: element.clientWidth,
          };
        })
        .filter((row) => row.right > clientWidth + 2 || row.left < -2 || row.scrollWidth > row.clientWidth + 2)
        .sort((a, b) => Math.max(b.right - clientWidth, b.scrollWidth - b.clientWidth) - Math.max(a.right - clientWidth, a.scrollWidth - a.clientWidth))
        .slice(0, 12);
      return { scrollWidth: document.documentElement.scrollWidth, clientWidth, offenders };
    });
    expect(dimensions.scrollWidth, `${route} should fit the mobile viewport. Offenders: ${JSON.stringify(dimensions.offenders)}`).toBeLessThanOrEqual(dimensions.clientWidth + 2);
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
