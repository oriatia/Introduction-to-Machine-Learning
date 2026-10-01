import { getTranslations } from "next-intl/server";
import { Button, Card, ChatBubble, Stepper, TextField } from "@/components/ui";

export default async function DesignPage() {
  const t = await getTranslations("design");
  const steps = [t("stepQuestionnaire"), t("stepDocuments"), t("stepEstimate"), t("stepSign")];
  return (
    <main id="main" className="mx-auto flex w-full max-w-md flex-col gap-8 px-5 py-8">
      <h1 className="text-2xl font-bold text-brand-900">{t("title")}</h1>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-bold">{t("buttons")}</h2>
        <Button fullWidth>{t("primary")}</Button>
        <Button fullWidth variant="secondary">
          {t("secondary")}
        </Button>
        <Button variant="ghost">{t("ghost")}</Button>
        <Button fullWidth loading>
          {t("loadingButton")}
        </Button>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-bold">{t("cards")}</h2>
        <Card title={t("cardTitle")} headingLevel={3}>
          {t("cardBody")}
        </Card>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-bold">{t("chat")}</h2>
        <ChatBubble from="bot" senderLabel={t("botLabel")}>
          {t("botMessage")}
        </ChatBubble>
        <ChatBubble from="user" senderLabel={t("userLabel")}>
          {t("userMessage")}
        </ChatBubble>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-bold">{t("stepper")}</h2>
        <Stepper steps={steps} current={1} label={t("stepperLabel")} />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-bold">{t("fields")}</h2>
        <TextField label={t("fieldLabel")} hint={t("fieldHint")} />
        <TextField label={t("fieldLabel")} error={t("fieldError")} />
      </section>
    </main>
  );
}
