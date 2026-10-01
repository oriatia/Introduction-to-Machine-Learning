"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Button, TextField } from "@/components/ui";
import { getJson, postJson } from "@/lib/api-client";
import { EXTRACTABLE, fieldsToCheck, initialValues, type DocumentDetail } from "@/lib/documents";

const POLL_MS = 1500;

export function ReviewDocument({ initial, years }: { initial: DocumentDetail; years: number[] }) {
  const t = useTranslations("documents");
  const router = useRouter();
  const [doc, setDoc] = useState(initial);
  const [values, setValues] = useState(() => initialValues(initial));
  const [year, setYear] = useState(initial.tax_year ? String(initial.tax_year) : "");
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState(initial.status !== "confirmed");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const extractable = EXTRACTABLE.includes(doc.type);

  const refresh = useCallback(async () => {
    const res = await getJson<DocumentDetail>(`/api/documents/${doc.id}`);
    if (res.ok) {
      setDoc(res.data);
      setValues(initialValues(res.data));
      if (res.data.tax_year) setYear(String(res.data.tax_year));
    }
  }, [doc.id]);

  useEffect(() => {
    if (doc.status !== "extracting") return;
    const timer = setTimeout(() => void refresh(), POLL_MS);
    return () => clearTimeout(timer);
  }, [doc.status, refresh]);

  const pending = fieldsToCheck(doc).filter((f) => !checked.has(f));
  const allEmpty = doc.fields.length > 0 && doc.fields.every((f) => f.value === null);

  async function confirm(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = extractable ? { fields: values } : { tax_year: Number(year) };
    const res = await postJson<DocumentDetail>(`/api/documents/${doc.id}/confirm`, body);
    setBusy(false);
    if (res.ok) {
      setDoc(res.data);
      setEditing(false);
      return;
    }
    if (res.error.startsWith("invalid_field:")) {
      const field = res.error.split(":")[1];
      setError(t("review.errors.invalid_field", { field: t(`review.fields.${field}`) }));
    } else {
      setError(t(res.error === "not_ready" ? "review.errors.not_ready" : "review.errors.generic"));
    }
  }

  async function retry() {
    const res = await postJson<DocumentDetail>(`/api/documents/${doc.id}/retry`, {});
    if (res.ok) setDoc({ ...doc, status: "extracting", error: null });
  }

  async function remove() {
    if (!window.confirm(t("review.deleteConfirm"))) return;
    const res = await postJson(`/api/documents/${doc.id}/delete`, {});
    if (res.ok) {
      router.replace("/documents");
      router.refresh();
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <p className="text-ink-muted">
        {t(`types.${doc.type}`)}
        {doc.tax_year ? ` · ${doc.tax_year}` : ""}
      </p>
      {doc.file_url && (
        <a href={doc.file_url} className="font-semibold text-brand-700 underline underline-offset-4">
          {t("review.openFile")}
        </a>
      )}

      {doc.status === "extracting" && (
        <p role="status" aria-live="polite" className="flex items-center gap-2">
          <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-brand-700 border-t-transparent" />
          {t("review.extracting")}
        </p>
      )}

      {doc.status === "failed" && (
        <div role="alert" className="flex flex-col gap-3">
          <p>{t("review.failed")}</p>
          <Button variant="secondary" onClick={() => void retry()}>
            {t("review.retry")}
          </Button>
        </div>
      )}

      {doc.status === "confirmed" && !editing && (
        <div className="flex flex-col gap-3">
          <p role="status" className="font-semibold text-brand-800">
            {t("review.confirmed")}
          </p>
          <dl className="grid grid-cols-1 gap-2">
            {doc.fields.map((f) => (
              <div key={f.name} className="flex justify-between gap-4 border-b border-line py-1">
                <dt className="text-ink-muted">{t(`review.fields.${f.name}`)}</dt>
                <dd dir="ltr" className="font-semibold">
                  {doc.confirmed?.[f.name] ?? "—"}
                </dd>
              </div>
            ))}
          </dl>
          <Button variant="secondary" onClick={() => setEditing(true)}>
            {t("review.edit")}
          </Button>
        </div>
      )}

      {(doc.status === "needs_review" || (doc.status === "confirmed" && editing) || (doc.status === "failed" && extractable)) && (
        <form onSubmit={confirm} className="flex flex-col gap-4" noValidate>
          <p>{allEmpty && doc.status !== "confirmed" ? t("review.manualIntro") : t("review.intro")}</p>
          {extractable ? (
            doc.fields.map((f) => {
              const attention = fieldsToCheck(doc).includes(f.name);
              return (
                <div
                  key={f.name}
                  className={attention ? "flex flex-col gap-2 rounded-[var(--radius-card)] border-2 border-danger/40 bg-danger-bg p-3" : ""}
                >
                  <TextField
                    label={t(`review.fields.${f.name}`)}
                    hint={attention ? t("review.needsAttention") : undefined}
                    value={values[f.name] ?? ""}
                    dir={f.kind === "text" ? "auto" : "ltr"}
                    inputMode={f.kind === "text" ? "text" : f.kind === "decimal" ? "decimal" : "numeric"}
                    onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
                  />
                  {attention && (
                    <label className="flex min-h-12 items-center gap-2 font-medium">
                      <input
                        type="checkbox"
                        className="size-5 accent-brand-700"
                        checked={checked.has(f.name)}
                        onChange={(e) => {
                          const next = new Set(checked);
                          if (e.target.checked) next.add(f.name);
                          else next.delete(f.name);
                          setChecked(next);
                        }}
                      />
                      {t("review.checked")}
                    </label>
                  )}
                </div>
              );
            })
          ) : (
            <label className="flex flex-col gap-1.5 font-semibold">
              {t("uploadPage.yearLabel")}
              <select
                className="min-h-12 rounded-[var(--radius-control)] border-2 border-line bg-surface px-3 text-lg"
                value={year}
                onChange={(e) => setYear(e.target.value)}
              >
                <option value="" disabled />
                {years.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </label>
          )}
          {error && (
            <p role="alert" className="text-sm font-medium text-danger">
              {error}
            </p>
          )}
          <Button type="submit" fullWidth loading={busy} disabled={extractable ? pending.length > 0 : !year}>
            {t("review.confirm")}
          </Button>
        </form>
      )}

      <div className="flex flex-col items-center gap-3">
        <Link href="/documents" className="font-semibold text-brand-700 underline underline-offset-4">
          {t("review.backToDocuments")}
        </Link>
        <Button variant="ghost" onClick={() => void remove()}>
          {t("review.delete")}
        </Button>
      </div>
    </div>
  );
}
