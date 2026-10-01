import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/AppShell";
import { FlowStepper } from "@/components/FlowStepper";
import { QuestionnaireChat } from "@/components/questionnaire/QuestionnaireChat";
import { apiFetch } from "@/lib/api-server";
import type { QuestionnaireState } from "@/lib/questionnaire";

export async function generateMetadata() {
  const t = await getTranslations("questionnaire");
  return { title: t("title") };
}

export default async function QuestionnairePage() {
  const res = await apiFetch("/api/questionnaire");
  if (res.status === 401) redirect("/login");
  if (!res.ok) throw new Error(`GET /api/questionnaire failed: ${res.status}`);
  const state = (await res.json()) as QuestionnaireState;
  const t = await getTranslations("questionnaire");
  return (
    <AppShell>
      <FlowStepper current="questionnaire" />
      <h1 className="text-2xl font-bold text-brand-900">{t("title")}</h1>
      <QuestionnaireChat initial={state} />
    </AppShell>
  );
}
