import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/AppShell";
import { FlowStepper } from "@/components/FlowStepper";
import { Card } from "@/components/ui";
import { apiFetch } from "@/lib/api-server";

type Finding = {
  rule_id: string;
  title_he: string;
  explanation_he: string;
  years: number[];
  documents: string[];
  legal_ref: string | null;
  legal_ref_verified: boolean;
};

type Estimate = { window: number[]; findings: Finding[]; is_estimate: true };

export async function generateMetadata() {
  const t = await getTranslations("estimate");
  return { title: t("title") };
}

function yearSpan(years: number[]): string {
  return [...new Set(years)].sort().join(", ");
}

/** Sprint 2 estimate: which benefits may apply, per year. No amounts until verified tables exist (ADR 0003). */
export default async function EstimatePage() {
  const res = await apiFetch("/api/estimate");
  if (res.status === 401) redirect("/login");
  if (res.status === 409) redirect("/questionnaire");
  if (!res.ok) throw new Error(`GET /api/estimate failed: ${res.status}`);
  const estimate = (await res.json()) as Estimate;
  const t = await getTranslations("estimate");
  const allYears = estimate.findings.flatMap((f) => f.years);

  return (
    <AppShell>
      <FlowStepper current="estimate" />
      {estimate.findings.length > 0 ? (
        <>
          <h1 className="text-2xl font-bold text-brand-900">{t("headline")}</h1>
          <p className="text-lg">{t("summary", { count: estimate.findings.length, years: yearSpan(allYears) })}</p>
        </>
      ) : (
        <>
          <h1 className="text-2xl font-bold text-brand-900">{t("emptyTitle")}</h1>
          <p className="text-lg">{t("emptyBody")}</p>
        </>
      )}
      <p className="rounded-[var(--radius-control)] border border-brand-100 bg-brand-50 p-4 text-ink">
        {t("noAmounts")}
      </p>

      <ul className="flex flex-col gap-4">
        {estimate.findings.map((f) => (
          <li key={f.rule_id}>
            <Card title={f.title_he}>
              <p className="mb-3 text-sm font-semibold text-ink">{t("years", { years: yearSpan(f.years) })}</p>
              <details className="group">
                <summary className="cursor-pointer font-semibold text-brand-700 underline underline-offset-4">
                  {t("why")}
                </summary>
                <div className="mt-2 flex flex-col gap-2">
                  <p>{f.explanation_he}</p>
                  <p className="text-sm">{f.legal_ref_verified && f.legal_ref ? f.legal_ref : t("legalRefPending")}</p>
                </div>
              </details>
              <h3 className="mt-3 text-sm font-bold text-ink">{t("documentsNeeded")}</h3>
              <ul className="list-inside list-disc text-sm">
                {f.documents.map((d) => (
                  <li key={d}>{t(`documents.${d}`)}</li>
                ))}
              </ul>
            </Card>
          </li>
        ))}
      </ul>

      <div className="flex flex-col items-center gap-3">
        <Link href="/timeline" className="font-semibold text-brand-700 underline underline-offset-4">
          {t("toTimeline")}
        </Link>
        <Link href="/questionnaire" className="font-semibold text-brand-700 underline underline-offset-4">
          {t("editAnswers")}
        </Link>
      </div>
    </AppShell>
  );
}
