import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import messages from "../../../locales/he.json";
import { axeViolations } from "@/test/axe";
import { LoginFlow } from "./LoginFlow";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, refresh: vi.fn() }) }));

function renderFlow() {
  return render(
    <NextIntlClientProvider locale="he" messages={messages}>
      <LoginFlow />
    </NextIntlClientProvider>,
  );
}

function reply(status: number, body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

describe("LoginFlow", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    replace.mockReset();
    fetchMock.mockReset();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("goes phone → code → /home for a new user", async () => {
    fetchMock
      .mockReturnValueOnce(reply(202, { status: "sent", resend_after: 60 }))
      .mockReturnValueOnce(reply(200, { is_new: true, user: {} }));
    const { container } = renderFlow();
    expect(await axeViolations(container)).toEqual([]);

    await userEvent.type(screen.getByLabelText(messages.auth.phoneLabel), "050-1234567");
    await userEvent.click(screen.getByRole("button", { name: messages.auth.sendCode }));

    const codeInput = await screen.findByLabelText(messages.auth.codeLabel);
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent(messages.auth.steps.code);
    expect(screen.getByRole("button", { name: messages.auth.resend })).toBeDisabled();
    expect(await axeViolations(container)).toEqual([]);

    await userEvent.type(codeInput, "12a3456");
    expect(codeInput).toHaveValue("123456");
    await userEvent.click(screen.getByRole("button", { name: messages.auth.verify }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/home?welcome=new"));
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/auth/verify-otp");
    expect(JSON.parse(init.body)).toEqual({ phone: "050-1234567", code: "123456" });
    expect(init.headers["Content-Type"]).toBe("application/json");
  });

  it("shows the invalid-phone message from he.json", async () => {
    fetchMock.mockReturnValueOnce(reply(422, { error: "invalid_phone" }));
    renderFlow();
    await userEvent.type(screen.getByLabelText(messages.auth.phoneLabel), "03-1234567");
    await userEvent.click(screen.getByRole("button", { name: messages.auth.sendCode }));
    expect(await screen.findByRole("alert")).toHaveTextContent(messages.auth.errors.invalid_phone);
    expect(screen.getByLabelText(messages.auth.phoneLabel)).toHaveAttribute("aria-invalid", "true");
  });

  it("shows rate-limit seconds", async () => {
    fetchMock.mockReturnValueOnce(reply(429, { error: "rate_limited", retry_after: 42 }));
    renderFlow();
    await userEvent.type(screen.getByLabelText(messages.auth.phoneLabel), "0501234567");
    await userEvent.click(screen.getByRole("button", { name: messages.auth.sendCode }));
    expect(await screen.findByRole("alert")).toHaveTextContent("42");
  });

  it("stays on the code step with an error for a wrong code", async () => {
    fetchMock
      .mockReturnValueOnce(reply(202, { status: "sent", resend_after: 0 }))
      .mockReturnValueOnce(reply(400, { error: "invalid_code" }));
    renderFlow();
    await userEvent.type(screen.getByLabelText(messages.auth.phoneLabel), "0501234567");
    await userEvent.click(screen.getByRole("button", { name: messages.auth.sendCode }));
    await userEvent.type(await screen.findByLabelText(messages.auth.codeLabel), "000000");
    await userEvent.click(screen.getByRole("button", { name: messages.auth.verify }));
    expect(await screen.findByRole("alert")).toHaveTextContent(messages.auth.errors.invalid_code);
    expect(replace).not.toHaveBeenCalled();
  });

  it("maps unknown errors and network failures to the generic message", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("network"));
    renderFlow();
    await userEvent.type(screen.getByLabelText(messages.auth.phoneLabel), "0501234567");
    await userEvent.click(screen.getByRole("button", { name: messages.auth.sendCode }));
    expect(await screen.findByRole("alert")).toHaveTextContent(messages.auth.errors.generic);
  });
});
