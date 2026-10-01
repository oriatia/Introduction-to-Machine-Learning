"use client";

import { useId, type InputHTMLAttributes } from "react";
import { cn } from "./cn";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "id"> & {
  label: string;
  hint?: string;
  error?: string;
};

/** Label, hint and error are wired with aria-describedby / aria-invalid. Pass dir="ltr" for numbers. */
export function TextField({ label, hint, error, className, ...input }: Props) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint && hintId, error && errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="font-semibold text-ink">
        {label}
      </label>
      {hint && (
        <p id={hintId} className="text-sm text-ink-muted">
          {hint}
        </p>
      )}
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cn(
          "min-h-12 w-full rounded-[var(--radius-control)] border-2 bg-surface px-4 text-lg text-ink",
          error ? "border-danger" : "border-line focus:border-brand-700",
          className,
        )}
        {...input}
      />
      {error && (
        <p id={errorId} role="alert" className="text-sm font-medium text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
