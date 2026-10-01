"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button, Stepper, TextField } from "@/components/ui";
import { postJson } from "@/lib/api-client";
import { ltr } from "@/lib/api-types";

type Step = "phone" | "code";
type VerifyResponse = { is_new: boolean };
const ERROR_KEYS = ["invalid_phone", "invalid_code", "too_many_attempts", "rate_limited", "generic"] as const;
type ErrorKey = (typeof ERROR_KEYS)[number];

function toErrorKey(code: string): ErrorKey {
  return (ERROR_KEYS as readonly string[]).includes(code) ? (code as ErrorKey) : "generic";
}

export function LoginFlow() {
  const t = useTranslations("auth");
  const router = useRouter();
  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<{ key: ErrorKey; seconds?: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [resendIn, setResendIn] = useState(0);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const isFirstRender = useRef(true);

  // Move focus to the new step's heading right after it renders, so screen readers announce the change.
  // Done in an effect (not a later animation frame) so it can never steal focus from a field the user
  // has already started typing in.
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    headingRef.current?.focus();
  }, [step]);

  useEffect(() => {
    if (resendIn <= 0) return;
    const timer = setTimeout(() => setResendIn((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendIn]);

  function goTo(next: Step) {
    setStep(next);
    setError(null);
  }

  async function requestCode(): Promise<boolean> {
    setLoading(true);
    setError(null);
    const res = await postJson<{ resend_after: number }>("/api/auth/request-otp", { phone });
    setLoading(false);
    if (res.ok) {
      setResendIn(res.data.resend_after);
      return true;
    }
    setError({ key: toErrorKey(res.error), seconds: res.retryAfter });
    return false;
  }

  async function onPhoneSubmit(e: FormEvent) {
    e.preventDefault();
    if (await requestCode()) {
      setCode("");
      goTo("code");
    }
  }

  async function onCodeSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const res = await postJson<VerifyResponse>("/api/auth/verify-otp", { phone, code });
    if (res.ok) {
      router.replace(res.data.is_new ? "/home?welcome=new" : "/home");
      router.refresh();
      return;
    }
    setLoading(false);
    setError({ key: toErrorKey(res.error), seconds: res.retryAfter });
  }

  const errorText = error ? t(`errors.${error.key}`, { seconds: error.seconds ?? 0 }) : undefined;
  const steps = [t("steps.phone"), t("steps.code")];
  const current = step === "phone" ? 0 : 1;

  return (
    <div className="flex flex-col gap-6">
      <Stepper
        steps={steps}
        current={current}
        label={t("stepper")}
        progressText={t("stepOf", { current: current + 1, total: steps.length })}
      />

      {step === "phone" ? (
        <form onSubmit={onPhoneSubmit} className="flex flex-col gap-5" noValidate>
          <h1 ref={headingRef} tabIndex={-1} className="text-2xl font-bold text-brand-900">
            {t("phoneTitle")}
          </h1>
          <TextField
            label={t("phoneLabel")}
            hint={t("phoneHint")}
            error={errorText}
            type="tel"
            inputMode="tel"
            autoComplete="tel-national"
            dir="ltr"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            required
          />
          <Button type="submit" fullWidth loading={loading} disabled={!phone.trim()}>
            {t("sendCode")}
          </Button>
        </form>
      ) : (
        <form onSubmit={onCodeSubmit} className="flex flex-col gap-5" noValidate>
          <h1 ref={headingRef} tabIndex={-1} className="text-2xl font-bold text-brand-900">
            {t("codeTitle")}
          </h1>
          <TextField
            label={t("codeLabel")}
            hint={t("codeHint", { phone: ltr(phone) })}
            error={errorText}
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="\d*"
            maxLength={8}
            dir="ltr"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            required
          />
          <Button type="submit" fullWidth loading={loading} disabled={code.length < 4}>
            {t("verify")}
          </Button>
          <div className="flex flex-col items-center gap-2">
            <Button variant="ghost" disabled={resendIn > 0 || loading} onClick={() => void requestCode()}>
              {t("resend")}
            </Button>
            {resendIn > 0 && (
              <p className="text-sm text-ink-muted" aria-live="polite">
                {t("resendIn", { seconds: resendIn })}
              </p>
            )}
            <Button variant="ghost" onClick={() => goTo("phone")}>
              {t("changePhone")}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
