"use client";

/** 应用市场（链路 §12）：多主视图 + 分页列表 + `useMarketplaceMeta`。 */

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { MarketplaceAppDetailDrawer } from "@/components/marketplace/MarketplaceAppDetailDrawer";
import { MarketplaceUpgradeDialog } from "@/components/marketplace/MarketplaceUpgradeDialog";
import { MarketplaceStarDisplay } from "@/components/marketplace/MarketplaceStarDisplay";
import { TagChips } from "@/components/tag/TagChips";
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import { TagPicker } from "@/components/tag/TagPicker";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout, type ResourceTab } from "@/components/resource/ResourceListLayout";
import { PromptDialog } from "@/components/resource/PromptDialog";
import { filterBySearch } from "@/lib/filter-search";
import {
  marketplaceCatalogSortOptions,
  marketplaceStatusLabel,
  marketplaceVisibilityLabel,
} from "@/lib/marketplace-labels";
import { useMarketplaceMeta } from "@/hooks/use-marketplace-meta";
import type {
  Agent,
  AppCategory,
  AppInstall,
  AppInstallResult,
  AppRating,
  AppUpgradePreview,
  Flow,
  KnowledgeBase,
  MarketplaceApp,
  MarketplaceAppDetail,
} from "@/lib/types";

type MainView = "plaza" | "installs" | "mine" | "publish" | "review";

const PAGE_DESC =
  "浏览并安装已审核上架的应用；可将本租户知识库、流程或智能体打包为应用，审核通过后供其他租户安装。";

