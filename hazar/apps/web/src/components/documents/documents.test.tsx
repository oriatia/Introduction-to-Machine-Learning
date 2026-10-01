import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import messages from "../../../locales/he.json";
import type { DocumentDetail } from "@/lib/documents";
import { axeViolations } from "@/test/axe";
import { ReviewDocument } from "./ReviewDocument";
import { UploadForm } from "./UploadForm";

const D = messages.documents;
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn() }) }));

function wrap(ui: React.ReactNode) {
  return render(
    <NextIntlClientProvider locale="he" messages={messages}>
      {ui}
    </NextIntlClientProvider>,
  );
}

function reply(status: number, body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

const doc: DocumentDetail = {
  id: "11111111-1111-1111-1111-111111111111",
  type: "form_106",
  tax_year: 2023,
  status: "needs_review",
  content_type: "image/png",
  size_bytes: 10,
  created_at: "2026-10-01T00:00:00Z",
  error: null,
  extractor: "mock",
  confirmed: null,
  file_url: "/api/files/token",
  fields: [
    { name: "tax_year", kind: "year", form_code: null, value: "2023", confidence: 0.99, needs_attention: false },
    { name: "tax_withheld", kind: "amount", form_code: null, value: "21340", confidence: 0.6, needs_attention: true },
  ],
};

describe("documents UI", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    fetchMock.mockReset();
    push.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("review: low-confidence fields must be ticked before confirming", async () => {
    fetchMock.mockReturnValueOnce(reply(200, { ...doc, status: "confirmed", confirmed: { tax_year: 2023, tax_withheld: 21400 } }));
    const { container } = wrap(<ReviewDocument initial={doc} years={[2025, 2024, 2023]} />);
    expect(await axeViolations(container)).toEqual([]);

    const confirm = screen.getByRole("button", { name: D.review.confirm });
    expect(confirm).toBeDisabled();
    const withheld = screen.getByLabelText(D.review.fields.tax_withheld);
    expect(withheld).toHaveAccessibleDescription(D.review.needsAttention);
    await userEvent.clear(withheld);
    await userEvent.type(withheld, "21400");
    await userEvent.click(screen.getByRole("checkbox", { name: D.review.checked }));
    expect(confirm).toBeEnabled();
    await userEvent.click(confirm);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`/api/documents/${doc.id}/confirm`);
    expect(JSON.parse(init.body)).toEqual({ fields: { tax_year: "2023", tax_withheld: "21400" } });
    expect(await screen.findByText(D.review.confirmed)).toBeInTheDocument();
    expect(screen.getByText("21400")).toBeInTheDocument();
  });

  it("review: shows a field-specific validation error", async () => {
    fetchMock.mockReturnValueOnce(reply(422, { error: "invalid_field:tax_withheld" }));
    wrap(<ReviewDocument initial={{ ...doc, fields: [doc.fields[0]] }} years={[2023]} />);
    await userEvent.click(screen.getByRole("button", { name: D.review.confirm }));
    expect(await screen.findByRole("alert")).toHaveTextContent(D.review.fields.tax_withheld);
  });

  it("review: polls while extracting", async () => {
    fetchMock.mockReturnValueOnce(reply(200, doc));
    wrap(<ReviewDocument initial={{ ...doc, status: "extracting", fields: [] }} years={[2023]} />);
    expect(screen.getByText(D.review.extracting)).toBeInTheDocument();
    expect(await screen.findByLabelText(D.review.fields.tax_withheld, {}, { timeout: 3000 })).toHaveValue("21340");
  });

  it("upload: a receipt needs a year; posts multipart with the CSRF header", async () => {
    fetchMock.mockReturnValueOnce(reply(201, { id: "abc" }));
    const { container } = wrap(<UploadForm initialType="donation_receipt" initialYear={null} years={[2025, 2024]} />);
    expect(await axeViolations(container)).toEqual([]);
    const pdf = new File(["%PDF-1.7"], "receipt.pdf", { type: "application/pdf" });
    await userEvent.upload(screen.getByLabelText(D.uploadPage.chooseFile), pdf);
    const send = await screen.findByRole("button", { name: D.uploadPage.send });
    expect(send).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText(D.uploadPage.yearLabel), "2024");
    await userEvent.click(send);

    await waitFor(() => expect(push).toHaveBeenCalledWith("/documents/abc"));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/documents");
    expect(init.headers["X-Hazar-Upload"]).toBe("1");
    const body = init.body as FormData;
    expect(body.get("type")).toBe("donation_receipt");
    expect(body.get("tax_year")).toBe("2024");
  });

  it("upload: maps API errors to Hebrew messages", async () => {
    fetchMock.mockReturnValueOnce(reply(415, { error: "unsupported_file" }));
    wrap(<UploadForm initialType="form_106" initialYear={null} years={[2025]} />);
    await userEvent.upload(
      screen.getByLabelText(D.uploadPage.chooseFile),
      new File(["%PDF"], "x.pdf", { type: "application/pdf" }),
    );
    await userEvent.click(await screen.findByRole("button", { name: D.uploadPage.send }));
    expect(await screen.findByRole("alert")).toHaveTextContent(D.uploadPage.errors.unsupported_file);
  });
});
