import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui";
import { apiFetch } from "@/lib/api-server";

export async function generateMetadata() {
  const t = await getTranslations("advisor");
  return { title: t("title") };
}

/** Advisor back office (desktop layout). The API is the authority on the role check. */
export default async function AdvisorPage() {
  const res = await apiFetch("/api/advisor/overview");
  if (res.status === 401) redirect("/login");
  const t = await getTranslations("advisor");

  if (res.status === 403) {
    return (
      <AppShell>
        <h1 className="text-2xl font-bold text-brand-900">{t("forbiddenTitle")}</h1>
        <p>{t("forbiddenBody")}</p>
        <Link href="/home" className="font-semibold text-brand-700 underline underline-offset-4">
          {t("backHome")}
        </Link>
      </AppShell>
    );
  }
  if (!res.ok) throw new Error(`GET /api/advisor/overview failed: ${res.status}`);
  const data = (await res.json()) as { queue: unknown[] };

  return (
    <AppShell wide>
      <h1 className="text-2xl font-bold text-brand-900">{t("title")}</h1>
      <Card title={t("queueTitle")}>{data.queue.length === 0 ? t("empty") : null}</Card>
    </AppShell>
  );
}
