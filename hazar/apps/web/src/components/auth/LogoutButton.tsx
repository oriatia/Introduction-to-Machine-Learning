"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui";
import { postJson } from "@/lib/api-client";

export function LogoutButton() {
  const t = useTranslations("home");
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  return (
    <Button
      variant="secondary"
      loading={loading}
      onClick={async () => {
        setLoading(true);
        await postJson("/api/auth/logout", {});
        router.replace("/login");
        router.refresh();
      }}
    >
      {t("logout")}
    </Button>
  );
}
