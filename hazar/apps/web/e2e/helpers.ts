import AxeBuilder from "@axe-core/playwright";
import { expect, type APIRequestContext, type Page } from "@playwright/test";
import he from "../locales/he.json" with { type: "json" };

export function randomPhone(): string {
  return `05${Math.floor(Math.random() * 10)}${String(Math.floor(Math.random() * 1e7)).padStart(7, "0")}`;
}

export async function readOtp(request: APIRequestContext, phone: string): Promise<string> {
  const res = await request.post("/api/dev/last-sms", { data: { phone } });
  expect(res.ok()).toBeTruthy();
  const { text } = (await res.json()) as { text: string };
  const match = text.match(/\b(\d{6})\b/);
  expect(match).not.toBeNull();
  return match![1];
}

export async function signIn(page: Page, phone: string) {
  await page.goto("/login");
  await page.getByLabel(he.auth.phoneLabel).fill(phone);
  await page.getByRole("button", { name: he.auth.sendCode }).click();
  await expect(page.getByRole("heading", { name: he.auth.codeTitle })).toBeFocused();
  await page.getByLabel(he.auth.codeLabel).fill(await readOtp(page.request, phone));
  await page.getByRole("button", { name: he.auth.verify, exact: true }).click();
  await expect(page).toHaveURL(/\/home/);
}

/** Our error alerts. (Next.js also renders an empty role="alert" route announcer.) */
export function alert(page: Page, text: string) {
  return page.getByRole("alert").filter({ hasText: text });
}

export async function expectNoA11yViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => v.id)).toEqual([]);
}
