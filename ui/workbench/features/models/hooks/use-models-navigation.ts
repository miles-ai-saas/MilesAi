"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export function useModelsNavigation() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const modelFromUrl = searchParams.get("model");

  const [detailModelId, setDetailModelId] = useState<string | null>(null);

  useEffect(() => {
    if (modelFromUrl) setDetailModelId(modelFromUrl);
  }, [modelFromUrl]);

  const closeDetail = useCallback(() => {
    setDetailModelId(null);
    const params = new URLSearchParams(searchParams.toString());
    params.delete("model");
    const q = params.toString();
    router.replace(q ? `/workbench/models?${q}` : "/workbench/models", { scroll: false });
  }, [router, searchParams]);

  const openDetail = useCallback(
    (id: string) => {
      setDetailModelId(id);
      const params = new URLSearchParams(searchParams.toString());
      params.set("model", id);
      router.replace(`/workbench/models?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  return { detailModelId, openDetail, closeDetail };
}

export type ModelsNavigationSlice = ReturnType<typeof useModelsNavigation>;
