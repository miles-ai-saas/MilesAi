"use client";

import { useCallback, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export function useModelCatalogPage() {
  const ready = useRequireAdmin();
  const [vendor, setVendor] = useState("");

  const list = usePagedList(
    useCallback((p, s) => adminApi.listModelCatalog(p, s, vendor || undefined), [vendor]),
    { enabled: ready, resetKey: vendor },
  );

  return {
    vendor,
    setVendor,
    list,
  };
}

export type ModelCatalogPageVm = ReturnType<typeof useModelCatalogPage>;
