import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/AppShell";
import { UploadForm } from "@/components/documents/UploadForm";
import { apiFetch } from "@/lib/api-server";
import { DOC_TYPES, type ChecklistItem, type DocType } from "@/lib/documents";

export async function generateMetadata() {
  const t = await getTranslations("documents");
  return { title: t("uploadPage.title") };
}

export default async function UploadPage({ searchParams }: PageProps<"/documents/upload">) {
  const res = await apiFetch("/api/documents/checklist");
  if (res.status === 401) redirect("/login");
  if (!res.ok) throw new Error(`GET /api/documents/checklist failed: ${res.status}`);
  // The refund window comes from the API (Form 106 is listed for every window year).
  const years = [...new Set(((await res.json()) as ChecklistItem[]).filter((i) => i.doc_type === "form_106").map((i) => i.year))].sort(
    (a, b) => b - a,
  );
  const params = await searchParams;
  const type = DOC_TYPES.includes(params.type as DocType) ? (params.type as DocType) : "form_106";
  const year = Number(params.year);
  const t = await getTranslations("documents");
  return (
    <AppShell>
      <h1 className="text-2xl font-bold text-brand-900">{t("uploadPage.title")}</h1>
      <UploadForm initialType={type} initialYear={years.includes(year) ? year : null} years={years} />
    </AppShell>
  );
}
