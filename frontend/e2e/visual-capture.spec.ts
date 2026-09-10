import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const visualEnabled = process.env.VISUAL_CAPTURE === "1";
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
  httpErrors: string[];
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
    test.skip(!visualEnabled, "Set VISUAL_CAPTURE=1 for exhaustive screenshot capture");
    test.setTimeout(10 * 60_000);
    const project = testInfo.project.name;
    const isMobile = project.includes("mobile");
    const root = path.resolve(process.cwd(), "visual-artifacts", project, role);
    fs.mkdirSync(root, { recursive: true });
    const manifest: ManifestRow[] = [];
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    const requestCapture = new WeakMap<import("@playwright/test").Request, number>();
    const httpErrorsByCapture = new Map<number, string[]>();
    let activeCapture = 0;

    page.on("console", msg => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
    page.on("pageerror", err => pageErrors.push(err.message));
    page.on("request", request => requestCapture.set(request, activeCapture));
    page.on("response", response => {
      if (response.status() < 500) return;
      const capture = requestCapture.get(response.request()) ?? activeCapture;
      if (capture <= 0) return;
      const errors = httpErrorsByCapture.get(capture) || [];
      errors.push(`${response.status()} ${response.request().method()} ${response.url()}`);
      httpErrorsByCapture.set(capture, errors);
    });

    await signIn(page, email);
    const discovered = new Set(staticRoutes());
    discovered.add("/dashboard");

    for (const route of [...discovered]) {
      activeCapture = 0;
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

    let captureSequence = 0;
    for (const route of [...discovered].sort()) {
      const captureId = ++captureSequence;
      activeCapture = captureId;
      httpErrorsByCapture.set(captureId, []);
      const beforeConsole = consoleErrors.length;
      const beforePage = pageErrors.length;
      await page.goto(route, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(450);
      if (isMobile) {
        const framing = await page.evaluate(() => {
          const visualWidth = window.visualViewport?.width ?? window.innerWidth;
          const mainRect = document.querySelector<HTMLElement>(".main-area")?.getBoundingClientRect();
          const offenders = Array.from(document.querySelectorAll<HTMLElement>("body *"))
            .map(element => {
              const rect = element.getBoundingClientRect();
              return {
                tag: element.tagName.toLowerCase(),
                className: typeof element.className === "string" ? element.className : "",
                text: (element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 70),
                left: Math.round(rect.left),
                right: Math.round(rect.right),
                width: Math.round(rect.width),
                scrollWidth: element.scrollWidth,
                clientWidth: element.clientWidth,
              };
            })
            .filter(row => row.right > visualWidth + 2 || row.left < -2 || row.scrollWidth > row.clientWidth + 2)
            .sort((a, b) => Math.max(b.right - visualWidth, b.scrollWidth - b.clientWidth) - Math.max(a.right - visualWidth, a.scrollWidth - a.clientWidth))
            .slice(0, 12);
          return {
            scrollX: window.scrollX,
            innerWidth: window.innerWidth,
            documentWidth: document.documentElement.scrollWidth,
            visualOffsetLeft: window.visualViewport?.offsetLeft ?? 0,
            visualWidth,
            main: mainRect ? { left: mainRect.left, right: mainRect.right, width: mainRect.width } : null,
            offenders,
          };
        });
        const diagnostic = JSON.stringify({ innerWidth: framing.innerWidth, visualWidth: framing.visualWidth, documentWidth: framing.documentWidth, offenders: framing.offenders });
        expect(Math.abs(framing.scrollX), `${route} mobile capture must start at x=0. ${diagnostic}`).toBeLessThanOrEqual(1);
        expect(Math.abs(framing.visualOffsetLeft), `${route} mobile visual viewport must start at x=0. ${diagnostic}`).toBeLessThanOrEqual(1);
        expect(framing.documentWidth, `${route} mobile document must fit the visible phone viewport. ${diagnostic}`).toBeLessThanOrEqual(framing.visualWidth + 2);
        if (framing.main) {
          expect(framing.main.left, `${route} main content must begin at left edge. ${diagnostic}`).toBeGreaterThanOrEqual(-1);
          expect(framing.main.right, `${route} main content must fill visible phone viewport. ${diagnostic}`).toBeGreaterThanOrEqual(framing.visualWidth - 1);
          expect(framing.main.width, `${route} main content must not be a half-width column. ${diagnostic}`).toBeGreaterThanOrEqual(framing.visualWidth - 2);
        }
        await page.screenshot({ path: path.join(root, `${slug(route)}--viewport.png`), fullPage: false });
      }
      const file = path.join(root, `${slug(route)}--default.png`);
      await page.screenshot({ path: file, fullPage: true });
      const routeConsoleErrors = consoleErrors
        .slice(beforeConsole)
        .filter(message => !/Failed to load resource: the server responded with a status of 5\d\d/i.test(message));
      manifest.push({
        project,
        role,
        route,
        state: "default",
        screenshot: path.relative(path.resolve(process.cwd(), "visual-artifacts"), file),
        finalUrl: page.url(),
        title: await page.title(),
        consoleErrors: routeConsoleErrors,
        pageErrors: pageErrors.slice(beforePage),
        httpErrors: httpErrorsByCapture.get(captureId) || [],
      });

      activeCapture = 0;
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
          httpErrors: [],
        });
        await page.unroute("**/api/v1/**");
      }
    }
    activeCapture = 0;
    fs.writeFileSync(path.join(root, "manifest.json"), JSON.stringify(manifest, null, 2));
  });
}
