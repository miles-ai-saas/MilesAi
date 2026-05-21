"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout, type ResourceTab } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import { marketplaceStatusLabel } from "@/lib/marketplace-status";
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

type MainView = "plaza" | "mine" | "publish" | "review";

function StarDisplay({ value, count }: { value: number; count?: number }) {
  const full = Math.round(value);
  return (
    <span className="inline-flex items-center gap-0.5 text-amber-500" title={`${value.toFixed(1)} 分`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={i <= full ? "" : "opacity-25"}>
          ★
        </span>
      ))}
      {count !== undefined && (
        <span className="ml-1 text-xs text-ink-faint">({count})</span>
      )}
    </span>
  );
}

export default function MarketplacePage() {
  const { ready, user } = useRequireAuth();
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

  const apps = usePagedList(
    useCallback(
      (p, s) => api.listMarketplaceApps(p, s, activeCategory || undefined, plazaSort),
      [activeCategory, plazaSort],
    ),
    { enabled: ready && mainView === "plaza", resetKey: `${activeCategory}-${plazaSort}-plaza` },
  );
  const myApps = usePagedList(useCallback((p, s) => api.listMyMarketplaceApps(p, s), []), {
    enabled: ready && mainView === "mine",
    resetKey: "mine",
  });
  const pendingApps = usePagedList(
    useCallback((p, s) => api.listPendingMarketplaceApps(p, s), []),
    { enabled: ready && mainView === "review" && canReview, resetKey: "pending" },
  );
  const installs = usePagedList(useCallback((p, s) => api.listAppInstalls(p, s), []), {
    enabled: ready,
  });

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
      await installs.reload();
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

  const onReject = async (app: MarketplaceApp) => {
    const note = window.prompt("驳回原因（将展示给发布方）", "");
    if (note === null) return;
    setReviewing(app.id);
    setMsg("");
    try {
      await api.rejectMarketplaceApp(app.id, note || undefined);
      setMsg("已驳回该应用");
      await pendingApps.reload();
      await myApps.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "驳回失败");
    } finally {
      setReviewing(null);
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
      setMainView("mine");
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

  const mainTabs: { key: MainView; label: string }[] = [
    { key: "plaza", label: "应用广场" },
    { key: "mine", label: "我的上架" },
    { key: "publish", label: "打包上架" },
    ...(canReview ? [{ key: "review" as const, label: "上架审核" }] : []),
  ];

  const renderRatingMeta = (app: MarketplaceApp) => (
    <span className="flex flex-wrap items-center gap-2">
      <StarDisplay value={app.rating_avg} count={app.rating_count} />
      <span>
        v{app.version}
        {app.category_name && ` · ${app.category_name}`} · {app.install_count} 次安装
      </span>
    </span>
  );

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-ink">应用市场</h1>
          <p className="mt-1 text-sm text-ink-muted">
            安装已审核上架的应用；租户打包后需审核通过方可进入广场；安装后可评分。
          </p>
        </div>
        <div className="flex rounded-lg border border-line bg-surface p-0.5">
          {mainTabs.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => {
                setMainView(t.key);
                setMsg("");
              }}
              className={`rounded-md px-3 py-1.5 text-sm transition ${
                mainView === t.key
                  ? "bg-brand-light font-medium text-brand"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {msg && (
        <p className="rounded-lg border border-line bg-brand-light/50 px-4 py-2 text-sm text-ink">
          {msg}
        </p>
      )}

      {mainView === "plaza" && (
        <ResourceListLayout
          title="应用广场"
          description="浏览已上架应用，一键安装到当前租户。"
          searchPlaceholder="搜索应用名称"
          search={search}
          onSearchChange={setSearch}
          tabs={categoryTabs}
          activeTab={activeCategory}
          onTabChange={setActiveCategory}
          loading={apps.loading}
          headerAction={
            <select
              className="input-field w-auto text-sm"
              value={plazaSort}
              onChange={(e) => setPlazaSort(e.target.value as "installs" | "rating")}
            >
              <option value="installs">按安装量</option>
              <option value="rating">按评分</option>
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
          {plazaFiltered.map((app) => (
            <ResourceItemCard
              key={app.id}
              title={`${app.icon || "📦"} ${app.name}`}
              description={app.description ?? "应用模板"}
              badge={
                app.installed
                  ? "已安装"
                  : app.is_official
                    ? "官方"
                    : app.category_name || undefined
              }
              meta={renderRatingMeta(app)}
              actions={
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
              }
            />
          ))}
        </ResourceListLayout>
      )}

      {mainView === "mine" && (
        <div className="resource-page-shell">
          <h2 className="mb-4 text-lg font-semibold text-ink">我的上架</h2>
          <div className="resource-card-grid">
            {myApps.loading && <p className="text-sm text-ink-muted">加载中…</p>}
            {!myApps.loading && myApps.items.length === 0 && (
              <p className="col-span-full py-8 text-center text-sm text-ink-faint">
                暂无草稿，前往「打包上架」创建
              </p>
            )}
            {myApps.items.map((app) => (
              <ResourceItemCard
                key={app.id}
                title={`${app.icon || "📦"} ${app.name}`}
                description={
                  app.status === "rejected" && app.review_note
                    ? `驳回：${app.review_note}`
                    : app.description ?? "租户应用"
                }
                badge={marketplaceStatusLabel(app.status)}
                meta={renderRatingMeta(app)}
                actions={
                  app.status === "draft" || app.status === "rejected" ? (
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
                  ) : app.status === "pending_review" ? (
                    <span className="text-xs text-ink-faint">等待平台审核</span>
                  ) : app.status === "published" ? (
                    <span className="text-xs text-ink-faint">已在应用广场展示</span>
                  ) : (
                    <span className="text-xs text-ink-faint">{marketplaceStatusLabel(app.status)}</span>
                  )
                }
              />
            ))}
          </div>
          {!myApps.loading && (
            <ResourceListFooter
              className="mt-4"
              page={myApps.page}
              size={myApps.size}
              total={myApps.total}
              onPageChange={myApps.setPage}
            />
          )}
        </div>
      )}

      {mainView === "review" && canReview && (
        <div className="resource-page-shell">
          <h2 className="mb-1 text-lg font-semibold text-ink">上架审核</h2>
          <p className="mb-4 text-sm text-ink-muted">审核租户提交的应用，通过后将在广场展示。</p>
          <div className="resource-card-grid">
            {pendingApps.loading && <p className="text-sm text-ink-muted">加载中…</p>}
            {!pendingApps.loading && pendingApps.items.length === 0 && (
              <p className="col-span-full py-8 text-center text-sm text-ink-faint">暂无待审核应用</p>
            )}
            {pendingApps.items.map((app) => (
              <ResourceItemCard
                key={app.id}
                title={`${app.icon || "📦"} ${app.name}`}
                description={app.description ?? "待审核应用"}
                badge="待审核"
                meta={
                  <span>
                    提交于 {app.submitted_at?.slice(0, 16) ?? "—"}
                    {app.category_name && ` · ${app.category_name}`}
                  </span>
                }
                actions={
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
                }
              />
            ))}
          </div>
          {!pendingApps.loading && (
            <ResourceListFooter
              className="mt-4"
              page={pendingApps.page}
              size={pendingApps.size}
              total={pendingApps.total}
              onPageChange={pendingApps.setPage}
            />
          )}
        </div>
      )}

      {mainView === "publish" && (
        <section className="card mx-auto max-w-xl p-6">
          <h2 className="text-lg font-semibold text-ink">打包上架</h2>
          <p className="mt-1 text-sm text-ink-muted">
            选择本租户已有资源生成安装包（草稿），提交审核通过后即可被其他租户安装。
          </p>
          <label className="mb-1 mt-5 block text-sm font-medium text-ink">应用名称</label>
          <input
            className="input-field"
            value={publishName}
            onChange={(e) => setPublishName(e.target.value)}
            placeholder="例如：客服 RAG 套件"
          />
          <label className="mb-1 mt-3 block text-sm font-medium text-ink">描述</label>
          <textarea
            className="input-field min-h-[72px]"
            value={publishDesc}
            onChange={(e) => setPublishDesc(e.target.value)}
            placeholder="简要说明适用场景"
          />
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="text-sm text-ink-muted">
              图标
              <input
                className="input-field mt-1"
                value={publishIcon}
                onChange={(e) => setPublishIcon(e.target.value)}
              />
            </label>
            <label className="text-sm text-ink-muted">
              分类
              <select
                className="input-field mt-1"
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
          <label className="mb-1 mt-4 block text-sm font-medium text-ink">关联资源（至少一项）</label>
          <div className="space-y-2">
            <select
              className="input-field"
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
              className="input-field"
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
              className="input-field"
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
            className="btn-primary mt-5 w-full"
          >
            {publishLoading ? "创建中…" : "保存为草稿"}
          </button>
        </section>
      )}

      {detailAppId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal
        >
          <div className="card max-h-[90vh] w-full max-w-lg overflow-y-auto p-6">
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-lg font-semibold text-ink">
                {detailLoading ? "加载中…" : detail ? `${detail.icon || "📦"} ${detail.name}` : "应用详情"}
              </h2>
              <button
                type="button"
                className="text-ink-muted hover:text-ink"
                onClick={() => {
                  setDetailAppId(null);
                  setDetail(null);
                }}
              >
                关闭
              </button>
            </div>
            {detail && !detailLoading && (
              <>
                <p className="mt-2 text-sm text-ink-muted">{detail.description ?? "无描述"}</p>
                <div className="mt-3">
                  <StarDisplay value={detail.rating_avg} count={detail.rating_count} />
                </div>
                {detail.installed ? (
                  <div className="mt-4 rounded-lg border border-line p-4">
                    <p className="text-sm font-medium text-ink">我的评分</p>
                    <div className="mt-2 flex gap-1">
                      {[1, 2, 3, 4, 5].map((s) => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => setRateScore(s)}
                          className={`text-xl ${s <= rateScore ? "text-amber-500" : "text-ink-faint"}`}
                        >
                          ★
                        </button>
                      ))}
                    </div>
                    <textarea
                      className="input-field mt-2 min-h-[60px] text-sm"
                      placeholder="可选评价内容"
                      value={rateComment}
                      onChange={(e) => setRateComment(e.target.value)}
                    />
                    <div className="mt-2 flex gap-2">
                      <button
                        type="button"
                        disabled={rateSaving}
                        onClick={onSaveRating}
                        className="btn-primary text-xs"
                      >
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
                  <div className="mt-4">
                    <p className="text-sm font-medium text-ink">用户评价</p>
                    <ul className="mt-2 space-y-2 text-sm">
                      {detailRatings.map((r) => (
                        <li key={r.id} className="rounded border border-line px-3 py-2">
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
          </div>
        </div>
      )}

      {lastResult && mainView === "plaza" && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 text-sm text-emerald-900">
          <p className="font-medium">安装完成</p>
          <ul className="mt-2 space-y-1 text-xs">
            {lastResult.kb_id && (
              <li>
                知识库 →{" "}
                <Link href={`/workbench/kb/${lastResult.kb_id}`} className="underline">
                  管理文档
                </Link>
              </li>
            )}
            {lastResult.flow_id && (
              <li>
                流程 →{" "}
                <Link href={`/workbench/flows/${lastResult.flow_id}/edit`} className="underline">
                  编辑画布
                </Link>
              </li>
            )}
            {lastResult.agent_id && (
              <li>
                智能体 →{" "}
                <Link href="/workbench/agents/chat" className="underline">
                  去对话
                </Link>
              </li>
            )}
          </ul>
        </div>
      )}

      <div className="resource-page-shell">
        <h2 className="mb-4 text-lg font-semibold text-ink">我的安装</h2>
        <div className="resource-card-grid">
          {installs.loading && <p className="text-sm text-ink-muted">加载中…</p>}
          {!installs.loading && installs.items.length === 0 && (
            <p className="col-span-full py-8 text-center text-sm text-ink-faint">尚未安装任何应用</p>
          )}
          {installs.items.map((ins) => (
            <ResourceItemCard
              key={ins.id}
              title={ins.app_name}
              description={`安装于 ${ins.created_at.slice(0, 10)}`}
              actions={
                <span className="flex flex-wrap gap-2 text-xs text-brand">
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
        </div>
        {!installs.loading && (
          <ResourceListFooter
            className="mt-4"
            page={installs.page}
            size={installs.size}
            total={installs.total}
            onPageChange={installs.setPage}
          />
        )}
      </div>
    </div>
  );
}
