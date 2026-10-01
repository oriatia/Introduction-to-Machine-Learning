import { getTranslations } from "next-intl/server";
import { Stepper } from "@/components/ui";

const STEPS = ["questionnaire", "estimate", "documents", "sign"] as const;

export async function FlowStepper({ current }: { current: (typeof STEPS)[number] }) {
  const t = await getTranslations("flow");
  return <Stepper steps={STEPS.map((s) => t(s))} current={STEPS.indexOf(current)} label={t("label")} />;
}
