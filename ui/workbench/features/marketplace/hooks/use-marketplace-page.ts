"use client";

import { useMemo, useState } from "react";
import { useMarketplaceAppDetail } from "@/features/marketplace/hooks/use-marketplace-app-detail";
import { useMarketplaceInstallOps } from "@/features/marketplace/hooks/use-marketplace-install-ops";
import { useMarketplacePageLists } from "@/features/marketplace/hooks/use-marketplace-page-lists";
import { useMarketplacePublishForm } from "@/features/marketplace/hooks/use-marketplace-publish-form";
import { useMarketplaceMeta } from "@/features/marketplace/hooks/use-marketplace-meta";
import { useRequireAuth } from "@/lib/auth-store";
import type { MarketplaceMainView } from "@/features/marketplace/lib/marketplace-page-shared";
import type { ResourceTab } from "@/components/resource/ResourceListLayout";

const MARKETPLACE_PAGE_DESC =
  "浏览并安装已审核上架的应用；可将本租户知识库、流程或智能体打包为应用，审核通过后供其他租户安装。";

export type { MarketplaceMainView } from "@/features/marketplace/lib/marketplace-page-shared";

export function useMarketplacePage() {
  const { ready, user } = useRequireAuth();
  const marketplaceMeta = useMarketplaceMeta(ready);
  const reviewMode = marketplaceMeta?.review_mode ?? "tenant";
  const canReview = Boolean(user?.is_superuser || user?.permissions?.includes("marketplace:review"));
  const showReviewTab = canReview && reviewMode === "tenant";

  const [mainView, setMainView] = useState<MarketplaceMainView>("plaza");
  const [plazaSort, setPlazaSort] = useState<"installs" | "rating">("installs");
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState("");
  const [tagFilterIds, setTagFilterIds] = useState<string[]>([]);
  const [msg, setMsg] = useState("");

  const switchView = (view: MarketplaceMainView) => {
    setMainView(view);
    setSearch("");
    setTagFilterIds([]);
    setMsg("");
  };

  const mainTabs: ResourceTab[] = useMemo(
    () => [
      { key: "plaza", label: "应用广场" },
      { key: "installs", label: "我的安装" },
      { key: "mine", label: "我的上架" },
      { key: "publish", label: "打包上架" },
      ...(showReviewTab ? [{ key: "review", label: "上架审核" }] : []),
    ],
    [showReviewTab],
  );

  const lists = useMarketplacePageLists({
    ready,
    mainView,
    showReviewTab,
    search,
    tagFilterIds,
    activeCategory,
    plazaSort,
  });

  const detail = useMarketplaceAppDetail({
    setMsg,
    reloadApps: lists.apps.reload,
  });

  const publish = useMarketplacePublishForm({
    ready,
    mainView,
    setMsg,
    switchView,
    reloadMyApps: lists.myApps.reload,
  });

  const ops = useMarketplaceInstallOps({
    setMsg,
    mainView,
    reviewMode,
    showReviewTab,
    detailAppId: detail.detailAppId,
    reloadDetail: detail.loadDetail,
    reloadApps: lists.apps.reload,
    reloadInstalls: lists.installs.reload,
    reloadMyApps: lists.myApps.reload,
    reloadPendingApps: lists.pendingApps.reload,
  });

  const layoutCommon = {
    title: "应用市场",
    description: MARKETPLACE_PAGE_DESC,
    tabs: mainTabs,
    activeTab: mainView,
    onTabChange: (k: string) => switchView(k as MarketplaceMainView),
  };

  return {
    ready,
    marketplaceMeta,
    reviewMode,
    showReviewTab,
    mainView,
    switchView,
    plazaSort,
    setPlazaSort,
    search,
    setSearch,
    activeCategory,
    setActiveCategory,
    tagFilterIds,
    setTagFilterIds,
    msg,
    setMsg,
    mainTabs,
    layoutCommon,
    ...lists,
    ...detail,
    ...publish,
    ...ops,
  };
}

export type MarketplacePageVm = ReturnType<typeof useMarketplacePage>;
