import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/AppShell";
import { LoginFlow } from "@/components/auth/LoginFlow";
import { getMe } from "@/lib/api-server";

export async function generateMetadata() {
  const t = await getTranslations("auth");
  return { title: t("title") };
}

export default async function LoginPage() {
  if (await getMe()) redirect("/home");
  return (
    <AppShell>
      <LoginFlow />
    </AppShell>
  );
}
