import { expect, test, type Page } from "@playwright/test";
import he from "../locales/he.json" with { type: "json" };
import { expectNoA11yViolations, randomPhone, signIn } from "./helpers";

const Q = he.questionnaire;

async function expectQuestion(page: Page, id: keyof typeof Q.questions) {
  await expect(page.getByText(Q.questions[id], { exact: true }).last()).toBeVisible();
}

async function yesNo(page: Page, id: keyof typeof Q.questions, yes: boolean) {
  await expectQuestion(page, id);
  await page.getByRole("group", { name: Q.questions[id] }).getByRole("button", { name: yes ? Q.yes : Q.no }).click();
}

async function choose(page: Page, id: "sex" | "marital_status", label: string) {
  await expectQuestion(page, id);
  await page.getByRole("group", { name: Q.questions[id] }).getByRole("button", { name: label }).click();
}

async function pickYears(page: Page, id: keyof typeof Q.questions, years: number[]) {
  await expectQuestion(page, id);
  for (const y of years) await page.getByRole("checkbox", { name: String(y) }).check();
  await page.getByRole("button", { name: Q.submit }).click();
}

test("questionnaire → estimate → timeline", async ({ page }) => {
  await signIn(page, randomPhone());
  await page.getByRole("link", { name: he.home.startQuestionnaire }).click();
  await expect(page).toHaveURL(/\/questionnaire$/);
  await expectNoA11yViolations(page);

  await yesNo(page, "resident", true);
  await choose(page, "sex", Q.options.sex.female);
  await choose(page, "marital_status", Q.options.marital_status.divorced);
  await yesNo(page, "has_children", true);

  await expectQuestion(page, "children_birth_dates");
  await page.getByLabel(`${Q.dateLabel} 1`).fill("2022-06-01");
  await page.getByRole("button", { name: Q.submit }).click();

  await yesNo(page, "single_parent", true);
  await yesNo(page, "has_degree", false);
  await yesNo(page, "discharged", false);
  await yesNo(page, "aliyah", false);
  await yesNo(page, "disability", false);
  await yesNo(page, "multiple_employers", false);
  await yesNo(page, "partial_year", true);
  await pickYears(page, "partial_years", [2024]);
  await yesNo(page, "donations", true);
  await pickYears(page, "donation_years", [2023]);
  await yesNo(page, "life_insurance", false);

  // Undo the last answer and give a different one.
  await expectQuestion(page, "pension_self");
  await page.getByRole("button", { name: Q.undo }).click();
  await yesNo(page, "life_insurance", false);
  await yesNo(page, "pension_self", false);

  await expectQuestion(page, "localities");
  await page.getByLabel(Q.localityName).fill("באר שבע");
  await page.getByLabel(Q.fromYear).fill("2018");
  await page.getByRole("button", { name: Q.submit }).click();

  await expect(page.getByText(Q.doneTitle)).toBeVisible();
  await expectNoA11yViolations(page);
  await page.getByRole("link", { name: Q.toEstimate }).click();

  // Estimate: benefits per year, no amounts.
  await expect(page.getByRole("heading", { level: 1, name: he.estimate.headline })).toBeVisible();
  await expect(page.getByText(he.estimate.noAmounts)).toBeVisible();
  const children = page.getByRole("heading", { name: "נקודות זיכוי על ילדים" });
  await expect(children).toBeVisible();
  await expect(page.getByRole("heading", { name: "זיכוי על תרומות" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "שנה שבה לא עבדת את כל השנה" })).toBeVisible();
  await expect(page.getByText(he.estimate.documents.donation_receipt)).toBeVisible();
  await expect(page.locator("main")).not.toContainText("₪");
  await page.getByText(he.estimate.why).first().click();
  await expect(page.getByText(he.estimate.legalRefPending).first()).toBeVisible();
  await expectNoA11yViolations(page);

  // Timeline built from the answers.
  await page.getByRole("link", { name: he.estimate.toTimeline }).click();
  await expect(page.getByRole("heading", { level: 1, name: he.timeline.title })).toBeVisible();
  await expect(page.getByText(he.timeline.types.child_birth)).toBeVisible();
  await expect(page.getByText("מגורים בבאר שבע")).toBeVisible();
  await expectNoA11yViolations(page);

  // Home now points to the estimate.
  await page.goto("/home");
  await expect(page.getByRole("link", { name: he.home.viewEstimate })).toBeVisible();
});

test("the estimate redirects to the questionnaire until it is complete", async ({ page }) => {
  await signIn(page, randomPhone());
  await page.goto("/estimate");
  await expect(page).toHaveURL(/\/questionnaire$/);
});
