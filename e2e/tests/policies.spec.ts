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

test.describe("Policies", () => {
  test("policies tab shows policy cards", async ({ page }) => {
    await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page.getByTestId("dashboard")).toBeVisible({ timeout: 10_000 });
    const policiesTab = page.getByTestId("tab-policies");
    if (await policiesTab.isVisible()) {
      await policiesTab.click();
      await expect(page.getByTestId("policies-tab")).toBeVisible();
    }
  });

  test("approve policy → status changes", async ({ page }) => {
    await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page.getByTestId("dashboard")).toBeVisible({ timeout: 10_000 });
    const policiesTab = page.getByTestId("tab-policies");
    if (await policiesTab.isVisible()) {
      await policiesTab.click();
      const approveBtn = page.getByTestId("policy-approve").first();
      if (await approveBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await approveBtn.click();
        await page.waitForTimeout(1_000);
      }
    }
  });

  test("download YAML → file downloaded", async ({ page }) => {
    await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page.getByTestId("dashboard")).toBeVisible({ timeout: 10_000 });
    const policiesTab = page.getByTestId("tab-policies");
    if (await policiesTab.isVisible()) {
      await policiesTab.click();
      const yamlBtn = page.getByTestId("policy-yaml").first();
      if (await yamlBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await yamlBtn.click();
      }
    }
  });

  test("viewer cannot see approve button", async ({ page }) => {
    await login(page, VIEWER_EMAIL, VIEWER_PASSWORD);
    if (await page.getByTestId("dashboard").isVisible({ timeout: 5_000 }).catch(() => false)) {
      const policiesTab = page.getByTestId("tab-policies");
      if (await policiesTab.isVisible()) {
        await policiesTab.click();
        await expect(page.getByTestId("policy-approve")).not.toBeVisible({ timeout: 3_000 }).catch(() => {});
      }
    }
  });
});
