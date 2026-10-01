import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/AppShell";
import { ReviewDocument } from "@/components/documents/ReviewDocument";
import { apiFetch } from "@/lib/api-server";
import type { ChecklistItem, DocumentDetail } from "@/lib/documents";

export async function generateMetadata() {
  const t = await getTranslations("documents");
  return { title: t("review.title") };
}

export default async function DocumentPage({ params }: PageProps<"/documents/[id]">) {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound();
  const [docRes, checklistRes] = await Promise.all([apiFetch(`/api/documents/${id}`), apiFetch("/api/documents/checklist")]);
  if (docRes.status === 401) redirect("/login");
  if (docRes.status === 404) notFound();
  if (!docRes.ok || !checklistRes.ok) throw new Error("document fetch failed");
  const doc = (await docRes.json()) as DocumentDetail;
  const years = [...new Set(((await checklistRes.json()) as ChecklistItem[]).filter((i) => i.doc_type === "form_106").map((i) => i.year))].sort(
    (a, b) => b - a,
  );
  const t = await getTranslations("documents");
  return (
    <AppShell>
      <h1 className="text-2xl font-bold text-brand-900">{t("review.title")}</h1>
      <ReviewDocument initial={doc} years={years} />
    </AppShell>
  );
}
