import Link from "next/link";
import { getTranslations } from "next-intl/server";

export default async function LandingPage() {
  const t = await getTranslations("landing");
  return (
    <main id="main" className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6 px-5 py-10">
      <h1 className="text-3xl font-bold leading-tight text-brand-900">{t("title")}</h1>
      <p className="text-lg text-ink-muted">{t("subtitle")}</p>
      <Link
        href="/login"
        className="inline-flex min-h-12 items-center justify-center rounded-[var(--radius-control)] bg-brand-700 px-6 text-lg font-semibold text-white hover:bg-brand-800"
      >
        {t("cta")}
      </Link>
      <Link href="/login" className="text-center font-medium text-brand-700 underline underline-offset-4">
        {t("login")}
      </Link>
    </main>
  );
}
