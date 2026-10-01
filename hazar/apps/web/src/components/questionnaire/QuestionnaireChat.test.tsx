import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import messages from "../../../locales/he.json";
import type { QuestionnaireState } from "@/lib/questionnaire";
import { axeViolations } from "@/test/axe";
import { QuestionnaireChat } from "./QuestionnaireChat";

const Q = messages.questionnaire;
const WINDOW = [2020, 2021, 2022, 2023, 2024, 2025];

function state(partial: Partial<QuestionnaireState>): QuestionnaireState {
  return { next: null, answered: [], total: 0, complete: false, ...partial };
}

function reply(status: number, body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

function renderChat(initial: QuestionnaireState) {
  return render(
    <NextIntlClientProvider locale="he" messages={messages}>
      <QuestionnaireChat initial={initial} />
    </NextIntlClientProvider>,
  );
}

describe("QuestionnaireChat", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("answers a yes/no question and shows the answer as a user bubble", async () => {
    fetchMock.mockReturnValueOnce(
      reply(200, state({ answered: [{ id: "resident", kind: "yes_no", value: true }], next: { id: "sex", kind: "choice", options: ["female", "male"], window: [] } })),
    );
    const { container } = renderChat(state({ next: { id: "resident", kind: "yes_no", options: [], window: [] } }));
    expect(await axeViolations(container)).toEqual([]);

    await userEvent.click(screen.getByRole("button", { name: Q.yes }));
    expect(await screen.findByRole("button", { name: Q.options.sex.female })).toBeInTheDocument();
    expect(screen.getByText(Q.yes, { selector: "div" })).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/questionnaire/answers");
    expect(JSON.parse(init.body)).toEqual({ question_id: "resident", value: true });
    expect(await axeViolations(container)).toEqual([]);
  });

  it("submits selected window years", async () => {
    fetchMock.mockReturnValueOnce(reply(200, state({ complete: true })));
    renderChat(state({ next: { id: "donation_years", kind: "window_years", options: [], window: WINDOW } }));
    const submit = screen.getByRole("button", { name: Q.submit });
    expect(submit).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "2023" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "2021" }));
    await userEvent.click(submit);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).value).toEqual([2021, 2023]);
    expect(await screen.findByRole("link", { name: Q.toEstimate })).toHaveAttribute("href", "/estimate");
  });

  it("submits localities with an open end year as null", async () => {
    fetchMock.mockReturnValueOnce(reply(200, state({ complete: true })));
    renderChat(state({ next: { id: "localities", kind: "localities", options: [], window: [] } }));
    await userEvent.type(screen.getByLabelText(Q.localityName), "באר שבע");
    await userEvent.type(screen.getByLabelText(Q.fromYear), "2018");
    await userEvent.click(screen.getByRole("button", { name: Q.submit }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).value).toEqual([
      { name: "באר שבע", from_year: 2018, to_year: null },
    ]);
  });

  it("undo posts to the API", async () => {
    fetchMock.mockReturnValueOnce(reply(200, state({ next: { id: "resident", kind: "yes_no", options: [], window: [] } })));
    renderChat(
      state({
        answered: [{ id: "resident", kind: "yes_no", value: true }],
        next: { id: "sex", kind: "choice", options: ["female", "male"], window: [] },
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: Q.undo }));
    await waitFor(() => expect(fetchMock.mock.calls[0][0]).toBe("/api/questionnaire/undo"));
    expect(await screen.findByRole("button", { name: Q.yes })).toBeInTheDocument();
  });

  it("shows a validation error from the API", async () => {
    fetchMock.mockReturnValueOnce(reply(422, { error: "invalid_answer" }));
    renderChat(state({ next: { id: "discharge_date", kind: "date", options: [], window: [] } }));
    const input = screen.getByLabelText(`${Q.dateLabel} 1`);
    await userEvent.type(input, "2019-08-01");
    await userEvent.click(screen.getByRole("button", { name: Q.submit }));
    expect(await screen.findByRole("alert")).toHaveTextContent(Q.errors.invalid_answer);
  });
});
