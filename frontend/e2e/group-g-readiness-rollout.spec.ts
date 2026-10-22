import { expect, test } from "@playwright/test";

const email = process.env.E2E_OWNER_EMAIL || "owner@example.com";
const password = process.env.E2E_OWNER_PASSWORD || "password123";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("CSV validation uses authenticated same-origin API rather than stale localStorage", async ({ page }) => {
  await login(page);
  // Deliberately set the wrong legacy value; session-cookie API must ignore it.
  await page.evaluate(() => localStorage.setItem("inventory_token", "stale-invalid-token"));
  const seen: { url: string; cookie: string; authorization?: string; xRequestedWith?: string }[] = [];
  await page.route("**/api/v1/migration/imports/items/validate", async route => {
    const req = route.request();
    const headers = req.headers();
    seen.push({
      url: req.url(),
      cookie: headers.cookie || "",
      authorization: headers.authorization,
      xRequestedWith: headers["x-requested-with"],
    });
    await route.fulfill({
      status: 201, contentType: "application/json",
      body: JSON.stringify({
        job_id: "synthetic-validation-only",
        import_type: "items", filename: "items.csv", status: "validated",
        summary: { row_count: 1 }, errors: [],
      }),
    });
  });
  await page.goto("/readiness");
  await expect(page.getByRole("heading", { name: "Production Readiness" })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({
    name: "items.csv", mimeType: "text/csv",
    buffer: Buffer.from("sku,name,category,unit\nITEM-G,Group G,Food,EA\n"),
  });
  await page.getByRole("button", { name: "Validate CSV" }).click();
  await expect(page.getByText("Import validated and ready to apply.")).toBeVisible();
  expect(seen).toHaveLength(1);
  expect(new URL(seen[0].url).origin).toBe(new URL(page.url()).origin);
  expect(seen[0].cookie).toContain("inventory_session");
  expect(seen[0].authorization).toBeUndefined();
  expect(seen[0].xRequestedWith).toBe("HiddenOasisInventory");
  await test.info().attach("group-g-readiness-cookie-auth-upload", {
    body: await page.screenshot({ fullPage: true }), contentType: "image/png",
  });
});

test("scoped staff can submit rollout feedback without viewing global incident data", async ({ page }) => {
  await login(page);
  await page.route("**/api/v1/rollout/summary", route => route.fulfill({
    status: 403, contentType: "application/json", body: JSON.stringify({detail:"Global operational records require unrestricted location access"}),
  }));
  await page.route("**/api/v1/incidents", route => route.fulfill({
    status: 403, contentType: "application/json", body: JSON.stringify({detail:"Global operational records require unrestricted location access"}),
  }));
  await page.route("**/api/v1/feedback", route => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 201, contentType: "application/json",
        body: JSON.stringify({id:"synthetic-feedback"}),
      });
    }
    return route.fulfill({
      status: 403, contentType: "application/json",
      body: JSON.stringify({detail:"Global operational records require unrestricted location access"}),
    });
  });
  await page.goto("/rollout");
  await expect(page.getByText("Your location access allows feedback submission.", {exact:false})).toBeVisible();
  await expect(page.getByRole("heading", { name: "Operational incidents" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Run smoke test" })).toHaveCount(0);
  await page.getByRole("textbox", { name: "Feedback details" })
    .fill("Location team needs easier shelf label printing");
  await page.getByRole("button", { name: "Submit feedback" }).click();
  await expect(page.getByText("Feedback submitted.")).toBeVisible();
  await test.info().attach("group-g-scoped-feedback-mobile-desktop", {
    body: await page.screenshot({ fullPage: true }), contentType: "image/png",
  });
});
