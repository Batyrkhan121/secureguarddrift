import { test, expect } from "@playwright/test";

const VALID_EMAIL = "admin@secureguard.dev";
const VALID_PASSWORD = "admin123";

test.describe("Login Flow", () => {
  test("valid credentials → dashboard visible", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("login-email").fill(VALID_EMAIL);
    await page.getByTestId("login-password").fill(VALID_PASSWORD);
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("dashboard")).toBeVisible({ timeout: 10_000 });
  });

  test("invalid credentials → error message", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("login-email").fill("wrong@test.com");
    await page.getByTestId("login-password").fill("wrongpass");
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("login-error")).toBeVisible();
  });

  test("logout → redirected to login page", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("login-email").fill(VALID_EMAIL);
    await page.getByTestId("login-password").fill(VALID_PASSWORD);
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("dashboard")).toBeVisible({ timeout: 10_000 });
    await page.getByTestId("user-menu").click();
    await page.getByTestId("logout-btn").click();
    await expect(page.getByTestId("login-form")).toBeVisible();
  });

  test("protected page without auth → redirect to login", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("login-form")).toBeVisible({ timeout: 5_000 });
  });
});
