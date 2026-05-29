"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { usePagedList } from "@/hooks/use-paged-list";
import { filterBySearch } from "@/lib/filter-search";
import { marketplaceAppSearchText, type MarketplaceMainView } from "@/lib/marketplace-page-shared";
import type { ResourceTab } from "@/components/resource/ResourceListLayout";
import type { AppCategory } from "@/lib/types";

type Params = {
  ready: boolean;
  mainView: MarketplaceMainView;
  showReviewTab: boolean;
  search: string;
  tagFilterIds: string[];
  activeCategory: string;
  plazaSort: "installs" | "rating";
};

export function useMarketplacePageLists({ ready, mainView, showReviewTab, search, tagFilterIds, activeCategory, plazaSort }: Params) {
  const [categories, setCategories] = useState<AppCategory[]>([]);
  const tagFilterKey = tagFilterIds.join(",");

  const apps = usePagedList(
    useCallback(
      (p, s) => api.listMarketplaceApps(p, s, activeCategory || undefined, plazaSort, tagFilterIds.length ? tagFilterIds : undefined),
      [activeCategory, plazaSort, tagFilterKey],
    ),
    { enabled: ready && mainView === "plaza", resetKey: `${activeCategory}-${plazaSort}-${tagFilterKey}-plaza` },
  );

  const installs = usePagedList(useCallback((p, s) => api.listAppInstalls(p, s), []), {
    enabled: ready && mainView === "installs",
    resetKey: "installs",
  });

  const myApps = usePagedList(
    useCallback((p, s) => api.listMyMarketplaceApps(p, s, tagFilterIds.length ? tagFilterIds : undefined), [tagFilterKey]),
    { enabled: ready && mainView === "mine", resetKey: `mine-${tagFilterKey}` },
  );

  const pendingApps = usePagedList(
    useCallback((p, s) => api.listPendingMarketplaceApps(p, s, tagFilterIds.length ? tagFilterIds : undefined), [tagFilterKey]),
    { enabled: ready && mainView === "review" && showReviewTab, resetKey: `pending-${tagFilterKey}` },
  );

  useEffect(() => {
    if (!ready) return;
    api.listMarketplaceCategories().then(setCategories);
  }, [ready]);

  const categoryTabs: ResourceTab[] = useMemo(
    () => [{ key: "", label: "全部" }, ...categories.map((c) => ({ key: c.slug, label: c.name }))],
    [categories],
  );

  const plazaFiltered = useMemo(() => filterBySearch(apps.items, search, marketplaceAppSearchText), [apps.items, search]);
  const installsFiltered = useMemo(() => filterBySearch(installs.items, search, (i) => i.app_name), [installs.items, search]);
  const myFiltered = useMemo(() => filterBySearch(myApps.items, search, marketplaceAppSearchText), [myApps.items, search]);
  const pendingFiltered = useMemo(() => filterBySearch(pendingApps.items, search, marketplaceAppSearchText), [pendingApps.items, search]);
  const plazaInstalledOnPage = useMemo(() => plazaFiltered.filter((a) => a.installed).length, [plazaFiltered]);

  return {
    categories,
    categoryTabs,
    apps,
    installs,
    myApps,
    pendingApps,
    plazaFiltered,
    installsFiltered,
    myFiltered,
    pendingFiltered,
    plazaInstalledOnPage,
  };
}

export type MarketplacePageLists = ReturnType<typeof useMarketplacePageLists>;
