import path from "node:path";
import { expect, test } from "@playwright/test";
import he from "../locales/he.json" with { type: "json" };
import { alert, expectNoA11yViolations, randomPhone, signIn } from "./helpers";

const D = he.documents;
// A PNG carrying the mock extractor's expected values (made by hazar_api.extraction.make_mock_png).
const FIXTURE = path.join(__dirname, "fixtures", "form106-mock.png");

test("photograph a Form 106 → extracted → reviewed → confirmed", async ({ page }) => {
  await signIn(page, randomPhone());
  await page.getByRole("link", { name: he.home.viewDocuments }).click();
  await expect(page.getByRole("heading", { level: 1, name: D.title })).toBeVisible();
  await expectNoA11yViolations(page);

  const row2023 = page.getByRole("link", { name: `${D.upload} ${D.types.form_106} 2023` });
  await row2023.click();
  await expect(page.getByRole("heading", { level: 1, name: D.uploadPage.title })).toBeVisible();
  await page.getByLabel(D.uploadPage.chooseFile).setInputFiles(FIXTURE);
  await expect(page.getByText(D.uploadPage.warnings.small)).toBeVisible(); // the fixture is 1x1 px
  await expectNoA11yViolations(page);
  await page.getByRole("button", { name: D.uploadPage.send }).click();

  // Worker extracts; the page polls until the fields appear.
  await expect(page.getByRole("heading", { level: 1, name: D.review.title })).toBeVisible();
  const income = page.getByLabel(D.review.fields.gross_taxable_income);
  await expect(income).toHaveValue("184500", { timeout: 15_000 });
  await expect(page.getByLabel(D.review.fields.tax_withheld)).toHaveValue("21340");

  const confirm = page.getByRole("button", { name: D.review.confirm });
  await expect(confirm).toBeDisabled(); // two low-confidence fields not yet checked
  await income.fill("185500");
  for (const box of await page.getByRole("checkbox", { name: D.review.checked }).all()) await box.check();
  await expectNoA11yViolations(page);
  await confirm.click();
  await expect(page.getByText(D.review.confirmed)).toBeVisible();
  await expect(page.getByText("185500")).toBeVisible();

  // The checklist shows 2023 as confirmed.
  await page.getByRole("link", { name: D.review.backToDocuments }).click();
  const card2023 = page.getByRole("heading", { name: D.year.replace("{year}", "2023") }).locator("..");
  await expect(card2023.getByText(D.status.confirmed)).toBeVisible();
  await expect(page.getByRole("link", { name: `${D.upload} ${D.types.form_106} 2023` })).toHaveCount(0);
});

test("a non-image file is rejected", async ({ page }) => {
  await signIn(page, randomPhone());
  await page.goto("/documents/upload");
  await page.getByLabel(D.uploadPage.chooseFile).setInputFiles({
    name: "doc.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("<html>not a pdf</html>"),
  });
  await page.getByRole("button", { name: D.uploadPage.send }).click();
  await expect(alert(page, D.uploadPage.errors.unsupported_file)).toBeVisible();
});
