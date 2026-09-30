import type { MetadataRoute } from "next";
import { getTranslations } from "next-intl/server";

export default async function manifest(): Promise<MetadataRoute.Manifest> {
  const t = await getTranslations("app");
  return {
    name: t("name"),
    short_name: t("shortName"),
    description: t("description"),
    lang: "he",
    dir: "rtl",
    start_url: "/",
    display: "standalone",
    background_color: "#f6f7f9",
    theme_color: "#0f766e",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
