import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { stableDraftIdempotency } from "../lib/draftIdempotency";

const email = process.env.E2E_OWNER_EMAIL || "owner@example.com";
const password = process.env.E2E_OWNER_PASSWORD || "password123";

async function signIn(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

test("staff meal draft idempotency survives identical retries and rotates after edits", () => {
  const keys = ["retry-key", "edited-key"];
  const makeKey = () => keys.shift()!;
  const firstDraft = { meal_name: "Adobo", servings: 4, location_id: "kitchen", lines: [{ item_id: "chicken", quantity: "1" }] };
  const first = stableDraftIdempotency(firstDraft, null, makeKey);
  const retry = stableDraftIdempotency(firstDraft, first, makeKey);
  expect(retry.key).toBe(first.key);
  expect(retry.key).toBe("retry-key");

  const edited = stableDraftIdempotency({ ...firstDraft, servings: 5 }, retry, makeKey);
  expect(edited.key).toBe("edited-key");
  expect(edited.key).not.toBe(first.key);
});

test("login and core operational pages are reachable", async ({ page }) => {
  await signIn(page);
  for (const [path, heading] of [
    ["/items", "Inventory"],
    ["/suppliers", "Suppliers"],
    ["/purchasing", "Purchasing"],
    ["/receiving", "Receiving"],
    ["/counts", "Counts"],
    ["/production", "Recipes & Production"],
    ["/fnb/staff-meals", "Staff Meals"],
    ["/assets", "Assets & Property"],
  ] as const) {
    await page.goto(path);
    await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }
});

test("staff meals is available from the F&B sidebar and uses the compact operational workspace", async ({ page, isMobile }) => {
  await signIn(page);
  if (isMobile) {
    await page.getByRole("button", { name: "Open navigation" }).click();
  }
  await page.locator(".nav-section > summary").filter({ hasText: /^F&B$/ }).click();
  const link = page.getByRole("link", { name: "Staff Meals", exact: true });
  await expect(link).toBeVisible();
  await link.click();
  await expect(page).toHaveURL(/\/fnb\/staff-meals$/);
  await expect(page.getByRole("heading", { name: "Record staff meal" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Staff meal ingredients" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Preview cost" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Post staff meal" })).toBeVisible();
});

test("sidebar state remains visually stable during client navigation", async ({ page, isMobile }) => {
  test.skip(isMobile, "desktop shell stability is covered separately from the mobile drawer");
  await signIn(page);
  const sidebar = page.locator("aside.sidebar");
  const header = page.locator("header.app-header");
  await expect(sidebar).toBeVisible();
  const beforeSidebar = await sidebar.boundingBox();
  const beforeHeader = await header.boundingBox();
  await page.getByRole("link", { name: "Inventory", exact: true }).click();
  await expect(page).toHaveURL(/\/items$/);
  const afterSidebar = await sidebar.boundingBox();
  const afterHeader = await header.boundingBox();
  expect(afterSidebar?.width).toBe(beforeSidebar?.width);
  expect(afterHeader?.x).toBe(beforeHeader?.x);
  await expect(page.getByRole("link", { name: "Operational Access", exact: true })).toHaveCount(0);
});

test("sidebar scroll position survives route changes", async ({ page, isMobile }) => {
  test.skip(isMobile, "desktop sidebar owns the persistent scroll container");
  await signIn(page);
  const sidebar = page.locator("aside.sidebar");
  await page.locator(".nav-section > summary").filter({ hasText: /^Admin$/ }).click();
  await sidebar.evaluate(element => { element.scrollTop = element.scrollHeight; });
  const before = await sidebar.evaluate(element => element.scrollTop);
  expect(before).toBeGreaterThan(0);
  await page.getByRole("link", { name: "System health", exact: true }).click();
  await expect(page).toHaveURL(/\/readiness$/);
  const after = await sidebar.evaluate(element => element.scrollTop);
  expect(after).toBeGreaterThanOrEqual(before - 4);
});

test("slow refresh fallback never paints a green sidebar", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/v1/**", async route => {
    await new Promise(resolve => setTimeout(resolve, 500));
    await route.continue();
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  const loadingSidebar = page.locator(".loading-sidebar, .loading-shell-sidebar").first();
  if (await loadingSidebar.count()) {
    const background = await loadingSidebar.evaluate(element => getComputedStyle(element).backgroundColor);
    expect(background).not.toMatch(/rgb\((?:0|[1-4]?\d),\s*(?:6\d|7\d|8\d|9\d|1[01]\d),/);
  }
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
});

test("mobile navigation opens, routes, and closes", async ({ page, isMobile }) => {
  test.skip(!isMobile, "mobile-only navigation behavior");
  await signIn(page);
  const menu = page.getByRole("button", { name: "Open navigation" });
  await menu.click();
  await expect(page.locator("aside.sidebar")).toHaveClass(/is-open/);
  await page.getByRole("link", { name: "Inventory", exact: true }).click();
  await expect(page).toHaveURL(/\/items$/);
  await expect(page.locator("aside.sidebar")).not.toHaveClass(/is-open/);
});


test("shell popovers and dialogs fit the viewport", async ({ page, isMobile }) => {
  await signIn(page);
  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();

  const notifications = page.getByRole("button", { name: /Notifications/ });
  if (await notifications.count()) {
    await notifications.click();
    const popover = page.getByRole("dialog", { name: "Notifications" });
    await expect(popover).toBeVisible();
    const box = await popover.boundingBox();
    expect(box?.x ?? -1).toBeGreaterThanOrEqual(0);
    expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(viewport!.width + 1);
    expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual(viewport!.height + 1);
    await page.keyboard.press("Escape");
  }

  if (!isMobile) {
    const help = page.getByRole("button", { name: "Help" });
    await help.click();
    const helpDialog = page.getByRole("dialog", { name: /help/i });
    await expect(helpDialog).toBeVisible();
    const box = await helpDialog.boundingBox();
    expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(viewport!.width + 1);
    expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual(viewport!.height + 1);
  }
});

test("critical pages have no serious Axe violations", async ({ page }) => {
  await signIn(page);
  for (const path of ["/dashboard", "/items", "/purchasing", "/receiving", "/counts", "/fnb/staff-meals", "/assets"]) {
    await page.goto(path);
    await expect(page.locator("main#main-content")).toBeVisible();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const serious = results.violations.filter(v => v.impact === "critical" || v.impact === "serious");
    expect(serious, `${path}: ${serious.map(v => `${v.id} (${v.nodes.length})`).join(", ")}`).toEqual([]);
  }
});


test("inventory operations remains usable when supplementary suppliers request fails", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/v1/suppliers", route => route.fulfill({
    status: 500, contentType: "application/json",
    body: JSON.stringify({ detail: "Temporary supplier lookup failure" }),
  }));
  await page.goto("/inventory-operations");
  await expect(page.getByRole("heading", { name: "Inventory Operations", exact: true })).toBeVisible();
  await expect(page.getByText("Available stock", { exact: true })).toBeVisible();
  await expect(page.getByText("Supplementary information unavailable")).toBeVisible();
  await expect(page.getByText("Inventory operations unavailable")).toHaveCount(0);
});

test("counter inventory operations avoids forbidden supplier and reports endpoints", async ({ page }) => {
  test.skip(process.env.VISUAL_CAPTURE !== "1", "Counter user exists in exhaustive visual seed");
  await page.goto("/login");
  await page.getByLabel("Email address").fill("visual-counter@example.com");
  await page.locator('input[name="password"]').fill(process.env.E2E_VISUAL_PASSWORD || "visual-acceptance-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  const restrictedCalls: string[] = [];
  page.on("request", request => {
    const url = request.url();
    if (/\/api\/v1\/(suppliers|reports\/expiry|reports\/valuation)(?:\?|$)/.test(url)) restrictedCalls.push(url);
  });
  await page.goto("/inventory-operations");
  await expect(page.getByText("Available stock", { exact: true })).toBeVisible();
  await expect(page.getByText("Inventory operations unavailable")).toHaveCount(0);
  expect(restrictedCalls).toEqual([]);
});


test("stock ledger clearly labels truncated totals and validates filter dates", async ({ page }) => {
  await signIn(page);
  let ledgerRequests = 0;
  await page.route("**/api/v1/stock/ledger?*", route => {
    ledgerRequests += 1;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        filters: { limit: 500 },
        summary: {
          movement_count: 500, document_count: 500,
          net_quantity: "500", net_value: "5000",
          has_more: true, totals_scope: "displayed_rows",
        },
        rows: Array.from({ length: 500 }, (_, index) => ({
          id: `m-${index}`, document_id: `doc-${index}`,
          document_number: `DOC-${index}`, document_type: "receipt",
          document_status: "posted", reference: null,
          item_id: "item-1", sku: "TEST-ITEM", item_name: "Synthetic item",
          location_id: "loc-1", location_code: "MAIN", location_name: "Main",
          quantity: "1", unit_cost: "10", line_value: "10",
          running_quantity: String(index + 1), reason: null,
          created_at: "2026-01-01T08:00:00Z", posted_at: "2026-01-01T08:00:00Z",
        })),
      }),
    });
  });
  await page.goto("/stock");
  await expect(page.getByText("Partial ledger results:")).toBeVisible();
  await expect(page.getByText(/only the first 500 matching movements are shown/i)).toBeVisible();
  await expect(page.getByText(/Page 1 of 50/)).toBeVisible();

  const dates = page.locator(".ledger-filters input[type=date]");
  await dates.nth(0).fill("2026-02-15");
  await dates.nth(1).fill("2026-02-01");
  await expect(page.getByRole("alert", { name: /start date/i })).toBeVisible();
  const requestsBefore = ledgerRequests;
  await page.waitForTimeout(100);
  expect(ledgerRequests).toBe(requestsBefore);
});
