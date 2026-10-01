import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/AppShell";
import { LogoutButton } from "@/components/auth/LogoutButton";
import { apiFetch, getMe } from "@/lib/api-server";
import { ltr } from "@/lib/api-types";

export async function generateMetadata() {
  const t = await getTranslations("home");
  return { title: t("title") };
}

export default async function HomePage({ searchParams }: PageProps<"/home">) {
  const me = await getMe();
  if (!me) redirect("/login");
  const t = await getTranslations("home");
  const isNew = (await searchParams).welcome === "new";
  const qRes = await apiFetch("/api/questionnaire");
  const q = qRes.ok ? ((await qRes.json()) as { complete: boolean; answered: unknown[] }) : null;
  const cta = q?.complete
    ? { href: "/estimate", label: t("viewEstimate") }
    : { href: "/questionnaire", label: q?.answered.length ? t("continueQuestionnaire") : t("startQuestionnaire") };
  return (
    <AppShell>
      <h1 className="text-2xl font-bold text-brand-900">{t("title")}</h1>
      <p role="status" className="text-lg">
        {isNew ? t("welcomeNew") : t("welcomeBack")}
      </p>
      <p className="text-ink-muted">{t("signedInAs", { phone: ltr(me.phone_masked) })}</p>
      <Link
        href={cta.href}
        className="inline-flex min-h-12 items-center justify-center rounded-[var(--radius-control)] bg-brand-700 px-6 text-lg font-semibold text-white hover:bg-brand-800"
      >
        {cta.label}
      </Link>
      <Link href="/documents" className="text-center font-semibold text-brand-700 underline underline-offset-4">
        {t("viewDocuments")}
      </Link>
      {q?.complete && (
        <Link href="/timeline" className="text-center font-semibold text-brand-700 underline underline-offset-4">
          {t("viewTimeline")}
        </Link>
      )}
      {(me.role === "advisor" || me.role === "admin") && (
        <Link href="/advisor" className="font-semibold text-brand-700 underline underline-offset-4">
          {t("advisorLink")}
        </Link>
      )}
      <LogoutButton />
    </AppShell>
  );
}
