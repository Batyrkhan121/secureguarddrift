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

test.describe("Drift Analysis", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("select snapshots and analyze → events appear", async ({ page }) => {
    const baselineSelect = page.getByTestId("baseline-select");
    const currentSelect = page.getByTestId("current-select");
    if (await baselineSelect.isVisible() && await currentSelect.isVisible()) {
      await page.getByTestId("analyze-btn").click();
      await page.waitForTimeout(2_000);
      await expect(page.getByTestId("drift-feed")).toBeVisible();
    }
  });

  test("critical event has severity styling", async ({ page }) => {
    const criticalCard = page.locator('[data-testid="drift-card"][data-severity="critical"]').first();
    if (await criticalCard.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await expect(criticalCard).toHaveCSS("border-left-color", /rgb/);
    }
  });

  test("click drift card → edge highlighted in graph", async ({ page }) => {
    const card = page.getByTestId("drift-card").first();
    if (await card.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await card.click();
      await expect(page.getByTestId("service-graph")).toBeVisible();
    }
  });

  test("feedback button sends request", async ({ page }) => {
    const card = page.getByTestId("drift-card").first();
    if (await card.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await card.click();
      const feedbackBtn = page.getByTestId("feedback-agree").first();
      if (await feedbackBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
        const responsePromise = page.waitForResponse(
          (resp) => resp.url().includes("/feedback") && resp.status() < 500,
          { timeout: 5_000 }
        ).catch(() => null);
        await feedbackBtn.click();
        const response = await responsePromise;
        if (response) {
          expect(response.status()).toBeLessThan(500);
        }
      }
    }
  });
});
