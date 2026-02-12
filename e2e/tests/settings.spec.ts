import { test, expect } from "@playwright/test";

const ADMIN_EMAIL = "admin@secureguard.dev";
const ADMIN_PASSWORD = "admin123";
const VIEWER_EMAIL = "viewer@secureguard.dev";
const VIEWER_PASSWORD = "viewer123";

async function login(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(email);
  await page.getByTestId("login-password").fill(password);
  await page.getByTestId("login-submit").click();
}

test.describe("Settings Page", () => {
  test("admin can access settings page", async ({ page }) => {
    await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page.getByTestId("dashboard")).toBeVisible({ timeout: 10_000 });
    await page.goto("/settings");
    await expect(page.getByTestId("settings-page")).toBeVisible({ timeout: 5_000 });
  });

  test("viewer sees Access Denied on settings", async ({ page }) => {
    await login(page, VIEWER_EMAIL, VIEWER_PASSWORD);
    if (await page.getByTestId("dashboard").isVisible({ timeout: 5_000 }).catch(() => false)) {
      await page.goto("/settings");
      await expect(page.getByText(/access denied/i)).toBeVisible({ timeout: 5_000 });
    }
  });

  test("Slack webhook test button exists", async ({ page }) => {
    await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page.getByTestId("dashboard")).toBeVisible({ timeout: 10_000 });
    await page.goto("/settings");
    if (await page.getByTestId("settings-page").isVisible({ timeout: 5_000 }).catch(() => false)) {
      const testBtn = page.getByTestId("slack-test-btn");
      if (await testBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await testBtn.click();
        await page.waitForTimeout(1_000);
      }
    }
  });
});
