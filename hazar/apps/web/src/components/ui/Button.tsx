import type { ButtonHTMLAttributes } from "react";
import { cn } from "./cn";

type Variant = "primary" | "secondary" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand-700 text-white hover:bg-brand-800 disabled:bg-brand-700/60",
  secondary: "border-2 border-brand-700 bg-surface text-brand-800 hover:bg-brand-50 disabled:opacity-60",
  ghost: "bg-transparent text-brand-800 underline-offset-4 hover:underline disabled:opacity-60",
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  loading?: boolean;
  fullWidth?: boolean;
};

/** Touch target is at least 48px high. While `loading`, the button is disabled and announces aria-busy. */
export function Button({
  variant = "primary",
  loading = false,
  fullWidth = false,
  disabled,
  className,
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex min-h-12 items-center justify-center gap-2 rounded-[var(--radius-control)] px-6 text-base font-semibold transition-colors disabled:cursor-not-allowed",
        VARIANTS[variant],
        fullWidth && "w-full",
        className,
      )}
      {...rest}
    >
      {loading && (
        <span
          aria-hidden="true"
          className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
        />
      )}
      {children}
    </button>
  );
}
