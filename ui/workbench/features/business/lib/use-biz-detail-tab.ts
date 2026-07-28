"use client";

/** 业务详情路由：静态导出下统一为 `{base}/detail/?id=&tab=`（勿用 `/{id}` 动态段）。 */

import { useCallback, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function detailHref(listBasePath: string, id: string, tab?: string | null, defaultTab = "info"): string {
  const base = listBasePath.replace(/\/$/, "");
  const params = new URLSearchParams();
  params.set("id", id);
  if (tab && tab !== defaultTab) params.set("tab", tab);
  return `${base}/detail/?${params.toString()}`;
}

export function parseBizDetailTab<T extends string>(
  raw: string | null,
  validTabs: readonly T[],
  defaultTab: T,
): T {
  if (raw && validTabs.includes(raw as T)) return raw as T;
  return defaultTab;
}

export function useBizDetailTab<T extends string>(
  listBasePath: string,
  entityId: string,
  validTabs: readonly T[],
  defaultTab: T,
) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = parseBizDetailTab(searchParams.get("tab"), validTabs, defaultTab);

  const handleTabChange = useCallback(
    (next: T) => {
      if (!entityId || entityId === "_") return;
      // 保留除 tab 外的其它 query（如将来扩展）
      const params = new URLSearchParams(searchParams.toString());
      params.set("id", entityId);
      if (next === defaultTab) params.delete("tab");
      else params.set("tab", next);
      const base = listBasePath.replace(/\/$/, "");
      router.replace(`${base}/detail/?${params.toString()}`, { scroll: false });
    },
    [router, listBasePath, entityId, searchParams, defaultTab],
  );

  return { tab, handleTabChange };
}

/** 列表页 `?id=` 旧链接重定向至 `detail/?id=`。 */
export function useBizLegacyDetailRedirect(entityBasePath: string) {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const id = searchParams.get("id");
    if (!id) return;
    const params = new URLSearchParams(searchParams.toString());
    const tab = params.get("tab");
    router.replace(detailHref(entityBasePath, id, tab));
  }, [router, searchParams, entityBasePath]);
}

export function useBizDetailNavigation(entityBasePath: string) {
  const router = useRouter();
  const openDetail = useCallback(
    (id: string, tab?: string) => {
      router.push(detailHref(entityBasePath, id, tab));
    },
    [router, entityBasePath],
  );
  return { openDetail };
}

export { detailHref as buildBizDetailHref };
