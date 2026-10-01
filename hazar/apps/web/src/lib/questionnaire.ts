export type Kind = "yes_no" | "choice" | "date" | "dates" | "years" | "window_years" | "localities";

export type Locality = { name: string; from_year: number; to_year: number | null };

export type Question = { id: string; kind: Kind; options: string[]; window: number[] };

export type Answered = { id: string; kind: Kind; value: unknown };

export type QuestionnaireState = {
  next: Question | null;
  answered: Answered[];
  total: number;
  complete: boolean;
};

/** "2022-06-01" → "1.6.2022", without timezone drift. */
export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("he-IL", { timeZone: "UTC" }).format(new Date(`${iso}T00:00:00Z`));
}

type Translate = (key: string, values?: Record<string, string | number>) => string;

/** Human-readable answer for the user's chat bubble. `t` is scoped to the "questionnaire" namespace. */
export function formatAnswer(t: Translate, a: Answered): string {
  const v = a.value;
  switch (a.kind) {
    case "yes_no":
      return v ? t("yes") : t("no");
    case "choice":
      return t(`options.${a.id}.${String(v)}`);
    case "date":
      return formatDate(String(v));
    case "dates":
      return (v as string[]).map(formatDate).join(", ");
    case "years":
    case "window_years":
      return (v as number[]).join(", ");
    case "localities":
      return (v as Locality[])
        .map((l) =>
          t("localityAnswer", {
            name: l.name,
            period: t("period", { from: l.from_year, to: l.to_year ?? t("untilToday") }),
          }),
        )
        .join(", ");
  }
}
