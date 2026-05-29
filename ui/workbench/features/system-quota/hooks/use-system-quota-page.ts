"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import type { TenantQuota } from "@/lib/types";

export function useSystemQuotaPage() {
  const { ready } = useRequireAuth();
  const [quota, setQuota] = useState<TenantQuota | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!ready) return;
    setLoading(true);
    setError("");
    void api
      .getSystemQuota()
      .then(setQuota)
      .catch((e: Error) => setError(e.message || "加载失败"))
      .finally(() => setLoading(false));
  }, [ready]);

  return { quota, loading, error };
}

export type SystemQuotaPageVm = ReturnType<typeof useSystemQuotaPage>;
