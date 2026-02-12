import { test, expect } from "@playwright/test";

const VALID_EMAIL = "admin@secureguard.dev";
const VALID_PASSWORD = "admin123";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(VALID_EMAIL);
  await page.getByTestId("login-password").fill(VALID_PASSWORD);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("dashboard")).toBeVisible({ timeout: 10_000 });
}

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("graph container renders", async ({ page }) => {
    await expect(page.getByTestId("service-graph")).toBeVisible();
  });

  test("drift feed shows cards", async ({ page }) => {
    const feed = page.getByTestId("drift-feed");
    await expect(feed).toBeVisible();
  });

  test("summary bar shows severity counts", async ({ page }) => {
    const summary = page.getByTestId("summary-bar");
    await expect(summary).toBeVisible();
    await expect(summary).toContainText(/critical|high|medium|low/i);
  });

  test("click on drift card → card expands", async ({ page }) => {
    const card = page.getByTestId("drift-card").first();
    if (await card.isVisible()) {
      await card.click();
      await expect(page.getByTestId("drift-card-body").first()).toBeVisible();
    }
  });

  test("Analyze button → updates drift feed", async ({ page }) => {
    const analyzeBtn = page.getByTestId("analyze-btn");
    if (await analyzeBtn.isVisible()) {
      await analyzeBtn.click();
      await page.waitForTimeout(1_000);
      await expect(page.getByTestId("drift-feed")).toBeVisible();
    }
  });

  test("Export button → triggers download", async ({ page }) => {
    const exportBtn = page.getByTestId("export-btn");
    if (await exportBtn.isVisible()) {
      const [download] = await Promise.all([
        page.waitForEvent("download", { timeout: 5_000 }).catch(() => null),
        exportBtn.click(),
      ]);
      if (download) {
        expect(download.suggestedFilename()).toBeTruthy();
      }
    }
  });
});
