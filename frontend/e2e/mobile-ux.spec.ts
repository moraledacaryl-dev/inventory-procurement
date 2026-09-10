import { expect, test } from "@playwright/test";

const email = process.env.E2E_OWNER_EMAIL || "owner@example.com";
const password = process.env.E2E_OWNER_PASSWORD || "password123";

test.use({ viewport: { width: 393, height: 852 } });

async function signIn(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("mobile workflows remain readable at 100% zoom without focus auto-zoom triggers", async ({ page }) => {
  await signIn(page);

  const viewport = await page.locator('meta[name="viewport"]').getAttribute("content");
  expect(viewport || "").toContain("width=device-width");
  expect(viewport || "").not.toContain("user-scalable=no");
  expect(viewport || "").not.toContain("maximum-scale=1");

  for (const path of ["/purchasing", "/inventory-operations", "/receiving", "/counts", "/production", "/fnb/staff-meals", "/assets", "/assets/maintenance", "/dashboard"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");

    const geometry = await page.evaluate(() => {
      const main = document.querySelector<HTMLElement>(".main-area");
      const rect = main?.getBoundingClientRect();
      return {
        overflow: document.documentElement.scrollWidth - window.innerWidth,
        scrollX: window.scrollX,
        mainLeft: rect?.left ?? -1,
        mainRight: rect?.right ?? -1,
        mainWidth: rect?.width ?? 0,
        viewportWidth: window.innerWidth,
        visualOffsetLeft: window.visualViewport?.offsetLeft ?? 0,
        visualWidth: window.visualViewport?.width ?? window.innerWidth,
      };
    });
    expect(geometry.overflow, `${path} should not require horizontal page scrolling`).toBeLessThanOrEqual(1);
    expect(Math.abs(geometry.scrollX), `${path} should open at the left edge, not halfway across the page`).toBeLessThanOrEqual(1);
    expect(Math.abs(geometry.visualOffsetLeft), `${path} visual viewport should start at the left edge`).toBeLessThanOrEqual(1);
    expect(geometry.mainLeft, `${path} main content should begin at the viewport left edge`).toBeGreaterThanOrEqual(-1);
    expect(geometry.mainRight, `${path} main content should fill the phone viewport`).toBeGreaterThanOrEqual(geometry.viewportWidth - 1);
    expect(geometry.mainWidth, `${path} main content should not render as a half-width desktop column`).toBeGreaterThanOrEqual(geometry.viewportWidth - 2);
    expect(geometry.visualWidth, `${path} should remain at normal mobile scale`).toBeGreaterThanOrEqual(geometry.viewportWidth - 2);

    const tinyControls = await page.locator("input:visible, select:visible, textarea:visible").evaluateAll(elements =>
      elements.filter(element => Number.parseFloat(getComputedStyle(element).fontSize) < 16).map(element => ({
        tag: element.tagName,
        fontSize: getComputedStyle(element).fontSize,
        name: element.getAttribute("name") || element.getAttribute("aria-label") || "",
      }))
    );
    expect(tinyControls, `${path} should not contain sub-16px editable controls that can trigger mobile browser auto-zoom`).toEqual([]);

    const undersizedPrimaryControls = await page.locator("button.primary:visible, button.secondary:visible, .menu-button:visible").evaluateAll(elements =>
      elements.filter(element => element.getBoundingClientRect().height < 44).map(element => ({
        text: element.textContent?.trim() || "",
        height: element.getBoundingClientRect().height,
      }))
    );
    expect(undersizedPrimaryControls, `${path} should keep primary touch controls at least 44px tall`).toEqual([]);
  }
});
