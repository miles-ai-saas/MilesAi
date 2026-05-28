"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { filterBySearch } from "@/lib/filter-search";
import { useMarketplaceMeta } from "@/hooks/use-marketplace-meta";
import { MARKETPLACE_PAGE_DESC } from "@/components/marketplace/marketplace-page-ui";
import type { ResourceTab } from "@/components/resource/ResourceListLayout";
import type {
  Agent,
  AppCategory,
  AppInstall,
  AppInstallResult,
  AppRating,
  AppRollbackPreview,
  AppUpgradePreview,
  Flow,
  KnowledgeBase,
  MarketplaceApp,
  MarketplaceAppDetail,
} from "@/lib/types";

export type MarketplaceMainView = "plaza" | "installs" | "mine" | "publish" | "review";

export function useMarketplacePage() {
  const { ready, user } = useRequireAuth();
  const marketplaceMeta = useMarketplaceMeta(ready);
  const reviewMode = marketplaceMeta?.review_mode ?? "tenant";
  const canReview = Boolean(user?.is_superuser || user?.permissions?.includes("marketplace:review"));
  const showReviewTab = canReview && reviewMode === "tenant";
  const [mainView, setMainView] = useState<MarketplaceMainView>("plaza");
  const [plazaSort, setPlazaSort] = useState<"installs" | "rating">("installs");
  const [search, setSearch] = useState("");
  const [categories, setCategories] = useState<AppCategory[]>([]);
  const [activeCategory, setActiveCategory] = useState("");
  const [installing, setInstalling] = useState<string | null>(null);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [upgradeTarget, setUpgradeTarget] = useState<AppInstall | null>(null);
  const [upgradePreview, setUpgradePreview] = useState<AppUpgradePreview | null>(null);
  const [upgradePreviewLoading, setUpgradePreviewLoading] = useState(false);
  const [rollbackTarget, setRollbackTarget] = useState<AppInstall | null>(null);
  const [rollbackPreview, setRollbackPreview] = useState<AppUpgradePreview | null>(null);
  const [rollbackPreviewLoading, setRollbackPreviewLoading] = useState(false);
  const [rollingBack, setRollingBack] = useState<string | null>(null);
  const [publishing, setPublishing] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [rejectTarget, setRejectTarget] = useState<MarketplaceApp | null>(null);
  const [rejectLoading, setRejectLoading] = useState(false);
  const [lastResult, setLastResult] = useState<AppInstallResult | null>(null);
  const [msg, setMsg] = useState("");

  const [detailAppId, setDetailAppId] = useState<string | null>(null);
  const [detail, setDetail] = useState<MarketplaceAppDetail | null>(null);
  const [detailRatings, setDetailRatings] = useState<AppRating[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [rateScore, setRateScore] = useState(5);
  const [rateComment, setRateComment] = useState("");
  const [rateSaving, setRateSaving] = useState(false);

  const [publishName, setPublishName] = useState("");
  const [publishDesc, setPublishDesc] = useState("");
  const [publishIcon, setPublishIcon] = useState("📦");
  const [publishCategory, setPublishCategory] = useState("rag");
  const [publishKbId, setPublishKbId] = useState("");
  const [publishFlowId, setPublishFlowId] = useState("");
  const [publishAgentId, setPublishAgentId] = useState("");
  const [publishTagIds, setPublishTagIds] = useState<string[]>([]);
  const [publishVisibility, setPublishVisibility] = useState<"public" | "tenant_only">("public");
  const [tagFilterIds, setTagFilterIds] = useState<string[]>([]);
  const [publishLoading, setPublishLoading] = useState(false);
  const [resourceOptions, setResourceOptions] = useState<{
    kbs: KnowledgeBase[];
    flows: Flow[];
    agents: Agent[];
  }>({ kbs: [], flows: [], agents: [] });

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

  const switchView = (view: MarketplaceMainView) => {
    setMainView(view);
    setSearch("");
    setTagFilterIds([]);
    setMsg("");
  };

  const tagFilterKey = tagFilterIds.join(",");

  const apps = usePagedList(
    useCallback(
      (p, s) => api.listMarketplaceApps(p, s, activeCategory || undefined, plazaSort, tagFilterIds.length ? tagFilterIds : undefined),
      [activeCategory, plazaSort, tagFilterKey],
    ),
    { enabled: ready && mainView === "plaza", resetKey: `${activeCategory}-${plazaSort}-${tagFilterKey}-plaza` },
  );
  const installs = usePagedList(
    useCallback((p, s) => api.listAppInstalls(p, s), []),
    {
      enabled: ready && mainView === "installs",
      resetKey: "installs",
    },
  );
  const myApps = usePagedList(
    useCallback((p, s) => api.listMyMarketplaceApps(p, s, tagFilterIds.length ? tagFilterIds : undefined), [tagFilterKey]),
    {
      enabled: ready && mainView === "mine",
      resetKey: `mine-${tagFilterKey}`,
    },
  );
  const pendingApps = usePagedList(
    useCallback((p, s) => api.listPendingMarketplaceApps(p, s, tagFilterIds.length ? tagFilterIds : undefined), [tagFilterKey]),
    { enabled: ready && mainView === "review" && showReviewTab, resetKey: `pending-${tagFilterKey}` },
  );

  useEffect(() => {
    if (!ready) return;
    api.listMarketplaceCategories().then(setCategories);
  }, [ready]);

  useEffect(() => {
    if (!ready || mainView !== "publish") return;
    Promise.all([api.listKbs(1, 100), api.listFlows(1, 100), api.listAgents(1, 100)]).then(([kbRes, flowRes, agentRes]) => {
      setResourceOptions({
        kbs: kbRes.items,
        flows: flowRes.items,
        agents: agentRes.items,
      });
    });
  }, [ready, mainView]);

  const loadDetail = useCallback(async (appId: string) => {
    setDetailAppId(appId);
    setDetailLoading(true);
    setDetail(null);
    setDetailRatings([]);
    try {
      const [d, ratings] = await Promise.all([api.getMarketplaceApp(appId), api.listMarketplaceAppRatings(appId, 1, 20)]);
      setDetail(d);
      setDetailRatings(ratings.items);
      if (d.my_rating) {
        setRateScore(d.my_rating.score);
        setRateComment(d.my_rating.comment ?? "");
      } else {
        setRateScore(5);
        setRateComment("");
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "加载详情失败");
      setDetailAppId(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const categoryTabs: ResourceTab[] = useMemo(() => [{ key: "", label: "全部" }, ...categories.map((c) => ({ key: c.slug, label: c.name }))], [categories]);

  const appSearchText = (a: MarketplaceApp) => `${a.name} ${a.description ?? ""} ${(a.tags ?? []).map((t) => t.name).join(" ")}`;

  const plazaFiltered = useMemo(() => filterBySearch(apps.items, search, appSearchText), [apps.items, search]);
  const installsFiltered = useMemo(() => filterBySearch(installs.items, search, (i) => i.app_name), [installs.items, search]);
  const myFiltered = useMemo(() => filterBySearch(myApps.items, search, appSearchText), [myApps.items, search]);
  const pendingFiltered = useMemo(() => filterBySearch(pendingApps.items, search, appSearchText), [pendingApps.items, search]);

  const plazaInstalledOnPage = useMemo(() => plazaFiltered.filter((a) => a.installed).length, [plazaFiltered]);

  const onOpenUpgrade = async (ins: AppInstall) => {
    setUpgradeTarget(ins);
    setUpgradePreview(null);
    setUpgradePreviewLoading(true);
    setMsg("");
    try {
      const preview = await api.getMarketplaceUpgradePreview(ins.app_id);
      setUpgradePreview(preview);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "加载升级预览失败");
      setUpgradeTarget(null);
    } finally {
      setUpgradePreviewLoading(false);
    }
  };

  const closeUpgradeDialog = () => {
    if (upgrading) return;
    setUpgradeTarget(null);
    setUpgradePreview(null);
    setUpgradePreviewLoading(false);
  };

  const onConfirmUpgrade = async () => {
    if (!upgradeTarget) return;
    setUpgrading(upgradeTarget.app_id);
    setMsg("");
    try {
      const res = await api.upgradeMarketplaceApp(upgradeTarget.app_id);
      setMsg(res.message);
      setUpgradeTarget(null);
      setUpgradePreview(null);
      await installs.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "升级失败");
    } finally {
      setUpgrading(null);
      setUpgradePreviewLoading(false);
    }
  };

  const rollbackPreviewToUpgrade = (p: import("@/lib/types").AppRollbackPreview): AppUpgradePreview => ({
    app_id: p.app_id,
    app_name: p.app_name,
    installed_version: p.current_version,
    target_version: p.target_version,
    can_upgrade: p.can_rollback,
    has_changes: p.resources.some((r) => r.has_changes),
    message: p.message,
    resources: p.resources,
  });

  const onOpenRollback = async (ins: AppInstall) => {
    setRollbackTarget(ins);
    setRollbackPreview(null);
    setRollbackPreviewLoading(true);
    setMsg("");
    try {
      const preview = await api.getMarketplaceRollbackPreview(ins.app_id);
      setRollbackPreview(rollbackPreviewToUpgrade(preview));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "加载回滚预览失败");
      setRollbackTarget(null);
    } finally {
      setRollbackPreviewLoading(false);
    }
  };

  const closeRollbackDialog = () => {
    if (rollingBack) return;
    setRollbackTarget(null);
    setRollbackPreview(null);
    setRollbackPreviewLoading(false);
  };

  const onConfirmRollback = async () => {
    if (!rollbackTarget) return;
    setRollingBack(rollbackTarget.app_id);
    setMsg("");
    try {
      const res = await api.rollbackMarketplaceApp(rollbackTarget.app_id);
      setMsg(res.message);
      setRollbackTarget(null);
      setRollbackPreview(null);
      await installs.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "回滚失败");
    } finally {
      setRollingBack(null);
      setRollbackPreviewLoading(false);
    }
  };

  const onInstall = async (app: MarketplaceApp) => {
    if (app.installed) {
      setMsg("该应用已安装");
      return;
    }
    setInstalling(app.id);
    setMsg("");
    try {
      const res = await api.installMarketplaceApp(app.id);
      setLastResult(res);
      setMsg(res.message);
      await apps.reload();
      if (mainView === "installs") await installs.reload();
      if (detailAppId === app.id) await loadDetail(app.id);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "安装失败");
    } finally {
      setInstalling(null);
    }
  };

  const onTrial = async (app: MarketplaceApp) => {
    if (app.installed) {
      setMsg("该应用已安装");
      return;
    }
    setInstalling(app.id);
    setMsg("");
    try {
      const res = await api.trialMarketplaceApp(app.id);
      setLastResult(res);
      setMsg("试用已安装，24 小时内有效");
      await apps.reload();
      if (detailAppId === app.id) await loadDetail(app.id);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "试用失败");
    } finally {
      setInstalling(null);
    }
  };

  const onSubmitReview = async (appId: string) => {
    setPublishing(appId);
    setMsg("");
    try {
      await api.publishMarketplaceApp(appId);
      setMsg(reviewMode === "off" ? "已上架" : reviewMode === "platform" ? "已提交，等待平台运营审核" : "已提交审核，通过后将在应用广场展示");
      await myApps.reload();
      if (showReviewTab) await pendingApps.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "提交失败");
    } finally {
      setPublishing(null);
    }
  };

  const onApprove = async (appId: string) => {
    setReviewing(appId);
    setMsg("");
    try {
      await api.approveMarketplaceApp(appId);
      setMsg("已通过审核并上架");
      await pendingApps.reload();
      await apps.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "操作失败");
    } finally {
      setReviewing(null);
    }
  };

  const onReject = (app: MarketplaceApp) => setRejectTarget(app);

  const onConfirmReject = async (note: string) => {
    if (!rejectTarget) return;
    setRejectLoading(true);
    setMsg("");
    try {
      await api.rejectMarketplaceApp(rejectTarget.id, note || undefined);
      setMsg("已驳回该应用");
      setRejectTarget(null);
      await pendingApps.reload();
      await myApps.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "驳回失败");
    } finally {
      setRejectLoading(false);
    }
  };

  const onCreateDraft = async () => {
    if (!publishName.trim()) {
      setMsg("请填写应用名称");
      return;
    }
    if (!publishKbId && !publishFlowId && !publishAgentId) {
      setMsg("请至少选择知识库、流程或智能体之一");
      return;
    }
    setPublishLoading(true);
    setMsg("");
    try {
      await api.createMarketplaceAppFromResources({
        name: publishName.trim(),
        description: publishDesc.trim() || undefined,
        icon: publishIcon || "📦",
        category_slug: publishCategory || undefined,
        kb_id: publishKbId || undefined,
        flow_id: publishFlowId || undefined,
        agent_id: publishAgentId || undefined,
        tag_ids: publishTagIds,
        visibility: publishVisibility,
      });
      setMsg("草稿已创建，可在「我的上架」中提交审核");
      setPublishName("");
      setPublishDesc("");
      setPublishKbId("");
      setPublishFlowId("");
      setPublishAgentId("");
      setPublishTagIds([]);
      switchView("mine");
      await myApps.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "创建失败");
    } finally {
      setPublishLoading(false);
    }
  };

  const onSaveRating = async () => {
    if (!detailAppId || !detail?.installed) return;
    setRateSaving(true);
    try {
      await api.rateMarketplaceApp(detailAppId, {
        score: rateScore,
        comment: rateComment.trim() || undefined,
      });
      setMsg("评分已保存");
      await loadDetail(detailAppId);
      await apps.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "评分失败");
    } finally {
      setRateSaving(false);
    }
  };

  const onDeleteRating = async () => {
    if (!detailAppId) return;
    setRateSaving(true);
    try {
      await api.deleteMyMarketplaceRating(detailAppId);
      setMsg("已删除评分");
      await loadDetail(detailAppId);
      await apps.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "删除失败");
    } finally {
      setRateSaving(false);
    }
  };
  const layoutCommon = {
    title: "应用市场",
    description: MARKETPLACE_PAGE_DESC,
    tabs: mainTabs,
    activeTab: mainView,
    onTabChange: (k: string) => switchView(k as MarketplaceMainView),
  };

  const closeDetail = () => {
    setDetailAppId(null);
    setDetail(null);
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
    categories,
    activeCategory,
    setActiveCategory,
    installing,
    upgrading,
    upgradeTarget,
    upgradePreview,
    upgradePreviewLoading,
    rollbackTarget,
    rollbackPreview,
    rollbackPreviewLoading,
    rollingBack,
    publishing,
    reviewing,
    rejectTarget,
    setRejectTarget,
    rejectLoading,
    lastResult,
    setLastResult,
    msg,
    setMsg,
    detailAppId,
    detail,
    detailRatings,
    detailLoading,
    rateScore,
    setRateScore,
    rateComment,
    setRateComment,
    rateSaving,
    publishName,
    setPublishName,
    publishDesc,
    setPublishDesc,
    publishIcon,
    setPublishIcon,
    publishCategory,
    setPublishCategory,
    publishKbId,
    setPublishKbId,
    publishFlowId,
    setPublishFlowId,
    publishAgentId,
    setPublishAgentId,
    publishTagIds,
    setPublishTagIds,
    publishVisibility,
    setPublishVisibility,
    tagFilterIds,
    setTagFilterIds,
    publishLoading,
    resourceOptions,
    mainTabs,
    layoutCommon,
    apps,
    installs,
    myApps,
    pendingApps,
    categoryTabs,
    plazaFiltered,
    installsFiltered,
    myFiltered,
    pendingFiltered,
    plazaInstalledOnPage,
    loadDetail,
    closeDetail,
    onOpenUpgrade,
    closeUpgradeDialog,
    onConfirmUpgrade,
    onOpenRollback,
    closeRollbackDialog,
    onConfirmRollback,
    onInstall,
    onTrial,
    onSubmitReview,
    onApprove,
    onReject,
    onConfirmReject,
    onCreateDraft,
    onSaveRating,
    onDeleteRating,
  };
}

export type MarketplacePageVm = ReturnType<typeof useMarketplacePage>;
