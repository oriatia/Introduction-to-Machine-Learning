import { describe, expect, it } from "vitest";
import { fieldsToCheck, initialValues, type DocumentDetail } from "./documents";

const base: DocumentDetail = {
  id: "d",
  type: "form_106",
  tax_year: 2023,
  status: "needs_review",
  content_type: "image/png",
  size_bytes: 1,
  created_at: "",
  error: null,
  extractor: "mock",
  confirmed: null,
  file_url: null,
  fields: [
    { name: "tax_year", kind: "year", form_code: null, value: "2023", confidence: 0.99, needs_attention: false },
    { name: "tax_withheld", kind: "amount", form_code: null, value: "100", confidence: 0.5, needs_attention: true },
    { name: "credit_points", kind: "decimal", form_code: null, value: null, confidence: 0, needs_attention: true },
  ],
};

describe("document helpers", () => {
  it("prefers confirmed values over suggestions", () => {
    expect(initialValues(base)).toEqual({ tax_year: "2023", tax_withheld: "100", credit_points: "" });
    expect(initialValues({ ...base, confirmed: { tax_withheld: 250, credit_points: null } }).tax_withheld).toBe("250");
  });
  it("requires checking low-confidence and missing fields until confirmed", () => {
    expect(fieldsToCheck(base)).toEqual(["tax_withheld", "credit_points"]);
    expect(fieldsToCheck({ ...base, status: "confirmed" })).toEqual([]);
  });
});
