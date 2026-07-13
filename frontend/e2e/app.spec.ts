import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

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

test("login and core operational pages are reachable", async ({ page }) => {
  await signIn(page);
  for (const [label, path, heading] of [
    ["Items", "/items", "Items"],
    ["Suppliers", "/suppliers", "Suppliers"],
    ["Purchasing", "/purchasing", "Purchasing"],
    ["Receiving", "/receiving", "Receiving"],
    ["Inventory Counts", "/counts", "Inventory Counts"],
    ["Recipes & Production", "/production", "Recipes & Production"],
    ["Asset Register", "/assets", "Assets"],
  ] as const) {
    await page.getByRole("link", { name: label, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }
});

test("sidebar state remains visually stable during client navigation", async ({ page }) => {
  await signIn(page);
  const sidebar = page.locator("aside.sidebar");
  const header = page.locator("header.app-header");
  await expect(sidebar).toBeVisible();
  const beforeSidebar = await sidebar.boundingBox();
  const beforeHeader = await header.boundingBox();
  await page.getByRole("link", { name: "Items", exact: true }).click();
  await expect(page).toHaveURL(/\/items$/);
  const afterSidebar = await sidebar.boundingBox();
  const afterHeader = await header.boundingBox();
  expect(afterSidebar?.width).toBe(beforeSidebar?.width);
  expect(afterHeader?.x).toBe(beforeHeader?.x);
  await expect(page.getByRole("link", { name: "Operational Access", exact: true })).toBeVisible();
});

test("sidebar scroll position survives route changes", async ({ page, isMobile }) => {
  test.skip(isMobile, "desktop sidebar owns the persistent scroll container");
  await signIn(page);
  const sidebar = page.locator("aside.sidebar");
  await sidebar.evaluate(element => { element.scrollTop = element.scrollHeight; });
  const before = await sidebar.evaluate(element => element.scrollTop);
  expect(before).toBeGreaterThan(0);
  await page.getByRole("link", { name: "Rollout", exact: true }).click();
  await expect(page).toHaveURL(/\/rollout$/);
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
  await page.getByRole("link", { name: "Items", exact: true }).click();
  await expect(page).toHaveURL(/\/items$/);
  await expect(page.locator("aside.sidebar")).not.toHaveClass(/is-open/);
});

test("critical pages have no serious Axe violations", async ({ page }) => {
  await signIn(page);
  for (const path of ["/dashboard", "/items", "/purchasing", "/receiving", "/counts", "/assets"]) {
    await page.goto(path);
    await expect(page.locator("main#main-content")).toBeVisible();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const serious = results.violations.filter(v => v.impact === "critical" || v.impact === "serious");
    expect(serious, `${path}: ${serious.map(v => `${v.id} (${v.nodes.length})`).join(", ")}`).toEqual([]);
  }
});
