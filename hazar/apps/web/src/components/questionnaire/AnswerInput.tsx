"use client";

import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui";
import type { Locality, Question } from "@/lib/questionnaire";

type Props = {
  question: Question;
  busy: boolean;
  onAnswer: (value: unknown) => void;
};

const inputClass =
  "min-h-12 w-full rounded-[var(--radius-control)] border-2 border-line bg-surface px-3 text-lg text-ink focus:border-brand-700";

/** One widget per answer kind. Labels are tied to inputs; numbers and dates are entered LTR. */
export function AnswerInput({ question, busy, onAnswer }: Props) {
  const t = useTranslations("questionnaire");
  const label = t(`questions.${question.id}`);

  switch (question.kind) {
    case "yes_no":
      return (
        <div role="group" aria-label={label} className="flex gap-3">
          <Button fullWidth disabled={busy} onClick={() => onAnswer(true)}>
            {t("yes")}
          </Button>
          <Button fullWidth variant="secondary" disabled={busy} onClick={() => onAnswer(false)}>
            {t("no")}
          </Button>
        </div>
      );
    case "choice":
      return (
        <div role="group" aria-label={label} className="flex flex-wrap gap-2">
          {question.options.map((opt) => (
            <Button key={opt} variant="secondary" disabled={busy} onClick={() => onAnswer(opt)}>
              {t(`options.${question.id}.${opt}`)}
            </Button>
          ))}
        </div>
      );
    case "date":
      return <DateList single label={label} busy={busy} onAnswer={(v) => onAnswer(v[0])} />;
    case "dates":
      return <DateList label={label} busy={busy} onAnswer={onAnswer} />;
    case "years":
      return <YearList label={label} busy={busy} onAnswer={onAnswer} />;
    case "window_years":
      return <WindowYears label={label} years={question.window} busy={busy} onAnswer={onAnswer} />;
    case "localities":
      return <Localities busy={busy} onAnswer={onAnswer} />;
  }
}

function useRows<T>(initial: T) {
  const [rows, setRows] = useState<T[]>([initial]);
  return {
    rows,
    set: (i: number, v: T) => setRows((r) => r.map((x, j) => (j === i ? v : x))),
    add: () => setRows((r) => [...r, initial]),
    remove: (i: number) => setRows((r) => r.filter((_, j) => j !== i)),
  };
}

function RowControls({ canRemove, onRemove }: { canRemove: boolean; onRemove: () => void }) {
  const t = useTranslations("questionnaire");
  return canRemove ? (
    <Button variant="ghost" onClick={onRemove}>
      {t("remove")}
    </Button>
  ) : null;
}

function DateList({
  label,
  busy,
  single = false,
  onAnswer,
}: {
  label: string;
  busy: boolean;
  single?: boolean;
  onAnswer: (v: string[]) => void;
}) {
  const t = useTranslations("questionnaire");
  const { rows, set, add, remove } = useRows("");
  const today = new Date().toISOString().slice(0, 10);
  const valid = rows.every((r) => r !== "");
  function submit(e: FormEvent) {
    e.preventDefault();
    if (valid) onAnswer(rows);
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-3" aria-label={label}>
      {rows.map((value, i) => (
        <div key={i} className="flex items-center gap-2">
          <input
            type="date"
            dir="ltr"
            max={today}
            aria-label={`${t("dateLabel")} ${i + 1}`}
            className={inputClass}
            value={value}
            onChange={(e) => set(i, e.target.value)}
            required
          />
          <RowControls canRemove={rows.length > 1} onRemove={() => remove(i)} />
        </div>
      ))}
      {!single && (
        <Button variant="ghost" onClick={add}>
          {t("addAnother")}
        </Button>
      )}
      <Button type="submit" fullWidth loading={busy} disabled={!valid}>
        {t("submit")}
      </Button>
    </form>
  );
}

