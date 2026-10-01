import type { ReactNode } from "react";
import { cn } from "./cn";

type Props = {
  from: "bot" | "user";
  /** Who is speaking, announced to screen readers (e.g. "Hazar" / "את/ה"). */
  senderLabel: string;
  children: ReactNode;
};

/** In RTL the bot sits at the start (right) and the user at the end (left), via logical alignment. */
export function ChatBubble({ from, senderLabel, children }: Props) {
  const isBot = from === "bot";
  const spokenSender = `${senderLabel}: `;
  return (
    <div className={cn("flex w-full", isBot ? "justify-start" : "justify-end")} data-from={from}>
      <div
        className={cn(
          "max-w-[85%] rounded-[var(--radius-bubble)] px-4 py-3 text-base leading-relaxed",
          isBot ? "rounded-ss-sm bg-surface text-ink shadow-sm" : "rounded-se-sm bg-brand-700 text-white",
        )}
      >
        <span className="sr-only">{spokenSender}</span>
        {children}
      </div>
    </div>
  );
}
