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
  Flow,
  KnowledgeBase,
  MarketplaceApp,
} from "@/lib/types";

type MainView = "plaza" | "mine" | "publish";

export default function MarketplacePage() {
  const { ready } = useRequireAuth();
  const [mainView, setMainView] = useState<MainView>("plaza");
  const [search, setSearch] = useState("");
  const [categories, setCategories] = useState<AppCategory[]>([]);
  const [activeCategory, setActiveCategory] = useState("");
  const [installing, setInstalling] = useState<string | null>(null);
  const [publishing, setPublishing] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<AppInstallResult | null>(null);
  const [msg, setMsg] = useState("");

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
    useCallback((p, s) => api.listMarketplaceApps(p, s, activeCategory || undefined), [activeCategory]),
    { enabled: ready && mainView === "plaza", resetKey: `${activeCategory}-plaza` },
  );
  const myApps = usePagedList(useCallback((p, s) => api.listMyMarketplaceApps(p, s), []), {
    enabled: ready && mainView === "mine",
    resetKey: "mine",
  });
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
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "安装失败");
    } finally {
      setInstalling(null);
    }
  };

  const onPublish = async (appId: string) => {
    setPublishing(appId);
    setMsg("");
    try {
      await api.publishMarketplaceApp(appId);
      setMsg("应用已上架，其他租户可在应用广场安装");
      await myApps.reload();
      await apps.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "上架失败");
    } finally {
      setPublishing(null);
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
      setMsg("草稿已创建，可在「我的上架」中发布");
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

  const mainTabs: { key: MainView; label: string }[] = [
    { key: "plaza", label: "应用广场" },
    { key: "mine", label: "我的上架" },
    { key: "publish", label: "打包上架" },
  ];

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-ink">应用市场</h1>
          <p className="mt-1 text-sm text-ink-muted">
            安装官方/租户上架模板，或将本租户知识库、流程、智能体打包发布。
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
              meta={
                <span>
                  v{app.version}
                  {app.category_name && ` · ${app.category_name}`} · {app.install_count} 次安装
                </span>
              }
              actions={
                <button
                  type="button"
                  disabled={app.installed || installing === app.id}
                  onClick={() => onInstall(app)}
                  className="btn-primary w-full py-1.5 text-xs disabled:opacity-50"
                >
                  {app.installed ? "已安装" : installing === app.id ? "安装中…" : "一键安装"}
                </button>
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
                description={app.description ?? "租户应用"}
                badge={marketplaceStatusLabel(app.status)}
                meta={<span>v{app.version} · {app.install_count} 次被安装</span>}
                actions={
                  app.status === "draft" ? (
                    <button
                      type="button"
                      disabled={publishing === app.id}
                      onClick={() => onPublish(app.id)}
                      className="btn-primary w-full py-1.5 text-xs"
                    >
                      {publishing === app.id ? "上架中…" : "发布到广场"}
                    </button>
                  ) : (
                    <span className="text-xs text-ink-faint">已在应用广场展示</span>
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

      {mainView === "publish" && (
        <section className="card mx-auto max-w-xl p-6">
          <h2 className="text-lg font-semibold text-ink">打包上架</h2>
          <p className="mt-1 text-sm text-ink-muted">
            选择本租户已有资源生成安装包（草稿），发布后即可被其他租户安装。
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
