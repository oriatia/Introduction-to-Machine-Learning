"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui";
import { DOC_TYPES, EXTRACTABLE, type DocType } from "@/lib/documents";
import { prepareFile, type PreparedFile } from "@/lib/image";

const selectClass =
  "min-h-12 w-full rounded-[var(--radius-control)] border-2 border-line bg-surface px-3 text-lg text-ink focus:border-brand-700";

type ErrorKey = "unsupported_file" | "too_large" | "bad_year" | "generic";

export function UploadForm({
  initialType,
  initialYear,
  years,
}: {
  initialType: DocType;
  initialYear: number | null;
  years: number[];
}) {
  const t = useTranslations("documents");
  const router = useRouter();
  const [type, setType] = useState<DocType>(initialType);
  const [year, setYear] = useState<string>(initialYear ? String(initialYear) : "");
  const [prepared, setPrepared] = useState<PreparedFile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorKey | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const extractable = EXTRACTABLE.includes(type);

  useEffect(() => () => void (prepared?.previewUrl && URL.revokeObjectURL(prepared.previewUrl)), [prepared]);

  async function onFile(file: File | undefined) {
    setError(null);
    if (!file) return;
    try {
      setPrepared(await prepareFile(file));
    } catch {
      setError("unsupported_file");
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!prepared) return;
    setBusy(true);
    setError(null);
    const body = new FormData();
    body.append("file", prepared.blob, prepared.name);
    body.append("type", type);
    if (year) body.append("tax_year", year);
    try {
      const res = await fetch("/api/documents", {
        method: "POST",
        body,
        credentials: "same-origin",
        headers: { "X-Hazar-Upload": "1" },
      });
      const data = await res.json().catch(() => null);
      if (res.ok) {
        router.push(`/documents/${data.id}`);
        return;
      }
      const code = data?.error;
      setError(code === "unsupported_file" || code === "too_large" || code === "bad_year" ? code : "generic");
    } catch {
      setError("generic");
    }
    setBusy(false);
  }

  const canSend = prepared && !prepared.warnings.includes("tooLarge") && (extractable || year);

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      <label className="flex flex-col gap-1.5 font-semibold">
        {t("uploadPage.typeLabel")}
        <select className={selectClass} value={type} onChange={(e) => setType(e.target.value as DocType)}>
          {DOC_TYPES.map((d) => (
            <option key={d} value={d}>
              {t(`types.${d}`)}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1.5 font-semibold">
        {t("uploadPage.yearLabel")}
        <select className={selectClass} value={year} onChange={(e) => setYear(e.target.value)}>
          {extractable && <option value="">{t("uploadPage.yearAuto")}</option>}
          {!extractable && <option value="" disabled />}
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </label>

      <div className="flex flex-col gap-2">
        <label htmlFor="document-file" className="font-semibold">
          {t("uploadPage.chooseFile")}
        </label>
        <p id="document-file-hint" className="text-sm text-ink-muted">
          {t("uploadPage.chooseHint")}
        </p>
        <input
          ref={fileRef}
          id="document-file"
          type="file"
          accept="image/*,application/pdf"
          capture="environment"
          aria-describedby="document-file-hint"
          className="block w-full text-sm file:me-3 file:min-h-12 file:rounded-[var(--radius-control)] file:border-0 file:bg-brand-50 file:px-4 file:font-semibold file:text-brand-800"
          onChange={(e) => void onFile(e.target.files?.[0])}
        />
      </div>

      {prepared && (
        <div className="flex flex-col gap-3">
          {prepared.previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- local blob preview
            <img
              src={prepared.previewUrl}
              alt={t("uploadPage.previewAlt")}
              className="max-h-80 w-full rounded-[var(--radius-card)] border border-line object-contain"
            />
          ) : (
            <p>{t("uploadPage.pdfSelected", { name: prepared.name })}</p>
          )}
          {prepared.warnings.map((w) => (
            <p key={w} role="status" className="rounded-[var(--radius-control)] bg-danger-bg p-3 text-sm text-danger">
              {t(`uploadPage.warnings.${w}`)}
            </p>
          ))}
          {prepared.warnings.length > 0 && (
            <Button
              variant="secondary"
              onClick={() => {
                setPrepared(null);
                if (fileRef.current) {
                  fileRef.current.value = "";
                  fileRef.current.click();
                }
              }}
            >
              {t("uploadPage.retake")}
            </Button>
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="text-sm font-medium text-danger">
          {t(`uploadPage.errors.${error}`)}
        </p>
      )}

      <Button type="submit" fullWidth loading={busy} disabled={!canSend}>
        {busy ? t("uploadPage.sending") : t("uploadPage.send")}
      </Button>
    </form>
  );
}
