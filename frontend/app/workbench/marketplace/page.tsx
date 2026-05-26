"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout, type ResourceTab } from "@/components/resource/ResourceListLayout";
import { PromptDialog } from "@/components/resource/PromptDialog";
import { filterBySearch } from "@/lib/filter-search";
import {
  marketplaceCatalogSortOptions,
  marketplaceStatusLabel,
} from "@/lib/marketplace-labels";
import { useMarketplaceMeta } from "@/hooks/use-marketplace-meta";
import type {
  Agent,
  AppCategory,
  AppInstallResult,
  AppRating,
  Flow,
  KnowledgeBase,
  MarketplaceApp,
  MarketplaceAppDetail,
} from "@/lib/types";

type MainView = "plaza" | "installs" | "mine" | "publish" | "review";

const PAGE_DESC =
  "浏览并安装已审核上架的应用；可将本租户知识库、流程或智能体打包为应用，审核通过后供其他租户安装。";

function StarDisplay({ value, count }: { value: number; count?: number }) {
  const full = Math.round(value);
  return (
    <span className="inline-flex items-center gap-0.5 text-amber-500" title={`${value.toFixed(1)} 分`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={i <= full ? "" : "opacity-25"}>
          ★
        </span>
      ))}
      {count !== undefined && <span className="ml-1 text-xs text-ink-faint">({count})</span>}
    </span>
  );
}

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
  const canReview = Boolean(
    user?.is_superuser || user?.permissions?.includes("marketplace:review"),
  );
  const [mainView, setMainView] = useState<MainView>("plaza");
  const [plazaSort, setPlazaSort] = useState<"installs" | "rating">("installs");
  const [search, setSearch] = useState("");
  const [categories, setCategories] = useState<AppCategory[]>([]);
  const [activeCategory, setActiveCategory] = useState("");
  const [installing, setInstalling] = useState<string | null>(null);
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
      ...(canReview ? [{ key: "review", label: "上架审核" }] : []),
    ],
    [canReview],
  );

  const switchView = (view: MainView) => {
    setMainView(view);
    setSearch("");
    setMsg("");
  };

  const apps = usePagedList(
    useCallback(
      (p, s) => api.listMarketplaceApps(p, s, activeCategory || undefined, plazaSort),
      [activeCategory, plazaSort],
    ),
    { enabled: ready && mainView === "plaza", resetKey: `${activeCategory}-${plazaSort}-plaza` },
  );
  const installs = usePagedList(useCallback((p, s) => api.listAppInstalls(p, s), []), {
    enabled: ready && mainView === "installs",
    resetKey: "installs",
  });
  const myApps = usePagedList(useCallback((p, s) => api.listMyMarketplaceApps(p, s), []), {
    enabled: ready && mainView === "mine",
    resetKey: "mine",
  });
  const pendingApps = usePagedList(
    useCallback((p, s) => api.listPendingMarketplaceApps(p, s), []),
    { enabled: ready && mainView === "review" && canReview, resetKey: "pending" },
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

  const plazaFiltered = useMemo(
    () => filterBySearch(apps.items, search, (a) => `${a.name} ${a.description ?? ""}`),
    [apps.items, search],
  );
  const installsFiltered = useMemo(
    () => filterBySearch(installs.items, search, (i) => i.app_name),
    [installs.items, search],
  );
  const myFiltered = useMemo(
    () => filterBySearch(myApps.items, search, (a) => `${a.name} ${a.description ?? ""}`),
    [myApps.items, search],
  );
  const pendingFiltered = useMemo(
    () => filterBySearch(pendingApps.items, search, (a) => `${a.name} ${a.description ?? ""}`),
    [pendingApps.items, search],
  );

  const plazaInstalledOnPage = useMemo(
    () => plazaFiltered.filter((a) => a.installed).length,
    [plazaFiltered],
  );

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

  const onSubmitReview = async (appId: string) => {
    setPublishing(appId);
    setMsg("");
    try {
      await api.publishMarketplaceApp(appId);
      setMsg("已提交审核，通过后将在应用广场展示");
      await myApps.reload();
      if (canReview) await pendingApps.reload();
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
      });
      setMsg("草稿已创建，可在「我的上架」中提交审核");
      setPublishName("");
      setPublishDesc("");
      setPublishKbId("");
      setPublishFlowId("");
      setPublishAgentId("");
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
    <span className="flex flex-wrap items-center gap-2 text-xs">
      <StarDisplay value={app.rating_avg} count={app.rating_count} />
      <span className="text-ink-muted">
        v{app.version}
        {app.category_name && ` · ${app.category_name}`} · {app.install_count} 次安装
      </span>
    </span>
  );

  const renderAppActions = (app: MarketplaceApp, mode: "plaza" | "mine" | "review") => {
    if (mode === "plaza") {
      return (
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={() => loadDetail(app.id)}
            className="btn-secondary w-full py-1.5 text-xs"
          >
            详情与评价
          </button>
          <button
            type="button"
            disabled={app.installed || installing === app.id}
            onClick={() => onInstall(app)}
            className="btn-primary w-full py-1.5 text-xs disabled:opacity-50"
          >
            {app.installed ? "已安装" : installing === app.id ? "安装中…" : "一键安装"}
          </button>
        </div>
      );
    }
    if (mode === "mine") {
      if (app.status === "draft" || app.status === "rejected") {
        return (
          <button
            type="button"
            disabled={publishing === app.id}
            onClick={() => onSubmitReview(app.id)}
            className="btn-primary w-full py-1.5 text-xs"
          >
            {publishing === app.id
              ? "提交中…"
              : app.status === "rejected"
                ? "重新提交审核"
                : "提交审核"}
          </button>
        );
      }
      if (app.status === "pending_review") {
        return <span className="text-xs text-ink-faint">等待平台审核</span>;
      }
      if (app.status === "published") {
        return <span className="text-xs text-ink-faint">已在应用广场展示</span>;
      }
      return (
        <span className="text-xs text-ink-faint">
          {marketplaceStatusLabel(app.status, marketplaceMeta)}
        </span>
      );
    }
    return (
      <div className="flex gap-2">
        <button
          type="button"
          disabled={reviewing === app.id}
          onClick={() => onApprove(app.id)}
          className="btn-primary flex-1 py-1.5 text-xs"
        >
          通过
        </button>
        <button
          type="button"
          disabled={reviewing === app.id}
          onClick={() => onReject(app)}
          className="btn-secondary flex-1 py-1.5 text-xs"
        >
          驳回
        </button>
      </div>
    );
  };

  const layoutCommon = {
    title: "应用市场",
    description: PAGE_DESC,
    tabs: mainTabs,
    activeTab: mainView,
    onTabChange: (k: string) => switchView(k as MainView),
  };

  const detailDialog = (
    <ResourceDialog
      open={detailAppId !== null}
      title={
        detailLoading
          ? "加载中…"
          : detail
            ? `${detail.icon || "📦"} ${detail.name}`
            : "应用详情"
      }
      size="lg"
      onClose={() => {
        setDetailAppId(null);
        setDetail(null);
      }}
    >
      {detail && !detailLoading && (
        <>
          <p className="text-sm leading-relaxed text-ink-muted">{detail.description ?? "无描述"}</p>
          <div className="mt-2">
            <StarDisplay value={detail.rating_avg} count={detail.rating_count} />
          </div>
          {detail.installed ? (
            <div className="mt-4 rounded-xl border border-line bg-surface-muted p-4">
              <p className="text-sm font-medium text-ink">我的评分</p>
              <div className="mt-2 flex gap-1">
                {[1, 2, 3, 4, 5].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setRateScore(s)}
                    className={`text-xl transition ${s <= rateScore ? "text-amber-500" : "text-ink-faint"}`}
                  >
                    ★
                  </button>
                ))}
              </div>
              <textarea
                className="input-field mt-2 min-h-[72px] w-full text-sm"
                placeholder="可选评价内容"
                value={rateComment}
                onChange={(e) => setRateComment(e.target.value)}
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" disabled={rateSaving} onClick={onSaveRating} className="btn-primary text-xs">
                  {rateSaving ? "保存中…" : "保存评分"}
                </button>
                {detail.my_rating && (
                  <button
                    type="button"
                    disabled={rateSaving}
                    onClick={onDeleteRating}
                    className="btn-secondary text-xs"
                  >
                    删除评分
                  </button>
                )}
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm text-ink-faint">安装后可对该应用评分</p>
          )}
          {!detail.installed && detail.status === "published" && (
            <button
              type="button"
              className="btn-primary mt-4 w-full"
              disabled={installing === detail.id}
              onClick={() => onInstall(detail)}
            >
              {installing === detail.id ? "安装中…" : "一键安装"}
            </button>
          )}
          {detailRatings.length > 0 && (
            <div className="mt-5">
              <p className="text-sm font-medium text-ink">用户评价</p>
              <ul className="mt-2 max-h-48 space-y-2 overflow-y-auto text-sm">
                {detailRatings.map((r) => (
                  <li key={r.id} className="rounded-lg border border-line px-3 py-2">
                    <StarDisplay value={r.score} />
                    {r.comment && <p className="mt-1 text-ink-muted">{r.comment}</p>}
                    <p className="mt-1 text-xs text-ink-faint">{r.created_at.slice(0, 10)}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
      {detailLoading && <p className="py-8 text-center text-sm text-ink-muted">加载应用详情…</p>}
    </ResourceDialog>
  );

  if (mainView === "plaza") {
    return (
      <>
        <ResourceListLayout
          {...layoutCommon}
          searchPlaceholder="搜索应用名称或描述"
          search={search}
          onSearchChange={setSearch}
          loading={apps.loading}
          headerAction={
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
          }
          footer={
            !apps.loading ? (
              <ResourceListFooter
                page={apps.page}
                size={apps.size}
                total={apps.total}
                onPageChange={apps.setPage}
              />
            ) : null
          }
        >
          {msg && <PageMessage message={msg} onDismiss={() => setMsg("")} />}
          {lastResult && <InstallSuccessBanner result={lastResult} onDismiss={() => setLastResult(null)} />}
          <div className="col-span-full grid gap-3 sm:grid-cols-3">
            <StatChip label="广场应用" value={String(apps.total)} hint="已上架可安装" />
            <StatChip
              label="本页已安装"
              value={String(plazaInstalledOnPage)}
              hint={`本页共 ${plazaFiltered.length} 个`}
            />
            <StatChip
              label="排序"
              value={plazaSort === "installs" ? "安装量" : "评分"}
              hint="可在右上角切换"
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
              actions={renderAppActions(app, "plaza")}
            />
          ))}
        </ResourceListLayout>
        {detailDialog}
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
          {installsFiltered.map((ins) => (
            <ResourceItemCard
              key={ins.id}
              title={ins.app_name}
              description={`安装于 ${new Date(ins.created_at).toLocaleDateString("zh-CN")}`}
              badge="已安装"
              actions={
                <span className="flex flex-wrap gap-3 text-xs text-brand">
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
              }
            />
          ))}
        </ResourceListLayout>
        {detailDialog}
      </>
    );
  }

  if (mainView === "mine") {
    return (
      <>
        <ResourceListLayout
          {...layoutCommon}
          searchPlaceholder="搜索我的应用"
          search={search}
          onSearchChange={setSearch}
          loading={myApps.loading}
          headerAction={
            <button type="button" className="btn-ghost shrink-0 text-sm" onClick={() => switchView("publish")}>
              新建打包
            </button>
          }
          footer={
            !myApps.loading ? (
              <ResourceListFooter
                page={myApps.page}
                size={myApps.size}
                total={myApps.total}
                onPageChange={myApps.setPage}
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
              actions={renderAppActions(app, "mine")}
            />
          ))}
        </ResourceListLayout>
        {detailDialog}
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

  if (mainView === "review" && canReview) {
    return (
      <>
        <ResourceListLayout
          {...layoutCommon}
          searchPlaceholder="搜索待审核应用"
          search={search}
          onSearchChange={setSearch}
          loading={pendingApps.loading}
          footer={
            !pendingApps.loading ? (
              <ResourceListFooter
                page={pendingApps.page}
                size={pendingApps.size}
                total={pendingApps.total}
                onPageChange={pendingApps.setPage}
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
                  <p className="mt-2 text-xs text-ink-faint">
                    提交于 {app.submitted_at ? new Date(app.submitted_at).toLocaleString("zh-CN") : "—"}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2 sm:w-48">{renderAppActions(app, "review")}</div>
              </article>
            ))}
          </div>
        </ResourceListLayout>
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
      {detailDialog}
    </>
  );
}
