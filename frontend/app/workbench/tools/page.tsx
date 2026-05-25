"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useCategoryTabs } from "@/components/category/useCategoryTabs";
import { TagFilterSelect } from "@/components/tag/TagFilterSelect";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { ToolCard } from "@/components/tool/ToolCard";
import { ToolCreateDialog, type ToolDialogMode } from "@/components/tool/ToolCreateDialog";
import { ToolTestDialog } from "@/components/tool/ToolTestDialog";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { usePagedList } from "@/hooks/use-paged-list";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { filterBySearch } from "@/lib/filter-search";
import {
  TOOL_PAGE_TABS,
  TOOL_SOURCE_TABS,
  type ToolPageTab,
  type ToolSourceTab,
} from "@/lib/tool-labels";
import type { CustomTool, ToolCatalogItem, ToolParameterSpec } from "@/lib/types";

function slugFromName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 63);
}

const defaultParams = (): ToolParameterSpec[] => [];

export default function ToolsPage() {
  const { ready } = useRequireAuth();
  const [pageTab, setPageTab] = useState<ToolPageTab>("catalog");
  const [sourceTab, setSourceTab] = useState<ToolSourceTab>("");
  const [search, setSearch] = useState("");
  const [catalog, setCatalog] = useState<ToolCatalogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const cat = useCategoryTabs("tool");
  const [tagFilterIds, setTagFilterIds] = useState<string[]>([]);
  const [tagManageOpen, setTagManageOpen] = useState(false);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<ToolDialogMode>("create");
  const [editing, setEditing] = useState<CustomTool | null>(null);
  const [busy, setBusy] = useState(false);

  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [version, setVersion] = useState("1.0.0");
  const [requireConfirmation, setRequireConfirmation] = useState(false);
  const [parameters, setParameters] = useState<ToolParameterSpec[]>(defaultParams());
  const [url, setUrl] = useState("");
  const [method, setMethod] = useState("POST");
  const [headersJson, setHeadersJson] = useState("{}");

  const [testOpen, setTestOpen] = useState(false);
  const [testTool, setTestTool] = useState<ToolCatalogItem | null>(null);

  const { requestConfirm, confirmDialog } = useConfirmAction();

  const logList = usePagedList(
    useCallback((p, s) => api.listToolInvocationLogs(p, s), []),
    { enabled: ready && pageTab === "logs" },
  );

  const reloadCatalog = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await api.listToolCatalog(
        sourceTab || undefined,
        cat.activeCategoryId,
        tagFilterIds.length ? tagFilterIds : undefined,
      );
      setCatalog(rows);
    } finally {
      setLoading(false);
    }
  }, [sourceTab, cat.activeCategoryId, tagFilterIds]);

  useEffect(() => {
    if (!ready) return;
    void reloadCatalog();
  }, [ready, reloadCatalog]);

  const filtered = useMemo(
    () =>
      filterBySearch(
        catalog,
        search,
        (t) =>
          `${t.name} ${t.slug} ${t.description ?? ""} ${t.category_name ?? ""} ${t.source}`,
      ),
    [catalog, search],
  );

  const resetForm = () => {
    setSlug("");
    setName("");
    setDescription("");
    setCategoryId(cat.activeId || "");
    setVersion("1.0.0");
    setRequireConfirmation(false);
    setParameters(defaultParams());
    setUrl("");
    setMethod("POST");
    setHeadersJson("{}");
    setTagIds([]);
  };

  const openCreate = () => {
    setDialogMode("create");
    setEditing(null);
    resetForm();
    setDialogOpen(true);
  };

  const openEdit = async (item: ToolCatalogItem) => {
    if (!item.tool_id) return;
    const detail = (await api.listCustomTools(1, 100)).items.find((t) => t.id === item.tool_id);
    if (!detail) return;
    setDialogMode("edit");
    setEditing(detail);
    setSlug(detail.slug);
    setName(detail.name);
    setDescription(detail.description ?? "");
    setCategoryId(detail.category_id ?? "");
    setTagIds((detail.tags ?? []).map((t) => t.id));
    setVersion(detail.version);
    setRequireConfirmation(detail.require_confirmation);
    setParameters(detail.parameters ?? []);
    setUrl(String((detail.config as { url?: string })?.url ?? ""));
    setMethod(String((detail.config as { method?: string })?.method ?? "POST"));
    setHeadersJson(JSON.stringify((detail.config as { headers?: object })?.headers ?? {}, null, 2));
    setDialogOpen(true);
  };

  const onSave = async () => {
    if (!name.trim() || !slug.trim() || !url.trim()) return;
    let headers: Record<string, string> = {};
    try {
      headers = headersJson.trim() ? JSON.parse(headersJson) : {};
    } catch {
      alert("Headers JSON 格式错误");
      return;
    }
    const payload = {
      slug: slug.trim(),
      name: name.trim(),
      description: description.trim() || null,
      category_id: categoryId || null,
      tag_ids: tagIds,
      version: version.trim() || "1.0.0",
      require_confirmation: requireConfirmation,
      parameters: parameters.filter((p) => p.name.trim()),
      config: { url: url.trim(), method, headers, body_mode: "json", timeout_sec: 15 },
    };
    setBusy(true);
    try {
      if (dialogMode === "edit" && editing) {
        await api.updateCustomTool(editing.id, payload);
      } else {
        await api.createCustomTool(payload);
      }
      setDialogOpen(false);
      await reloadCatalog();
    } finally {
      setBusy(false);
    }
  };

  const onDelete = (item: ToolCatalogItem) => {
    if (!item.tool_id) return;
    requestConfirm({
      title: "删除工具",
      message: (
        <>
          确定删除工具 <span className="font-medium">{item.name}</span>？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteCustomTool(item.tool_id!);
        await reloadCatalog();
      },
    });
  };

  const runTest = async (params: Record<string, unknown>, confirmed: boolean) => {
    if (!testTool) return "";
    if (testTool.source === "mcp" && testTool.mcp_service_name) {
      const mcpList = await api.listMcpServices(1, 100);
      const svc = mcpList.items.find((s) => s.name === testTool.mcp_service_name);
      if (!svc) throw new Error("未找到 MCP 服务");
      const res = await api.invokeMcpTool(svc.id, testTool.slug, params);
      return JSON.stringify(res.output, null, 2);
    }
    const res = await api.invokeTool(
      testTool.slug,
      params,
      testTool.tool_id || undefined,
      confirmed,
    );
    if (res.status === "confirmation_required" && res.pending) {
      return `__CONFIRM__:工具「${res.pending.name}」需要确认。\n参数：${JSON.stringify(res.pending.params, null, 2)}`;
    }
    return JSON.stringify(res.output, null, 2);
  };

  const sourceTabs = TOOL_SOURCE_TABS.map((t) => ({ key: t.key, label: t.label }));
  const mainTabs = TOOL_PAGE_TABS.map((t) => ({ key: t.key, label: t.label }));
  const categoryTabs = cat.tabs.map((t) => ({ key: t.key, label: t.label }));

  if (pageTab === "logs") {
    return (
      <>
        <ResourceListLayout
          title="工具"
          description="查看工具试调用与智能体执行的审计记录。"
          searchPlaceholder="搜索工具编号"
          search={search}
          onSearchChange={setSearch}
          tabs={mainTabs}
          activeTab={pageTab}
          onTabChange={(k) => setPageTab(k as ToolPageTab)}
          loading={logList.loading}
          footer={
            !logList.loading ? (
              <ResourceListFooter
                page={logList.page}
                size={logList.size}
                total={logList.total}
                onPageChange={logList.setPage}
              />
            ) : null
          }
        >
          {filterBySearch(logList.items, search, (l) => l.tool_slug).map((log) => (
            <article key={log.id} className="resource-card text-xs">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="font-medium text-ink">{log.tool_slug}</h3>
                  <p className="mt-1 text-ink-muted">
                    {log.status} · {log.source} · {log.invoke_source}
                    {log.latency_ms ? ` · ${log.latency_ms}ms` : ""}
                  </p>
                </div>
                <span className="text-ink-faint">
                  {new Date(log.created_at).toLocaleString("zh-CN")}
                </span>
              </div>
              {log.error_message && (
                <p className="mt-2 text-red-600 line-clamp-2">{log.error_message}</p>
              )}
            </article>
          ))}
        </ResourceListLayout>
      </>
    );
  }

  return (
    <>
      <ResourceListLayout
        title="工具"
        description="内置工具、自定义 HTTP 与 MCP 同步工具的统一目录，可供技能包与智能体引用。"
        searchPlaceholder="搜索工具名称或编号"
        search={search}
        onSearchChange={setSearch}
        tabs={mainTabs}
        activeTab={pageTab}
        onTabChange={(k) => setPageTab(k as ToolPageTab)}
        loading={loading}
        headerAction={
          <div className="flex items-center gap-4">
            <div className="flex gap-2 text-xs">
              {sourceTabs.map((tab) => (
                <button
                  key={tab.key || "all"}
                  type="button"
                  onClick={() => setSourceTab(tab.key as ToolSourceTab)}
                  className={`rounded-lg px-2 py-1 ${
                    sourceTab === tab.key
                      ? "bg-brand-light font-medium text-brand"
                      : "text-ink-muted"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <TagFilterSelect value={tagFilterIds} onChange={setTagFilterIds} />
            <button
              type="button"
              className="text-sm text-brand hover:underline"
              onClick={() => setTagManageOpen(true)}
            >
              管理标签
            </button>
          </div>
        }
      >
        <div className="col-span-full mb-2 flex flex-wrap gap-2">
          {categoryTabs.map((tab) => (
            <button
              key={tab.key || "all"}
              type="button"
              onClick={() => cat.setActiveId(tab.key)}
              className={`rounded-lg px-3 py-1 text-xs ${
                cat.activeId === tab.key
                  ? "bg-brand-light font-medium text-brand"
                  : "text-ink-muted hover:bg-surface-muted"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {sourceTab !== "builtin" && (
          <AddResourceCard
            label="添加新工具"
            hint="创建 HTTP 工具扩展智能体能力"
            onClick={openCreate}
          />
        )}

        {filtered.map((t) => (
          <ToolCard
            key={`${t.source}-${t.slug}-${t.tool_id ?? ""}`}
            tool={t}
            onTest={() => {
              setTestTool(t);
              setTestOpen(true);
            }}
            onEdit={t.source === "custom" ? () => void openEdit(t) : undefined}
            onDelete={t.source === "custom" ? () => onDelete(t) : undefined}
          />
        ))}
      </ResourceListLayout>

      <ToolCreateDialog
        open={dialogOpen}
        mode={dialogMode}
        editing={editing}
        categories={cat.categories}
        slug={slug}
        name={name}
        description={description}
        categoryId={categoryId}
        tagIds={tagIds}
        version={version}
        requireConfirmation={requireConfirmation}
        parameters={parameters}
        url={url}
        method={method}
        headersJson={headersJson}
        busy={busy}
        onClose={() => setDialogOpen(false)}
        onSubmit={onSave}
        onSlugChange={setSlug}
        onNameChange={(v) => {
          setName(v);
          if (dialogMode === "create") setSlug(slugFromName(v));
        }}
        onDescriptionChange={setDescription}
        onCategoryIdChange={setCategoryId}
        onTagIdsChange={setTagIds}
        onVersionChange={setVersion}
        onRequireConfirmationChange={setRequireConfirmation}
        onParametersChange={setParameters}
        onUrlChange={setUrl}
        onMethodChange={setMethod}
        onHeadersJsonChange={setHeadersJson}
      />

      <ToolTestDialog
        open={testOpen}
        tool={testTool}
        onClose={() => setTestOpen(false)}
        onRun={runTest}
      />

      <TagManageDialog open={tagManageOpen} onClose={() => setTagManageOpen(false)} />

      {confirmDialog}
    </>
  );
}
