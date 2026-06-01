"use client";

/** 列表页详情抽屉与 URL `?id=` 同步（可与其他 query 共存）。 */

import { useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export function useBizDetailQuery(basePath: string) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const detailId = searchParams.get("id");

  const openDetail = useCallback(
    (id: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("id", id);
      router.replace(`${basePath}?${params.toString()}`, { scroll: false });
    },
    [router, basePath, searchParams],
  );

  const closeDetail = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("id");
    const q = params.toString();
    router.replace(q ? `${basePath}?${q}` : basePath, { scroll: false });
  }, [router, basePath, searchParams]);

  return { detailId, openDetail, closeDetail };
};
