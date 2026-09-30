import Link from "next/link";
import type { ReactNode } from "react";
import { getTranslations } from "next-intl/server";

export async function AppShell({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  const t = await getTranslations("app");
  return (
    <>
      <header className="border-b border-line bg-surface">
        <div className={`mx-auto flex h-14 items-center px-5 ${wide ? "max-w-5xl" : "max-w-md"}`}>
          <Link href="/" className="text-xl font-bold text-brand-800">
            {t("name")}
          </Link>
        </div>
      </header>
      <main id="main" className={`mx-auto flex w-full flex-1 flex-col gap-6 px-5 py-8 ${wide ? "max-w-5xl" : "max-w-md"}`}>
        {children}
      </main>
    </>
  );
}
