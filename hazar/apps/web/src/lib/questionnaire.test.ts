import { describe, expect, it } from "vitest";
import messages from "../../locales/he.json";
import { formatAnswer, formatDate, type Answered } from "./questionnaire";

const q = messages.questionnaire as unknown as Record<string, unknown>;
function t(key: string, values: Record<string, string | number> = {}): string {
  const value = key.split(".").reduce<unknown>((node, part) => (node as Record<string, unknown>)?.[part], q);
  if (typeof value !== "string") throw new Error(`missing he.json key questionnaire.${key}`);
  return value.replace(/\{(\w+)\}/g, (_, k: string) => String(values[k]));
}

describe("formatAnswer", () => {
  it.each<[Answered, string]>([
    [{ id: "resident", kind: "yes_no", value: true }, "כן"],
    [{ id: "disability", kind: "yes_no", value: false }, "לא"],
    [{ id: "sex", kind: "choice", value: "female" }, "אישה"],
    [{ id: "marital_status", kind: "choice", value: "divorced" }, "גרוש/ה"],
    [{ id: "discharge_date", kind: "date", value: "2019-08-01" }, "1.8.2019"],
    [{ id: "children_birth_dates", kind: "dates", value: ["2020-01-02", "2022-12-31"] }, "2.1.2020, 31.12.2022"],
    [{ id: "donation_years", kind: "window_years", value: [2021, 2023] }, "2021, 2023"],
    [
      { id: "localities", kind: "localities", value: [{ name: "חיפה", from_year: 2015, to_year: null }] },
      "חיפה (2015 עד היום)",
    ],
  ])("%j → %s", (answered, expected) => {
    expect(formatAnswer(t, answered)).toBe(expected);
  });

  it("formats dates without timezone drift", () => {
    expect(formatDate("2024-01-01")).toBe("1.1.2024");
  });
});

describe("he.json covers every question id the API defines", () => {
  // Keep in sync with services/api/src/hazar_api/questionnaire.py (also checked end to end by Playwright).
  const ids = [
    "resident", "sex", "marital_status", "has_children", "children_birth_dates", "single_parent", "has_degree",
    "degree_years", "discharged", "discharge_date", "aliyah", "aliyah_date", "disability", "multiple_employers",
    "multiple_employer_years", "partial_year", "partial_years", "donations", "donation_years", "life_insurance",
    "life_insurance_years", "pension_self", "pension_self_years", "localities",
  ];
  it.each(ids)("%s", (id) => {
    expect(t(`questions.${id}`)).toBeTruthy();
  });
});
