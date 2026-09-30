import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { axeViolations } from "@/test/axe";
import { Button, Card, ChatBubble, Stepper, TextField } from ".";

describe("Button", () => {
  it("clicks and passes axe", async () => {
    const onClick = vi.fn();
    const { container } = render(<Button onClick={onClick}>שליחה</Button>);
    await userEvent.click(screen.getByRole("button", { name: "שליחה" }));
    expect(onClick).toHaveBeenCalledOnce();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("is disabled and busy while loading", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        שליחה
      </Button>,
    );
    const button = screen.getByRole("button", { name: "שליחה" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("defaults to type=button so it never submits forms by accident", () => {
    render(<Button>x</Button>);
    expect(screen.getByRole("button")).toHaveAttribute("type", "button");
  });
});

describe("Card", () => {
  it("renders a titled section with the requested heading level", async () => {
    const { container } = render(
      <Card title="2024" headingLevel={3}>
        תוכן
      </Card>,
    );
    expect(screen.getByRole("heading", { level: 3, name: "2024" })).toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("ChatBubble", () => {
  it("aligns bot to start and user to end with logical classes", async () => {
    const { container } = render(
      <div>
        <ChatBubble from="bot" senderLabel="Hazar">
          שלום
        </ChatBubble>
        <ChatBubble from="user" senderLabel="את/ה">
          היי
        </ChatBubble>
      </div>,
    );
    expect(container.querySelector('[data-from="bot"]')).toHaveClass("justify-start");
    expect(container.querySelector('[data-from="user"]')).toHaveClass("justify-end");
    expect(screen.getByText(/Hazar/)).toHaveClass("sr-only");
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("Stepper", () => {
  it("marks exactly the current step", async () => {
    const { container } = render(
      <Stepper steps={["א", "ב", "ג"]} current={1} label="שלבים" progressText="שלב 2 מתוך 3" />,
    );
    const list = screen.getByRole("list", { name: "שלבים" });
    const items = screen.getAllByRole("listitem");
    expect(list).toBeInTheDocument();
    expect(items.map((i) => i.getAttribute("data-state"))).toEqual(["done", "current", "todo"]);
    expect(items.filter((i) => i.getAttribute("aria-current") === "step")).toHaveLength(1);
    expect(screen.getByText("שלב 2 מתוך 3")).toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("TextField", () => {
  it("links label, hint and error", async () => {
    const { container } = render(<TextField label="טלפון" hint="עזרה" error="שגיאה" dir="ltr" />);
    const input = screen.getByLabelText("טלפון");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("עזרה שגיאה");
    expect(input).toHaveAttribute("dir", "ltr");
    expect(screen.getByRole("alert")).toHaveTextContent("שגיאה");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("is valid without an error", () => {
    render(<TextField label="טלפון" />);
    expect(screen.getByLabelText("טלפון")).not.toHaveAttribute("aria-invalid");
  });
});