function StatChip({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3 shadow-card">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-0.5 text-2xl font-bold tabular-nums text-brand">{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink-faint">{hint}</p> : null}
    </div>
  );
}

function PageMessage({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return (
    <div className="col-span-full flex items-start justify-between gap-3 rounded-xl border border-line bg-brand-light/40 px-4 py-3 text-sm text-ink">
      <p className="min-w-0 flex-1">{message}</p>
      {onDismiss && (
        <button type="button" className="shrink-0 text-xs text-ink-muted hover:text-ink" onClick={onDismiss}>
          关闭
        </button>
      )}
    </div>
  );
}

function InstallSuccessBanner({ result, onDismiss }: { result: AppInstallResult; onDismiss: () => void }) {
  return (
    <div className="col-span-full rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
      <div className="flex items-start justify-between gap-3">
        <p className="font-medium">{result.message || "安装完成"}</p>
        <button type="button" className="text-xs opacity-70 hover:opacity-100" onClick={onDismiss}>
          关闭
        </button>
      </div>
      <ul className="mt-2 space-y-1 text-xs">
        {result.kb_id && (
          <li>
            知识库 →{" "}
            <Link href={`/workbench/kb/${result.kb_id}`} className="underline">
              管理文档
            </Link>
          </li>
        )}
        {result.flow_id && (
          <li>
            流程 →{" "}
            <Link href={`/workbench/flows/${result.flow_id}/edit`} className="underline">
              编辑画布
            </Link>
          </li>
        )}
        {result.agent_id && (
          <li>
            智能体 →{" "}
            <Link href="/workbench/agents/chat" className="underline">
              去对话
            </Link>
          </li>
        )}
      </ul>
    </div>
  );
}

export default function MarketplacePage() {
  const { ready, user } = useRequireAuth();
  const marketplaceMeta = useMarketplaceMeta(ready);
  const reviewMode = marketplaceMeta?.review_mode ?? "tenant";
  const canReview = Boolean(
    user?.is_superuser || user?.permissions?.includes("marketplace:review"),
  );
  const showReviewTab = canReview && reviewMode === "tenant";
  const [mainView, setMainView] = useState<MainView>("plaza");
  const [plazaSort, setPlazaSort] = useState<"installs" | "rating">("installs");
  const [search, setSearch] = useState("");
  const [categories, setCategories] = useState<AppCategory[]>([]);
  const [activeCategory, setActiveCategory] = useState("");
  const [installing, setInstalling] = useState<string | null>(null);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [upgradeTarget, setUpgradeTarget] = useState<AppInstall | null>(null);
  const [upgradePreview, setUpgradePreview] = useState<AppUpgradePreview | null>(null);
  const [upgradePreviewLoading, setUpgradePreviewLoading] = useState(false);
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

  const switchView = (view: MainView) => {
    setMainView(view);
    setSearch("");
    setTagFilterIds([]);
    setMsg("");
  };

  const tagFilterKey = tagFilterIds.join(",");

  const apps = usePagedList(
    useCallback(
      (p, s) =>
        api.listMarketplaceApps(
          p,
          s,
          activeCategory || undefined,
          plazaSort,
          tagFilterIds.length ? tagFilterIds : undefined,
        ),
      [activeCategory, plazaSort, tagFilterKey],
    ),
    { enabled: ready && mainView === "plaza", resetKey: `${activeCategory}-${plazaSort}-${tagFilterKey}-plaza` },
  );
  const installs = usePagedList(useCallback((p, s) => api.listAppInstalls(p, s), []), {
    enabled: ready && mainView === "installs",
    resetKey: "installs",
  });
  const myApps = usePagedList(
    useCallback(
      (p, s) => api.listMyMarketplaceApps(p, s, tagFilterIds.length ? tagFilterIds : undefined),
      [tagFilterKey],
    ),
    {
      enabled: ready && mainView === "mine",
      resetKey: `mine-${tagFilterKey}`,
    },
  );
  const pendingApps = usePagedList(
    useCallback(
      (p, s) => api.listPendingMarketplaceApps(p, s, tagFilterIds.length ? tagFilterIds : undefined),
      [tagFilterKey],
    ),
    { enabled: ready && mainView === "review" && showReviewTab, resetKey: `pending-${tagFilterKey}` },
  );

  useEffect(() => {
    if (!ready) return;
    api.listMarketplaceCategories().then(setCategories);
  }, [ready]);

  useEffect(() => {
    if (!ready || mainView !== "publish") return;
    Promise.all([api.listKbs(1, 100), api.listFlows(1, 100), api.listAgents(1, 100)]).then(
      ([kbRes, flowRes, agentRes]) => {
        setResourceOptions({
          kbs: kbRes.items,
          flows: flowRes.items,
          agents: agentRes.items,
        });
      },
    );
  }, [ready, mainView]);

  const loadDetail = useCallback(async (appId: string) => {
    setDetailAppId(appId);
    setDetailLoading(true);
    setDetail(null);
    setDetailRatings([]);
    try {
      const [d, ratings] = await Promise.all([
        api.getMarketplaceApp(appId),
        api.listMarketplaceAppRatings(appId, 1, 20),
      ]);
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

  const categoryTabs: ResourceTab[] = useMemo(
    () => [{ key: "", label: "全部" }, ...categories.map((c) => ({ key: c.slug, label: c.name }))],
    [categories],
  );

  const appSearchText = (a: MarketplaceApp) =>
    `${a.name} ${a.description ?? ""} ${(a.tags ?? []).map((t) => t.name).join(" ")}`;

  const plazaFiltered = useMemo(
    () => filterBySearch(apps.items, search, appSearchText),
    [apps.items, search],
  );
  const installsFiltered = useMemo(
    () => filterBySearch(installs.items, search, (i) => i.app_name),
    [installs.items, search],
  );
  const myFiltered = useMemo(
    () => filterBySearch(myApps.items, search, appSearchText),
    [myApps.items, search],
  );
  const pendingFiltered = useMemo(
    () => filterBySearch(pendingApps.items, search, appSearchText),
    [pendingApps.items, search],
  );

  const plazaInstalledOnPage = useMemo(
    () => plazaFiltered.filter((a) => a.installed).length,
    [plazaFiltered],
  );

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
      setMsg(
        reviewMode === "off"
          ? "已上架"
          : reviewMode === "platform"
            ? "已提交，等待平台运营审核"
            : "已提交审核，通过后将在应用广场展示",
      );
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

  const renderRatingMeta = (app: MarketplaceApp) => (
    <span className="flex flex-col gap-2 text-xs">
      <span className="flex flex-wrap items-center gap-2">
        <MarketplaceStarDisplay value={app.rating_avg} count={app.rating_count} />
        <span className="text-ink-muted">
          v{app.version}
          {app.category_name && ` · ${app.category_name}`} · {app.install_count} 次安装
          {app.visibility && app.visibility !== "public"
            ? ` · ${marketplaceVisibilityLabel(app.visibility, marketplaceMeta)}`
            : ""}
        </span>
      </span>
      <TagChips tags={app.tags} />
    </span>
  );

  const renderAppActions = (app: MarketplaceApp, mode: "plaza" | "mine" | "review") => {
    if (mode === "plaza") {
      return (
        <CardActions
          actions={[
            { label: "详情", variant: "primary", onClick: () => void loadDetail(app.id) },
            {
              label: app.installed ? "已安装" : installing === app.id ? "安装中…" : "安装",
              onClick: () => void onInstall(app),
              disabled: app.installed || installing === app.id,
            },
            ...(app.installed || installing === app.id
              ? []
              : [{ label: "试用", onClick: () => void onTrial(app) }]),
          ]}
        />
      );
    }
    if (mode === "mine") {
      const actions: Parameters<typeof CardActions>[0]["actions"] = [
        { label: "详情", variant: "primary", onClick: () => void loadDetail(app.id) },
      ];
      if (app.status === "draft" || app.status === "rejected") {
        actions.push({
          label: publishing === app.id
            ? "提交中…"
            : app.status === "rejected"
              ? "重新提交审核"
              : "提交审核",
          onClick: () => void onSubmitReview(app.id),
          disabled: publishing === app.id,
        });
      }
      return <CardActions actions={actions} />;
    }
    return (
      <CardActions
        actions={[
          { label: "预览", variant: "primary", onClick: () => void loadDetail(app.id) },
          {
            label: reviewing === app.id ? "处理中…" : "通过",
            onClick: () => void onApprove(app.id),
            disabled: reviewing === app.id,
          },
          {
            label: "驳回",
            variant: "danger",
            onClick: () => onReject(app),
            disabled: reviewing === app.id,
          },
        ]}
      />
    );
  };

  const layoutCommon = {
    title: "应用市场",
    description: PAGE_DESC,
    tabs: mainTabs,
    activeTab: mainView,
    onTabChange: (k: string) => switchView(k as MainView),
  };

  const closeDetail = () => {
    setDetailAppId(null);
    setDetail(null);
  };

  const appDetailDrawer = (
    <MarketplaceAppDetailDrawer
      open={detailAppId !== null}
      loading={detailLoading}
      detail={detail}
      ratings={detailRatings}
      installingId={installing}
      rateScore={rateScore}
      rateComment={rateComment}
      rateSaving={rateSaving}
      marketplaceMeta={marketplaceMeta}
      onClose={closeDetail}
      onInstall={onInstall}
      onRateScoreChange={setRateScore}
      onRateCommentChange={setRateComment}
      onSaveRating={() => void onSaveRating()}
      onDeleteRating={() => void onDeleteRating()}
    />
  );

  const upgradeDialog = (
    <MarketplaceUpgradeDialog
      open={upgradeTarget !== null}
      loading={upgradePreviewLoading}
      preview={upgradePreview}
      upgrading={upgrading !== null}
      onClose={closeUpgradeDialog}
      onConfirm={() => void onConfirmUpgrade()}
    />
  );

  const pageOverlays = (
    <>
      {appDetailDrawer}
      {upgradeDialog}
    </>
  );

  if (mainView === "plaza") {
    return (
      <>
        <ResourceListLayout
          {...layoutCommon}
          searchPlaceholder="搜索应用名称、描述或标签"
          search={search}
          onSearchChange={setSearch}
          loading={apps.loading}
          headerAction={
            <div className="flex flex-wrap items-center gap-2">
              <TagFilterDropdown value={tagFilterIds} onChange={setTagFilterIds} />
              <select
                className="input-field w-auto shrink-0 text-sm"
                value={plazaSort}
                onChange={(e) => setPlazaSort(e.target.value as "installs" | "rating")}
                aria-label="排序方式"
              >
                {marketplaceCatalogSortOptions(marketplaceMeta).map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          }
          footer={
            !apps.loading ? (
              <ResourceListFooter
                page={apps.page}
                size={apps.size}
                total={apps.total}
                onPageChange={apps.setPage}
                onSizeChange={apps.setSize}
              />
            ) : null
          }
        >
          {msg && <PageMessage message={msg} onDismiss={() => setMsg("")} />}
          {lastResult && <InstallSuccessBanner result={lastResult} onDismiss={() => setLastResult(null)} />}
          <div className="col-span-full grid gap-3 sm:grid-cols-2">
            <StatChip label="广场应用" value={String(apps.total)} hint="已上架可安装" />
            <StatChip
              label="本页已安装"
              value={String(plazaInstalledOnPage)}
              hint={`本页共 ${plazaFiltered.length} 个`}
            />
          </div>
          <div className="col-span-full flex flex-wrap gap-2 border-b border-line pb-4">
            {categoryTabs.map((tab) => (
              <button
                key={tab.key || "all"}
                type="button"
                onClick={() => setActiveCategory(tab.key)}
                className={`rounded-lg px-3 py-1.5 text-xs transition ${
                  activeCategory === tab.key
                    ? "bg-brand-light font-medium text-brand"
                    : "text-ink-muted hover:bg-surface-muted hover:text-ink"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          {!apps.loading && plazaFiltered.length === 0 && (
            <p className="col-span-full py-12 text-center text-sm text-ink-faint">暂无匹配的应用</p>
          )}
          {plazaFiltered.map((app) => (
            <ResourceItemCard
              key={app.id}
              title={`${app.icon || "📦"} ${app.name}`}
              description={app.description ?? "应用模板"}
              badge={
                app.installed ? "已安装" : app.is_official ? "官方" : app.category_name || undefined
              }
              meta={renderRatingMeta(app)}
              onClick={() => void loadDetail(app.id)}
              actions={renderAppActions(app, "plaza")}
            />
          ))}
        </ResourceListLayout>
        {pageOverlays}
        <PromptDialog
          open={rejectTarget !== null}
          title="驳回应用"
          description="驳回原因将展示给发布方。"
          label="驳回原因（可选）"
          placeholder="请填写驳回原因"
          confirmLabel="确认驳回"
          destructive
          loading={rejectLoading}
          onClose={() => {
            if (!rejectLoading) setRejectTarget(null);
          }}
          onConfirm={onConfirmReject}
        />
      </>
    );
  }

  if (mainView === "installs") {
    return (
      <>
        <ResourceListLayout
          {...layoutCommon}
          searchPlaceholder="搜索已安装应用"
          search={search}
          onSearchChange={setSearch}
          loading={installs.loading}
          footer={
            !installs.loading ? (
              <ResourceListFooter
                page={installs.page}
                size={installs.size}
                total={installs.total}
                onPageChange={installs.setPage}
                onSizeChange={installs.setSize}
              />
            ) : null
          }
        >
          {msg && <PageMessage message={msg} onDismiss={() => setMsg("")} />}
          <div className="col-span-full grid gap-3 sm:grid-cols-2">
            <StatChip label="安装记录" value={String(installs.total)} hint="当前租户历史安装" />
            <StatChip label="本页展示" value={String(installsFiltered.length)} hint="受搜索筛选影响" />
          </div>
          {!installs.loading && installsFiltered.length === 0 && (
            <p className="col-span-full py-12 text-center text-sm text-ink-faint">
              尚未安装任何应用，请前往「应用广场」浏览
            </p>
          )}
          {installsFiltered.map((ins) => {
            const canUpgrade =
              ins.app_version &&
              ins.installed_version &&
              ins.app_version !== ins.installed_version;
            return (
            <ResourceItemCard
              key={ins.id}
              title={ins.app_name}
              description={`v${ins.installed_version ?? "?"} · 安装于 ${new Date(ins.created_at).toLocaleDateString("zh-CN")}${ins.app_version ? ` · 市场 v${ins.app_version}` : ""}`}
              badge={canUpgrade ? "可升级" : "已安装"}
              actions={
                <span className="flex flex-wrap items-center gap-3 text-xs">
                  {canUpgrade ? (
                    <button
                      type="button"
                      className="font-medium text-brand hover:underline disabled:opacity-50"
                      disabled={upgrading === ins.app_id}
                      onClick={() => void onOpenUpgrade(ins)}
                    >
                      {upgrading === ins.app_id ? "升级中…" : "升级到最新版"}
                    </button>
                  ) : null}
                  <span className="flex flex-wrap gap-3 text-brand">
                  {ins.kb_id && (
                    <Link href={`/workbench/kb/${ins.kb_id}`} className="hover:underline">
                      知识库
                    </Link>
                  )}
                  {ins.flow_id && (
                    <Link href={`/workbench/flows/${ins.flow_id}/edit`} className="hover:underline">
                      流程
                    </Link>
                  )}
                  {ins.agent_id && (
                    <Link href="/workbench/agents/chat" className="hover:underline">
                      智能体
                    </Link>
                  )}
                  </span>
                </span>
              }
            />
            );
          })}
        </ResourceListLayout>
        {pageOverlays}
      </>
    );
  }

  if (mainView === "mine") {
    return (
      <>
        <ResourceListLayout
          {...layoutCommon}
          searchPlaceholder="搜索应用名称、描述或标签"
          search={search}
          onSearchChange={setSearch}
          loading={myApps.loading}
          headerAction={
            <div className="flex flex-wrap items-center gap-2">
              <TagFilterDropdown value={tagFilterIds} onChange={setTagFilterIds} />
              <button type="button" className="btn-ghost shrink-0 text-sm" onClick={() => switchView("publish")}>
                新建打包
              </button>
            </div>
          }
          footer={
            !myApps.loading ? (
              <ResourceListFooter
                page={myApps.page}
                size={myApps.size}
                total={myApps.total}
                onPageChange={myApps.setPage}
                onSizeChange={myApps.setSize}
              />
            ) : null
          }
        >
          {msg && <PageMessage message={msg} onDismiss={() => setMsg("")} />}
          {!myApps.loading && myFiltered.length === 0 && (
            <p className="col-span-full py-12 text-center text-sm text-ink-faint">
              暂无草稿或上架记录，点击「新建打包」创建应用
            </p>
          )}
          {myFiltered.map((app) => (
            <ResourceItemCard
              key={app.id}
              title={`${app.icon || "📦"} ${app.name}`}
              description={
                app.status === "rejected" && app.review_note
                  ? `驳回：${app.review_note}`
                  : app.description ?? "租户应用"
              }
              badge={marketplaceStatusLabel(app.status, marketplaceMeta)}
              meta={renderRatingMeta(app)}
              onClick={() => void loadDetail(app.id)}
              actions={renderAppActions(app, "mine")}
            />
          ))}
        </ResourceListLayout>
        {pageOverlays}
        <PromptDialog
          open={rejectTarget !== null}
          title="驳回应用"
          description="驳回原因将展示给发布方。"
          label="驳回原因（可选）"
          placeholder="请填写驳回原因"
          confirmLabel="确认驳回"
          destructive
          loading={rejectLoading}
          onClose={() => {
            if (!rejectLoading) setRejectTarget(null);
          }}
          onConfirm={onConfirmReject}
        />
      </>
    );
  }

  if (mainView === "review" && showReviewTab) {
    return (
      <>
        <ResourceListLayout
          {...layoutCommon}
          searchPlaceholder="搜索应用名称、描述或标签"
          search={search}
          onSearchChange={setSearch}
          loading={pendingApps.loading}
          headerAction={<TagFilterDropdown value={tagFilterIds} onChange={setTagFilterIds} />}
          footer={
            !pendingApps.loading ? (
              <ResourceListFooter
                page={pendingApps.page}
                size={pendingApps.size}
                total={pendingApps.total}
                onPageChange={pendingApps.setPage}
                onSizeChange={pendingApps.setSize}
              />
            ) : null
          }
        >
          {msg && <PageMessage message={msg} onDismiss={() => setMsg("")} />}
          <div className="col-span-full">
            <StatChip
              label="待审核"
              value={String(pendingApps.total)}
              hint="通过后将在应用广场展示"
            />
          </div>
          <div className="col-span-full space-y-3">
            {!pendingApps.loading && pendingFiltered.length === 0 && (
              <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">
                暂无待审核应用
              </p>
            )}
            {pendingFiltered.map((app) => (
              <article
                key={app.id}
                className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-4 shadow-card sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-base font-semibold text-ink">
                      {app.icon || "📦"} {app.name}
                    </h3>
                    <span className="badge bg-amber-50 text-amber-800">待审核</span>
                    {app.category_name && (
                      <span className="text-xs text-ink-muted">{app.category_name}</span>
                    )}
                  </div>
                  <p className="mt-2 text-sm text-ink-muted line-clamp-2">
                    {app.description ?? "无描述"}
                  </p>
                  <div className="mt-2">
                    <TagChips tags={app.tags} />
                  </div>
                  <p className="mt-2 text-xs text-ink-faint">
                    提交于 {app.submitted_at ? new Date(app.submitted_at).toLocaleString("zh-CN") : "—"}
                  </p>
                </div>
                <div className="flex shrink-0 sm:min-w-[12rem]">{renderAppActions(app, "review")}</div>
              </article>
            ))}
          </div>
        </ResourceListLayout>
        {pageOverlays}
        <PromptDialog
          open={rejectTarget !== null}
          title="驳回应用"
          description="驳回原因将展示给发布方。"
          label="驳回原因（可选）"
          placeholder="请填写驳回原因"
          confirmLabel="确认驳回"
          destructive
          loading={rejectLoading}
          onClose={() => {
            if (!rejectLoading) setRejectTarget(null);
          }}
          onConfirm={onConfirmReject}
        />
      </>
    );
  }

  return (
    <>
      <ResourceListLayout
        {...layoutCommon}
        search=""
        onSearchChange={() => {}}
        showSearch={false}
      >
        {msg && <PageMessage message={msg} onDismiss={() => setMsg("")} />}
        <div className="col-span-full mx-auto w-full max-w-2xl">
          <section className="rounded-xl border border-line bg-surface p-6 shadow-panel">
            <h2 className="text-base font-semibold text-ink">从资源打包应用</h2>
            <p className="mt-1 text-sm text-ink-muted">
              选择本租户已有资源生成安装包草稿，提交审核通过后即可被其他租户安装。
            </p>
            <label className="mt-5 block space-y-1">
              <span className="text-xs text-ink-muted">应用名称</span>
              <input
                className="input-field w-full"
                value={publishName}
                onChange={(e) => setPublishName(e.target.value)}
                placeholder="例如：客服 RAG 套件"
              />
            </label>
            <label className="mt-3 block space-y-1">
              <span className="text-xs text-ink-muted">描述</span>
              <textarea
                className="input-field min-h-[88px] w-full resize-y"
                value={publishDesc}
                onChange={(e) => setPublishDesc(e.target.value)}
                placeholder="简要说明适用场景"
              />
            </label>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="block space-y-1">
                <span className="text-xs text-ink-muted">图标</span>
                <input
                  className="input-field w-full"
                  value={publishIcon}
                  onChange={(e) => setPublishIcon(e.target.value)}
                />
              </label>
              <label className="block space-y-1">
                <span className="text-xs text-ink-muted">分类</span>
                <select
                  className="input-field w-full"
                  value={publishCategory}
                  onChange={(e) => setPublishCategory(e.target.value)}
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.slug}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="mt-3 block space-y-1">
              <span className="text-xs text-ink-muted">可见范围</span>
              <select
                className="input-field w-full"
                value={publishVisibility}
                onChange={(e) =>
                  setPublishVisibility(e.target.value as "public" | "tenant_only")
                }
              >
                <option value="public">
                  {marketplaceVisibilityLabel("public", marketplaceMeta)}
                </option>
                <option value="tenant_only">
                  {marketplaceVisibilityLabel("tenant_only", marketplaceMeta)}
                </option>
              </select>
              <p className="text-[11px] text-ink-faint">
                「租户内可见」审核通过后仅本租户成员可在广场浏览与安装。
              </p>
            </label>
            <label className="mt-4 block space-y-1">
              <span className="text-xs text-ink-muted">标签</span>
              <TagPicker value={publishTagIds} onChange={setPublishTagIds} />
            </label>
            <p className="mt-5 text-xs font-medium text-ink-muted">关联资源（至少一项）</p>
            <div className="mt-2 space-y-2">
              <select
                className="input-field w-full"
                value={publishKbId}
                onChange={(e) => setPublishKbId(e.target.value)}
              >
                <option value="">不打包知识库</option>
                {resourceOptions.kbs.map((k) => (
                  <option key={k.id} value={k.id}>
                    知识库 · {k.name}
                  </option>
                ))}
              </select>
              <select
                className="input-field w-full"
                value={publishFlowId}
                onChange={(e) => setPublishFlowId(e.target.value)}
              >
                <option value="">不打包流程</option>
                {resourceOptions.flows.map((f) => (
                  <option key={f.id} value={f.id}>
                    流程 · {f.name}
                  </option>
                ))}
              </select>
              <select
                className="input-field w-full"
                value={publishAgentId}
                onChange={(e) => setPublishAgentId(e.target.value)}
              >
                <option value="">不打包智能体</option>
                {resourceOptions.agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    智能体 · {a.name}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              disabled={publishLoading}
              onClick={onCreateDraft}
              className="btn-primary mt-6 w-full"
            >
              {publishLoading ? "创建中…" : "保存为草稿"}
            </button>
          </section>
        </div>
      </ResourceListLayout>
      {pageOverlays}
    </>
  );
}
