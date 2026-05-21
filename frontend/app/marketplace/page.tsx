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
import type { AppCategory, AppInstallResult, MarketplaceApp } from "@/lib/types";

export default function MarketplacePage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [categories, setCategories] = useState<AppCategory[]>([]);
  const [activeCategory, setActiveCategory] = useState("");
  const [installing, setInstalling] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<AppInstallResult | null>(null);
  const [msg, setMsg] = useState("");

  const apps = usePagedList(
    useCallback((p, s) => api.listMarketplaceApps(p, s, activeCategory || undefined), [activeCategory]),
    { enabled: ready, resetKey: activeCategory },
  );
  const installs = usePagedList(useCallback((p, s) => api.listAppInstalls(p, s), []), {
    enabled: ready,
  });

  useEffect(() => {
    if (!ready) return;
    api.listMarketplaceCategories().then(setCategories);
  }, [ready]);

  const tabs: ResourceTab[] = useMemo(
    () => [{ key: "", label: "全部" }, ...categories.map((c) => ({ key: c.slug, label: c.name }))],
    [categories],
  );

  const filtered = useMemo(
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

  return (
    <div className="space-y-10">
      <ResourceListLayout
        title="应用市场"
        description="一键安装官方 RAG、流程与智能体模板到当前租户，快速搭建业务能力。"
        searchPlaceholder="搜索应用名称"
        search={search}
        onSearchChange={setSearch}
        tabs={tabs}
        activeTab={activeCategory}
        onTabChange={setActiveCategory}
        loading={apps.loading}
        headerAction={msg ? <span className="text-xs text-ink-muted">{msg}</span> : undefined}
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
        {filtered.map((app) => (
          <ResourceItemCard
            key={app.id}
            title={`${app.icon || "📦"} ${app.name}`}
            description={app.description ?? "官方应用模板"}
            badge={app.installed ? "已安装" : app.is_official ? "官方" : undefined}
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

      {lastResult && (
        <div className="resource-page-shell rounded-xl border border-emerald-200 bg-emerald-50 p-5 text-sm text-emerald-900">
          <p className="font-medium">安装完成</p>
          <ul className="mt-2 space-y-1 text-xs">
            {lastResult.kb_id && (
              <li>
                知识库 →{" "}
                <Link href={`/kb/${lastResult.kb_id}`} className="underline">
                  管理文档
                </Link>
              </li>
            )}
            {lastResult.flow_id && (
              <li>
                流程 →{" "}
                <Link href={`/flows/${lastResult.flow_id}/edit`} className="underline">
                  编辑画布
                </Link>
              </li>
            )}
            {lastResult.agent_id && (
              <li>
                智能体 →{" "}
                <Link href="/agents/chat" className="underline">
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
                    <Link href={`/kb/${ins.kb_id}`} className="hover:underline">
                      知识库
                    </Link>
                  )}
                  {ins.flow_id && (
                    <Link href={`/flows/${ins.flow_id}/edit`} className="hover:underline">
                      流程
                    </Link>
                  )}
                  {ins.agent_id && (
                    <Link href="/agents/chat" className="hover:underline">
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
