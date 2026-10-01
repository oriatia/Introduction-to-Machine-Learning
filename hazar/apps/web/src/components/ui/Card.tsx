import type { ReactNode } from "react";
import { cn } from "./cn";

type Props = {
  title?: ReactNode;
  headingLevel?: 2 | 3 | 4;
  children: ReactNode;
  className?: string;
};

export function Card({ title, headingLevel = 2, children, className }: Props) {
  const Heading = `h${headingLevel}` as const;
  return (
    <section
      className={cn(
        "rounded-[var(--radius-card)] border border-line bg-surface p-5 shadow-sm",
        className,
      )}
    >
      {title && <Heading className="mb-2 text-lg font-bold text-ink">{title}</Heading>}
      <div className="text-ink-muted">{children}</div>
    </section>
  );
}
