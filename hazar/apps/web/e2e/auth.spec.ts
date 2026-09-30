import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import he from "../locales/he.json" with { type: "json" };

// Seeded by `python -m hazar_api.seed` (see docs/local-dev.md). One advisor per project, so parallel
// projects never race on the same phone's one-time code.
const SEEDED_ADVISORS: Record<string, string> = { mobile: "0500000002", desktop: "0500000003" };

function randomPhone(): string {
  return `05${Math.floor(Math.random() * 10)}${String(Math.floor(Math.random() * 1e7)).padStart(7, "0")}`;
}

async function readOtp(request: APIRequestContext, phone: string): Promise<string> {
  const res = await request.post("/api/dev/last-sms", { data: { phone } });
  expect(res.ok()).toBeTruthy();
  const { text } = (await res.json()) as { text: string };
  const match = text.match(/\b(\d{6})\b/);
  expect(match).not.toBeNull();
  return match![1];
}

async function signIn(page: Page, phone: string) {
  await page.goto("/login");
  await page.getByLabel(he.auth.phoneLabel).fill(phone);
  await page.getByRole("button", { name: he.auth.sendCode }).click();
  await expect(page.getByRole("heading", { name: he.auth.codeTitle })).toBeFocused();
  await page.getByLabel(he.auth.codeLabel).fill(await readOtp(page.request, phone));
  await page.getByRole("button", { name: he.auth.verify, exact: true }).click();
  await expect(page).toHaveURL(/\/home/);
}

/** Our error alerts. (Next.js also renders an empty role="alert" route announcer.) */
function alert(page: Page, text: string) {
  return page.getByRole("alert").filter({ hasText: text });
}

async function expectNoA11yViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => v.id)).toEqual([]);
}

test("page is Hebrew RTL and accessible", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "he");
  await expectNoA11yViolations(page);
  await page.goto("/login");
  await expectNoA11yViolations(page);
  await page.goto("/design");
  await expectNoA11yViolations(page);
});

test("a new user registers, logs out and logs back in", async ({ page }) => {
  const phone = randomPhone();

  await page.goto("/");
  await page.getByRole("link", { name: he.landing.cta }).click();
  await expect(page).toHaveURL(/\/login$/);

  await signIn(page, phone);
  await expect(page.getByRole("status")).toHaveText(he.home.welcomeNew);
  await expect(page.getByRole("link", { name: he.home.advisorLink })).toHaveCount(0);
  await expectNoA11yViolations(page);

  // Regular users can't open the advisor back office.
  await page.goto("/advisor");
  await expect(page.getByRole("heading", { name: he.advisor.forbiddenTitle })).toBeVisible();

  await page.goto("/home");
  await page.getByRole("button", { name: he.home.logout }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/home");
  await expect(page).toHaveURL(/\/login$/);

  await signIn(page, phone);
  await expect(page.getByRole("status")).toHaveText(he.home.welcomeBack);
});

test("a wrong code shows an error and keeps the user signed out", async ({ page }) => {
  const phone = randomPhone();
  await page.goto("/login");
  await page.getByLabel(he.auth.phoneLabel).fill(phone);
  await page.getByRole("button", { name: he.auth.sendCode }).click();
  const real = await readOtp(page.request, phone);
  await page.getByLabel(he.auth.codeLabel).fill(real === "000000" ? "111111" : "000000");
  await page.getByRole("button", { name: he.auth.verify, exact: true }).click();
  await expect(alert(page, he.auth.errors.invalid_code)).toBeVisible();
  await page.goto("/home");
  await expect(page).toHaveURL(/\/login$/);
});

test("an invalid phone number is rejected", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel(he.auth.phoneLabel).fill("03-1234567");
  await page.getByRole("button", { name: he.auth.sendCode }).click();
  await expect(alert(page, he.auth.errors.invalid_phone)).toBeVisible();
});

test("the seeded advisor reaches the back office", async ({ page }, testInfo) => {
  await signIn(page, SEEDED_ADVISORS[testInfo.project.name]);
  await page.getByRole("link", { name: he.home.advisorLink }).click();
  await expect(page.getByRole("heading", { name: he.advisor.title })).toBeVisible();
  await expect(page.getByText(he.advisor.empty)).toBeVisible();
});
