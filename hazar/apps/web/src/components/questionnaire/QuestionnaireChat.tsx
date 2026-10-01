"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, ChatBubble } from "@/components/ui";
import { getJson, postJson } from "@/lib/api-client";
import { formatAnswer, type QuestionnaireState } from "@/lib/questionnaire";
import { AnswerInput } from "./AnswerInput";

type ErrorKey = "invalid_answer" | "unknown_question" | "generic";

export function QuestionnaireChat({ initial }: { initial: QuestionnaireState }) {
  const t = useTranslations("questionnaire");
  const [state, setState] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorKey | null>(null);
  const currentRef = useRef<HTMLDivElement>(null);
  const isFirstRender = useRef(true);
  const nextId = state.next?.id ?? "done";

  // Announce each new question by moving focus to it (after the first render).
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    currentRef.current?.focus();
    currentRef.current?.scrollIntoView({ block: "nearest" });
  }, [nextId]);

  const apply = useCallback(async (request: Promise<{ ok: boolean; data?: unknown; error?: string }>) => {
    setBusy(true);
    setError(null);
    const res = await request;
    if (res.ok) {
      setState(res.data as QuestionnaireState);
    } else {
      const key: ErrorKey =
        res.error === "invalid_answer" || res.error === "unknown_question" ? res.error : "generic";
      setError(key);
      if (key === "unknown_question") {
        const fresh = await getJson<QuestionnaireState>("/api/questionnaire");
        if (fresh.ok) setState(fresh.data);
      }
    }
    setBusy(false);
  }, []);

  const answer = (value: unknown) =>
    apply(postJson("/api/questionnaire/answers", { question_id: state.next?.id, value }));
  const undo = () => apply(postJson("/api/questionnaire/undo", {}));

  return (
    <div className="flex flex-col gap-4">
      <ol className="flex flex-col gap-3" aria-label={t("title")}>
        <li>
          <ChatBubble from="bot" senderLabel={t("botLabel")}>
            {t("intro")}
          </ChatBubble>
        </li>
        {state.answered.map((a) => (
          <li key={a.id} className="flex flex-col gap-2">
            <ChatBubble from="bot" senderLabel={t("botLabel")}>
              {t(`questions.${a.id}`)}
            </ChatBubble>
            <ChatBubble from="user" senderLabel={t("userLabel")}>
              {formatAnswer(t, a)}
            </ChatBubble>
          </li>
        ))}
      </ol>

      <div ref={currentRef} tabIndex={-1} className="flex flex-col gap-3 outline-none" aria-live="polite">
        {state.next ? (
          <>
            <ChatBubble from="bot" senderLabel={t("botLabel")}>
              <span className="font-semibold">{t(`questions.${state.next.id}`)}</span>
            </ChatBubble>
            <AnswerInput key={state.next.id} question={state.next} busy={busy} onAnswer={answer} />
          </>
        ) : (
          <>
            <ChatBubble from="bot" senderLabel={t("botLabel")}>
              <span className="block font-semibold">{t("doneTitle")}</span>
              {t("doneBody")}
            </ChatBubble>
            <Link
              href="/estimate"
              className="inline-flex min-h-12 items-center justify-center rounded-[var(--radius-control)] bg-brand-700 px-6 text-lg font-semibold text-white hover:bg-brand-800"
            >
              {t("toEstimate")}
            </Link>
            <Link href="/timeline" className="text-center font-medium text-brand-700 underline underline-offset-4">
              {t("toTimeline")}
            </Link>
          </>
        )}
        {error && (
          <p role="alert" className="text-sm font-medium text-danger">
            {t(`errors.${error}`)}
          </p>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 text-sm text-ink-muted">
        <span>{t("progress", { answered: state.answered.length })}</span>
        {state.answered.length > 0 && (
          <Button variant="ghost" disabled={busy} onClick={undo}>
            {t("undo")}
          </Button>
        )}
      </div>
    </div>
  );
}
