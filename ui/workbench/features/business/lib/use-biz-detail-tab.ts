"use client";

/** 详情页 Tab 与 URL `?tab=` 同步（与项目详情页一致）。 */

import { useCallback, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export function parseBizDetailTab<T extends string>(
  raw: string | null,
  validTabs: readonly T[],
  defaultTab: T,
): T {
  if (raw && validTabs.includes(raw as T)) return raw as T;
  return defaultTab;
}

export function useBizDetailTab<T extends string>(
  basePath: string,
  entityId: string,
  validTabs: readonly T[],
  defaultTab: T,
) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = parseBizDetailTab(searchParams.get("tab"), validTabs, defaultTab);

  const handleTabChange = useCallback(
    (next: T) => {
      const params = new URLSearchParams(searchParams.toString());
      if (next === defaultTab) params.delete("tab");
      else params.set("tab", next);
      const q = params.toString();
      router.replace(`${basePath}/${entityId}${q ? `?${q}` : ""}`, { scroll: false });
    },
    [router, basePath, entityId, searchParams, defaultTab],
  );

  return { tab, handleTabChange };
}

/** 列表页 `?id=` 旧链接重定向至独立详情页。 */
export function useBizLegacyDetailRedirect(entityBasePath: string) {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const id = searchParams.get("id");
    if (!id) return;
    const params = new URLSearchParams(searchParams.toString());
    params.delete("id");
    const tab = params.get("tab");
    const rest = params.toString();
    let target = `${entityBasePath}/${id}`;
    if (tab) target += `?tab=${encodeURIComponent(tab)}`;
    else if (rest) target += `?${rest}`;
    router.replace(target);
  }, [router, searchParams, entityBasePath]);
}

export function useBizDetailNavigation(entityBasePath: string) {
  const router = useRouter();
  const openDetail = useCallback(
    (id: string, tab?: string) => {
      const q = tab && tab !== "info" ? `?tab=${encodeURIComponent(tab)}` : "";
      router.push(`${entityBasePath}/${id}${q}`);
    },
    [router, entityBasePath],
  );
  return { openDetail };
}