function YearList({ label, busy, onAnswer }: { label: string; busy: boolean; onAnswer: (v: number[]) => void }) {
  const t = useTranslations("questionnaire");
  const { rows, set, add, remove } = useRows("");
  const thisYear = new Date().getFullYear();
  const years = rows.map(Number);
  const valid = years.every((y) => Number.isInteger(y) && y >= 1940 && y <= thisYear);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) onAnswer(years);
      }}
      className="flex flex-col gap-3"
      aria-label={label}
    >
      {rows.map((value, i) => (
        <div key={i} className="flex items-center gap-2">
          <input
            inputMode="numeric"
            dir="ltr"
            maxLength={4}
            aria-label={`${t("yearLabel")} ${i + 1}`}
            className={inputClass}
            value={value}
            onChange={(e) => set(i, e.target.value.replace(/\D/g, ""))}
            required
          />
          <RowControls canRemove={rows.length > 1} onRemove={() => remove(i)} />
        </div>
      ))}
      <Button variant="ghost" onClick={add}>
        {t("addAnother")}
      </Button>
      <Button type="submit" fullWidth loading={busy} disabled={!valid}>
        {t("submit")}
      </Button>
    </form>
  );
}

function WindowYears({
  label,
  years,
  busy,
  onAnswer,
}: {
  label: string;
  years: number[];
  busy: boolean;
  onAnswer: (v: number[]) => void;
}) {
  const t = useTranslations("questionnaire");
  const [selected, setSelected] = useState<number[]>([]);
  const toggle = (y: number) =>
    setSelected((s) => (s.includes(y) ? s.filter((x) => x !== y) : [...s, y].sort()));
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (selected.length) onAnswer(selected);
      }}
      className="flex flex-col gap-3"
    >
      <fieldset className="flex flex-wrap gap-2">
        <legend className="sr-only">{label}</legend>
        {years.map((y) => (
          <label
            key={y}
            className="flex min-h-12 cursor-pointer items-center gap-2 rounded-[var(--radius-control)] border-2 border-line bg-surface px-4 has-[:checked]:border-brand-700 has-[:checked]:bg-brand-50"
          >
            <input type="checkbox" className="size-5 accent-brand-700" checked={selected.includes(y)} onChange={() => toggle(y)} />
            <span dir="ltr">{y}</span>
          </label>
        ))}
      </fieldset>
      <Button type="submit" fullWidth loading={busy} disabled={!selected.length}>
        {t("submit")}
      </Button>
    </form>
  );
}

type LocalityRow = { name: string; from: string; to: string };

function Localities({ busy, onAnswer }: { busy: boolean; onAnswer: (v: Locality[]) => void }) {
  const t = useTranslations("questionnaire");
  const { rows, set, add, remove } = useRows<LocalityRow>({ name: "", from: "", to: "" });
  const rowLegend = (i: number) => `${t("localityName")} ${i + 1}`;
  const thisYear = new Date().getFullYear();
  const parsed = rows.map((r) => ({
    name: r.name.trim(),
    from_year: Number(r.from),
    to_year: r.to ? Number(r.to) : null,
  }));
  const valid = parsed.every(
    (p) =>
      p.name.length > 0 &&
      p.from_year >= 1940 &&
      p.from_year <= thisYear &&
      (p.to_year === null || (p.to_year >= p.from_year && p.to_year <= thisYear)),
  );
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) onAnswer(parsed);
      }}
      className="flex flex-col gap-4"
    >
      {rows.map((row, i) => (
        <fieldset key={i} className="flex flex-col gap-2 rounded-[var(--radius-card)] border border-line bg-surface p-3">
          <legend className="sr-only">{rowLegend(i)}</legend>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            {t("localityName")}
            <input
              className={inputClass}
              maxLength={80}
              value={row.name}
              onChange={(e) => set(i, { ...row, name: e.target.value })}
              required
            />
          </label>
          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              {t("fromYear")}
              <input
                className={inputClass}
                inputMode="numeric"
                dir="ltr"
                maxLength={4}
                value={row.from}
                onChange={(e) => set(i, { ...row, from: e.target.value.replace(/\D/g, "") })}
                required
              />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              {t("toYear")}
              <input
                className={inputClass}
                inputMode="numeric"
                dir="ltr"
                maxLength={4}
                value={row.to}
                onChange={(e) => set(i, { ...row, to: e.target.value.replace(/\D/g, "") })}
              />
            </label>
          </div>
          <RowControls canRemove={rows.length > 1} onRemove={() => remove(i)} />
        </fieldset>
      ))}
      <Button variant="ghost" onClick={add}>
        {t("addAnother")}
      </Button>
      <Button type="submit" fullWidth loading={busy} disabled={!valid}>
        {t("submit")}
      </Button>
    </form>
  );
}
