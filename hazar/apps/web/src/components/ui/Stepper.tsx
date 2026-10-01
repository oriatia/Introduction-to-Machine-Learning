import { cn } from "./cn";

type Props = {
  steps: string[];
  /** Zero-based index of the current step. */
  current: number;
  /** Accessible name of the list, e.g. "שלבי התהליך". */
  label: string;
  /** Visible progress text, e.g. "שלב 1 מתוך 3", already translated. */
  progressText?: string;
};

export function Stepper({ steps, current, label, progressText }: Props) {
  return (
    <div>
      <ol aria-label={label} className="flex items-center gap-2">
        {steps.map((step, i) => {
          const state = i < current ? "done" : i === current ? "current" : "todo";
          return (
            <li
              key={step}
              aria-current={state === "current" ? "step" : undefined}
              data-state={state}
              className="flex flex-1 flex-col items-center gap-1 text-center"
            >
              <span
                aria-hidden="true"
                className={cn(
                  "h-1.5 w-full rounded-full",
                  state === "todo" ? "bg-line" : "bg-brand-700",
                )}
              />
              <span
                className={cn(
                  "text-sm",
                  state === "current" ? "font-bold text-ink" : "text-ink-muted",
                )}
              >
                {step}
              </span>
            </li>
          );
        })}
      </ol>
      {progressText && <p className="mt-2 text-sm text-ink-muted">{progressText}</p>}
    </div>
  );
}
