import { getRequestConfig } from "next-intl/server";

// Hebrew only in phase 1. ru/ar/en arrive later as locales/{locale}.json.
export const DEFAULT_LOCALE = "he";

export default getRequestConfig(async () => {
  const locale = DEFAULT_LOCALE;
  return {
    locale,
    timeZone: "Asia/Jerusalem",
    messages: (await import(`../../locales/${locale}.json`)).default,
  };
});
