import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const password = process.env.E2E_VISUAL_PASSWORD || "visual-acceptance-password";
const users = {
  owner: "visual-owner@example.com",
  inventory_manager: "visual-inventory-manager@example.com",
  procurement_officer: "visual-procurement@example.com",
  receiver: "visual-receiver@example.com",
  counter: "visual-counter@example.com",
  viewer: "visual-viewer@example.com",
} as const;

type ManifestRow = {
  project: string;
  role: string;
  route: string;
  state: string;
  screenshot: string;
  finalUrl: string;
  title: string;
  consoleErrors: string[];
  pageErrors: string[];
};

function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const full = path.join(dir, entry.name);
    return entry.isDirectory() ? walk(full) : [full];
  });
}

function staticRoutes(): string[] {
  const appDir = path.resolve(process.cwd(), "app");
  return walk(appDir)
    .filter(file => file.endsWith(`${path.sep}page.tsx`))
    .map(file => {
      const rel = path.relative(appDir, path.dirname(file)).split(path.sep).join("/");
      return rel ? `/${rel}` : "/";
    })
    .filter(route => !route.includes("[") && route !== "/login")
    .sort();
}

function slug(value: string): string {
  return value.replace(/^\/+/, "").replace(/[^a-zA-Z0-9._-]+/g, "-") || "root";
}

async function signIn(page: import("@playwright/test").Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

for (const [role, email] of Object.entries(users)) {
  test(`visual capture — ${role}`, async ({ page }, testInfo) => {
    test.setTimeout(10 * 60_000);
    const project = testInfo.project.name;
    const root = path.resolve(process.cwd(), "visual-artifacts", project, role);
    fs.mkdirSync(root, { recursive: true });
    const manifest: ManifestRow[] = [];
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on("console", msg => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
    page.on("pageerror", err => pageErrors.push(err.message));

    await signIn(page, email);
    const discovered = new Set(staticRoutes());
    discovered.add("/dashboard");

    // First crawl visible navigation as this role to discover concrete dynamic/detail URLs.
    for (const route of [...discovered]) {
      await page.goto(route, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(250);
      const hrefs = await page.locator('a[href^="/"]').evaluateAll(nodes =>
        nodes.map(node => (node as HTMLAnchorElement).getAttribute("href") || "")
      );
      for (const href of hrefs) {
        if (!href || href.startsWith("//") || href.startsWith("/login") || href.includes("#")) continue;
        discovered.add(href.split("?")[0]);
      }
    }

    for (const route of [...discovered].sort()) {
      const beforeConsole = consoleErrors.length;
      const beforePage = pageErrors.length;
      await page.goto(route, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(450);
      const file = path.join(root, `${slug(route)}--default.png`);
      await page.screenshot({ path: file, fullPage: true });
      manifest.push({
        project,
        role,
        route,
        state: "default",
        screenshot: path.relative(path.resolve(process.cwd(), "visual-artifacts"), file),
        finalUrl: page.url(),
        title: await page.title(),
        consoleErrors: consoleErrors.slice(beforeConsole),
        pageErrors: pageErrors.slice(beforePage),
      });

      // Owner gets a second capture under a synthetic API failure to expose error/empty guards.
      if (role === "owner" && route !== "/dashboard") {
        await page.route("**/api/v1/**", async r => {
          const url = r.request().url();
          if (url.includes("/auth/")) return r.continue();
          return r.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"Visual QA synthetic upstream failure"}' });
        });
        await page.goto(route, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(500);
        const errorFile = path.join(root, `${slug(route)}--error.png`);
        await page.screenshot({ path: errorFile, fullPage: true });
        manifest.push({
          project,
          role,
          route,
          state: "synthetic-error",
          screenshot: path.relative(path.resolve(process.cwd(), "visual-artifacts"), errorFile),
          finalUrl: page.url(),
          title: await page.title(),
          consoleErrors: [],
          pageErrors: [],
        });
        await page.unroute("**/api/v1/**");
      }
    }

    fs.writeFileSync(path.join(root, "manifest.json"), JSON.stringify(manifest, null, 2));
    expect(manifest.length).toBeGreaterThan(0);
  });
}
