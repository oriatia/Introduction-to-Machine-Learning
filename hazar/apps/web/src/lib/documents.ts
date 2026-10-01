export type DocType = "form_106" | "form_867" | "donation_receipt" | "insurance" | "pension" | "other";
export const DOC_TYPES: DocType[] = ["form_106", "form_867", "donation_receipt", "insurance", "pension", "other"];
/** Types whose fields are read automatically; others only need a tax year. */
export const EXTRACTABLE: DocType[] = ["form_106"];

export type DocField = {
  name: string;
  kind: "year" | "text" | "digits" | "amount" | "months" | "decimal";
  form_code: string | null;
  value: string | null;
  confidence: number;
  needs_attention: boolean;
};

export type DocumentDetail = {
  id: string;
  type: DocType;
  tax_year: number | null;
  status: "uploaded" | "extracting" | "needs_review" | "confirmed" | "failed";
  content_type: string;
  size_bytes: number;
  created_at: string;
  error: string | null;
  extractor: string | null;
  fields: DocField[];
  confirmed: Record<string, string | number | null> | null;
  file_url: string | null;
};

export type ChecklistItem = {
  doc_type: DocType;
  year: number;
  reasons: string[];
  status: "missing" | "uploaded" | "confirmed";
};

/** Initial form values: confirmed values win over extracted suggestions. */
export function initialValues(doc: DocumentDetail): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of doc.fields) {
    const confirmed = doc.confirmed?.[f.name];
    out[f.name] = confirmed !== undefined && confirmed !== null ? String(confirmed) : (f.value ?? "");
  }
  return out;
}

/** Fields the user must explicitly tick before confirming (low confidence or missing), unless already confirmed. */
export function fieldsToCheck(doc: DocumentDetail): string[] {
  if (doc.status === "confirmed") return [];
  return doc.fields.filter((f) => f.needs_attention).map((f) => f.name);
}
