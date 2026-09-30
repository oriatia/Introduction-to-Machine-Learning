import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/AppShell";
import { LogoutButton } from "@/components/auth/LogoutButton";
import { Card } from "@/components/ui";
import { getMe } from "@/lib/api-server";
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
  return (
    <AppShell>
      <h1 className="text-2xl font-bold text-brand-900">{t("title")}</h1>
      <p role="status" className="text-lg">
        {isNew ? t("welcomeNew") : t("welcomeBack")}
      </p>
      <p className="text-ink-muted">{t("signedInAs", { phone: ltr(me.phone_masked) })}</p>
      <Card title={t("nextStepTitle")}>{t("nextStepBody")}</Card>
      {(me.role === "advisor" || me.role === "admin") && (
        <Link href="/advisor" className="font-semibold text-brand-700 underline underline-offset-4">
          {t("advisorLink")}
        </Link>
      )}
      <LogoutButton />
    </AppShell>
  );
}
