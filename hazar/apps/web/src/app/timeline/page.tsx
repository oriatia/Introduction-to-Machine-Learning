import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui";
import { apiFetch } from "@/lib/api-server";
import { formatDate } from "@/lib/questionnaire";

type Timeline = {
  profile: {
    resident: boolean | null;
    sex: string | null;
    marital_status: string | null;
    single_parent: boolean;
    disability: boolean;
  } | null;
  events: { type: string; date_from: string; date_to: string | null; data: { name?: string }; source: string }[];
};

const YEAR_EVENTS = new Set([
  "degree_completed",
  "multiple_employers",
  "partial_year",
  "donation",
  "life_insurance",
  "pension_self",
]);

export async function generateMetadata() {
  const t = await getTranslations("timeline");
  return { title: t("title") };
}

export default async function TimelinePage() {
  const res = await apiFetch("/api/timeline");
  if (res.status === 401) redirect("/login");
  if (!res.ok) throw new Error(`GET /api/timeline failed: ${res.status}`);
  const { profile, events } = (await res.json()) as Timeline;
  const t = await getTranslations("timeline");
  const q = await getTranslations("questionnaire");

  function when(e: Timeline["events"][number]): string {
    if (e.type === "locality") {
      return t("period", {
        from: e.date_from.slice(0, 4),
        to: e.date_to ? e.date_to.slice(0, 4) : t("untilToday"),
      });
    }
    return YEAR_EVENTS.has(e.type) ? e.date_from.slice(0, 4) : formatDate(e.date_from);
  }

  return (
    <AppShell>
      <h1 className="text-2xl font-bold text-brand-900">{t("title")}</h1>
      <p className="text-ink-muted">{t("intro")}</p>

      {profile && (
        <Card title={t("profileTitle")}>
          <ul className="flex flex-col gap-1">
            {profile.resident !== null && <li>{profile.resident ? t("residentYes") : t("residentNo")}</li>}
            {profile.sex && <li>{q(`options.sex.${profile.sex}`)}</li>}
            {profile.marital_status && <li>{q(`options.marital_status.${profile.marital_status}`)}</li>}
          </ul>
        </Card>
      )}

      <section aria-labelledby="events-title" className="flex flex-col gap-3">
        <h2 id="events-title" className="text-lg font-bold">
          {t("eventsTitle")}
        </h2>
        {events.length === 0 ? (
          <p>{t("empty")}</p>
        ) : (
          <ol className="flex flex-col gap-0 border-s-2 border-brand-100 ps-4">
            {events.map((e, i) => (
              <li key={i} className="relative pb-4">
                <span
                  aria-hidden="true"
                  className="absolute -start-[1.4rem] top-1.5 size-3 rounded-full bg-brand-700"
                />
                <p className="font-semibold">{t(`types.${e.type}`, { name: e.data.name ?? "" })}</p>
                <p className="text-sm text-ink-muted">{when(e)}</p>
              </li>
            ))}
          </ol>
        )}
      </section>

      <div className="flex flex-col items-center gap-3">
        <Link href="/estimate" className="font-semibold text-brand-700 underline underline-offset-4">
          {t("toEstimate")}
        </Link>
        <Link href="/questionnaire" className="font-semibold text-brand-700 underline underline-offset-4">
          {t("editAnswers")}
        </Link>
      </div>
    </AppShell>
  );
}
