import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/AppShell";
import { FlowStepper } from "@/components/FlowStepper";
import { Card } from "@/components/ui";
import { apiFetch } from "@/lib/api-server";
import type { ChecklistItem, DocumentDetail } from "@/lib/documents";

export async function generateMetadata() {
  const t = await getTranslations("documents");
  return { title: t("title") };
}

const STATUS_STYLE: Record<string, string> = {
  missing: "bg-canvas text-ink-muted",
  uploaded: "bg-brand-50 text-brand-800",
  confirmed: "bg-brand-700 text-white",
  extracting: "bg-brand-50 text-brand-800",
  needs_review: "bg-brand-50 text-brand-800",
  failed: "bg-danger-bg text-danger",
};

export default async function DocumentsPage() {
  const [checklistRes, docsRes] = await Promise.all([apiFetch("/api/documents/checklist"), apiFetch("/api/documents")]);
  if (checklistRes.status === 401) redirect("/login");
  if (!checklistRes.ok || !docsRes.ok) throw new Error("documents fetch failed");
  const checklist = (await checklistRes.json()) as ChecklistItem[];
  const docs = (await docsRes.json()) as DocumentDetail[];
  const t = await getTranslations("documents");
  const years = [...new Set(checklist.map((i) => i.year))].sort((a, b) => b - a);

  return (
    <AppShell>
      <FlowStepper current="documents" />
      <h1 className="text-2xl font-bold text-brand-900">{t("title")}</h1>
      <p className="text-ink-muted">{t("intro")}</p>

      <section aria-labelledby="checklist-title" className="flex flex-col gap-3">
        <h2 id="checklist-title" className="text-lg font-bold">
          {t("checklistTitle")}
        </h2>
        <p className="text-sm text-ink-muted">{t("checklistIntro")}</p>
        {years.map((year) => (
          <Card key={year} title={t("year", { year })} headingLevel={3}>
            <ul className="flex flex-col gap-2">
              {checklist
                .filter((i) => i.year === year)
                .map((i) => (
                  <li key={`${i.doc_type}-${i.year}`} className="flex items-center justify-between gap-3">
                    <span className="text-ink">{t(`types.${i.doc_type}`)}</span>
                    <span className="flex items-center gap-2">
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_STYLE[i.status]}`}>
                        {t(`status.${i.status}`)}
                      </span>
                      {i.status !== "confirmed" && (
                        <Link
                          href={`/documents/upload?type=${i.doc_type}&year=${i.year}`}
                          className="font-semibold text-brand-700 underline underline-offset-4"
                          aria-label={`${t("upload")} ${t(`types.${i.doc_type}`)} ${i.year}`}
                        >
                          {t("upload")}
                        </Link>
                      )}
                    </span>
                  </li>
                ))}
            </ul>
          </Card>
        ))}
      </section>

      <section aria-labelledby="uploaded-title" className="flex flex-col gap-3">
        <h2 id="uploaded-title" className="text-lg font-bold">
          {t("uploadedTitle")}
        </h2>
        {docs.length === 0 ? (
          <p>{t("noDocuments")}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {docs.map((d) => (
              <li key={d.id}>
                <Link
                  href={`/documents/${d.id}`}
                  className="flex items-center justify-between gap-3 rounded-[var(--radius-control)] border border-line bg-surface p-3 hover:border-brand-700"
                >
                  <span>
                    {t(`types.${d.type}`)}
                    {d.tax_year ? ` · ${d.tax_year}` : ""}
                  </span>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_STYLE[d.status]}`}>
                    {t(`status.${d.status}`)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        <Link
          href="/documents/upload"
          className="inline-flex min-h-12 items-center justify-center rounded-[var(--radius-control)] bg-brand-700 px-6 text-lg font-semibold text-white hover:bg-brand-800"
        >
          {t("upload")}
        </Link>
      </section>
    </AppShell>
  );
}
