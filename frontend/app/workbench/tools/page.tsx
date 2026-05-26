"use client";

/** 工具工作台（链路 §3 + §4）：目录/调用日志 + `useToolsMeta`。 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { TagFilterSelect } from "@/components/tag/TagFilterSelect";
import { TagManageDialog } from "@/components/tag/TagManageDialog";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { ToolCard } from "@/components/tool/ToolCard";
import { KbPageAlert } from "@/components/kb/KbPageAlert";
import { ToolCreateDialog, DEFAULT_SCRIPT, type ToolDialogMode } from "@/components/tool/ToolCreateDialog";
import { ToolDetailDialog } from "@/components/tool/ToolDetailDialog";
import { ToolTestDialog } from "@/components/tool/ToolTestDialog";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { usePagedList } from "@/hooks/use-paged-list";
import { useToolsMeta } from "@/hooks/use-tools-meta";
import { api, getApiErrorMessage } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { filterBySearch } from "@/lib/filter-search";
import {
  TOOL_PAGE_TABS,
  catalogSourceTabs,
  invocationStatusLabel,
  toolKindTabs,
  toolSourceLabel,
  type ToolKindTab,
  type ToolPageTab,
  type ToolSourceTab,
} from "@/lib/tool-labels";
import type { CustomTool, ToolCatalogItem, ToolInvocationLog, ToolParameterSpec, ToolsMeta } from "@/lib/types";

function slugFromName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 63);
}

const defaultParams = (): ToolParameterSpec[] => [];

const PAGE_DESC =
  "平台内置与自定义 HTTP / Python 脚本工具；供技能包引用与智能体 function calling。外部 MCP 服务请前往 MCP 工作台。";

const MAIN_TABS = TOOL_PAGE_TABS.map((t) => ({ key: t.key, label: t.label }));

function StatChip({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3 shadow-card">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-0.5 text-2xl font-bold tabular-nums text-brand">{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink-faint">{hint}</p> : null}
    </div>
  );
}

function FilterChip({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-xs transition ${
        active
          ? "bg-brand-light font-medium text-brand"
          : "text-ink-muted hover:bg-surface hover:text-ink"
      }`}
    >
      {label}
    </button>
  );
}

function LogStatusBadge({ status, toolsMeta }: { status: string; toolsMeta: ToolsMeta | null }) {
  const failed = status === "failed" || status === "error";
  const ok = status === "success" || status === "ok";
  return (
    <span
      className={`badge ${
        ok
          ? "bg-emerald-50 text-emerald-800"
          : failed
            ? "bg-red-50 text-red-700"
            : "bg-surface-muted text-ink-muted"
      }`}
    >
      {invocationStatusLabel(status, toolsMeta)}
    </span>
  );
}

function InvocationLogRow({ log, toolsMeta }: { log: ToolInvocationLog; toolsMeta: ToolsMeta | null }) {
  return (
    <article className="rounded-xl border border-line bg-surface p-4 shadow-card transition hover:border-brand/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium text-ink">{log.tool_slug}</h3>
            <LogStatusBadge status={log.status} toolsMeta={toolsMeta} />
            <span className="badge bg-brand-light text-brand">
              {toolSourceLabel(log.source, toolsMeta)}
            </span>
            <span className="text-xs text-ink-muted">{log.invoke_source}</span>
          </div>
          <p className="mt-2 text-xs text-ink-muted">
            {log.latency_ms != null ? `耗时 ${log.latency_ms} ms` : "—"}
          </p>
        </div>
        <time className="shrink-0 font-mono text-xs text-ink-faint">
          {new Date(log.created_at).toLocaleString("zh-CN")}
        </time>
      </div>
      {log.error_message && (
        <p className="mt-3 rounded-lg bg-red-50/80 px-3 py-2 text-xs text-red-700 line-clamp-3">
          {log.error_message}
        </p>
      )}
    </article>
  );
}

export default function ToolsPage() {
  const { ready } = useRequireAuth();
  const toolsMeta = useToolsMeta(ready);
  const [pageTab, setPageTab] = useState<ToolPageTab>("catalog");
  const [sourceTab, setSourceTab] = useState<ToolSourceTab>("");
  const [search, setSearch] = useState("");
  const [catalog, setCatalog] = useState<ToolCatalogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [tagFilterIds, setTagFilterIds] = useState<string[]>([]);
  const [tagManageOpen, setTagManageOpen] = useState(false);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<ToolDialogMode>("create");
  const [editing, setEditing] = useState<CustomTool | null>(null);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState("");

  const [toolKind, setToolKind] = useState<ToolKindTab>("http");
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [version, setVersion] = useState("1.0.0");
  const [requireConfirmation, setRequireConfirmation] = useState(false);
  const [parameters, setParameters] = useState<ToolParameterSpec[]>(defaultParams());
  const [url, setUrl] = useState("");
  const [method, setMethod] = useState("POST");
  const [headersJson, setHeadersJson] = useState("{}");
  const [bodyMode, setBodyMode] = useState<"json" | "none">("json");
  const [timeoutSec, setTimeoutSec] = useState(15);
  const [scriptSource, setScriptSource] = useState(DEFAULT_SCRIPT);

  const [testOpen, setTestOpen] = useState(false);
  const [testTool, setTestTool] = useState<ToolCatalogItem | null>(null);

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailTool, setDetailTool] = useState<ToolCatalogItem | null>(null);

  const { requestConfirm, confirmDialog } = useConfirmAction();

  const switchPageTab = (tab: ToolPageTab) => {
    setPageTab(tab);
    setSearch("");
  };

  const logList = usePagedList(
    useCallback((p, s) => api.listToolInvocationLogs(p, s), []),
    { enabled: ready && pageTab === "logs" },
  );

  const reloadCatalog = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await api.listToolCatalog(
        sourceTab || undefined,
        undefined,
        tagFilterIds.length ? tagFilterIds : undefined,
      );
      setCatalog(rows);
    } finally {
      setLoading(false);
    }
  }, [sourceTab, tagFilterIds]);

  useEffect(() => {
    if (!ready || pageTab !== "catalog") return;
    void reloadCatalog();
  }, [ready, pageTab, reloadCatalog]);

  const filtered = useMemo(
    () =>
      filterBySearch(
        catalog,
        search,
        (t) => `${t.name} ${t.slug} ${t.description ?? ""} ${t.source}`,
      ),
    [catalog, search],
  );

  const filteredLogs = useMemo(
    () =>
      filterBySearch(
        logList.items,
        search,
        (l) =>
          `${l.tool_slug} ${l.status} ${l.source} ${l.invoke_source} ${l.error_message ?? ""}`,
      ),
    [logList.items, search],
  );

  const catalogStats = useMemo(() => {
    let builtin = 0;
    let custom = 0;
    for (const t of catalog) {
      if (t.source === "builtin") builtin += 1;
      else if (t.source === "custom") custom += 1;
    }
    return { total: catalog.length, builtin, custom };
  }, [catalog]);

  const layoutCommon = {
    title: "工具",
    description: PAGE_DESC,
    tabs: MAIN_TABS,
    activeTab: pageTab,
    onTabChange: (k: string) => switchPageTab(k as ToolPageTab),
  };

  const resetForm = () => {
    setSlug("");
    setName("");
    setDescription("");
    setVersion("1.0.0");
    setRequireConfirmation(false);
    setParameters(defaultParams());
    setUrl("");
    setMethod("POST");
    setHeadersJson("{}");
    setBodyMode("json");
    setTimeoutSec(15);
    setScriptSource(DEFAULT_SCRIPT);
    setToolKind("http");
    setTagIds([]);
  };

  const openCreate = () => {
    setDialogMode("create");
    setEditing(null);
    resetForm();
    setSaveError("");
    setDialogOpen(true);
  };

  const openDetail = (item: ToolCatalogItem) => {
    setDetailTool(item);
    setDetailOpen(true);
  };

  const openEdit = async (item: ToolCatalogItem) => {
    if (!item.tool_id) return;
    const detail = (await api.listCustomTools(1, 100)).items.find((t) => t.id === item.tool_id);
    if (!detail) return;
    setDialogMode("edit");
    setSaveError("");
    setEditing(detail);
    setSlug(detail.slug);
    setName(detail.name);
    setDescription(detail.description ?? "");
    setTagIds((detail.tags ?? []).map((t) => t.id));
    setVersion(detail.version);
    setRequireConfirmation(detail.require_confirmation);
    setParameters(detail.parameters ?? []);
    setUrl(String((detail.config as { url?: string })?.url ?? ""));
    setMethod(String((detail.config as { method?: string })?.method ?? "POST"));
    setHeadersJson(JSON.stringify((detail.config as { headers?: object })?.headers ?? {}, null, 2));
    setBodyMode((detail.config as { body_mode?: string })?.body_mode === "none" ? "none" : "json");
    setTimeoutSec(Number((detail.config as { timeout_sec?: number })?.timeout_sec) || 15);
    setScriptSource(String((detail.config as { source?: string })?.source ?? DEFAULT_SCRIPT));
    setToolKind(detail.tool_type === "script" ? "script" : "http");
    setDialogOpen(true);
  };

  const onSave = async () => {
    if (!name.trim() || !slug.trim()) return;
    if (toolKind === "http" && !url.trim()) return;
    if (toolKind === "script" && !scriptSource.trim()) return;

    let headers: Record<string, string> = {};
    if (toolKind === "http") {
      try {
        headers = headersJson.trim() ? JSON.parse(headersJson) : {};
      } catch {
        alert("Headers JSON 格式错误");
        return;
      }
    }

    const payload = {
      slug: slug.trim(),
      name: name.trim(),
      description: description.trim() || null,
      tool_type: toolKind,
      category_id: null,
      tag_ids: tagIds,
      version: version.trim() || "1.0.0",
      require_confirmation: requireConfirmation,
      parameters: parameters.filter((p) => p.name.trim()),
      config:
        toolKind === "script"
          ? {
              language: "python",
              source: scriptSource,
              timeout_sec: timeoutSec,
            }
          : {
              url: url.trim(),
              method,
              headers,
              body_mode: bodyMode,
              timeout_sec: timeoutSec,
            },
    };
    setBusy(true);
    setSaveError("");
    try {
      if (dialogMode === "edit" && editing) {
        await api.updateCustomTool(editing.id, payload);
      } else {
        await api.createCustomTool(payload);
      }
      setDialogOpen(false);
      await reloadCatalog();
    } catch (e) {
      setSaveError(getApiErrorMessage(e, "保存失败"));
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

  const dialogs = (
    <>
      <ToolCreateDialog
        open={dialogOpen}
        mode={dialogMode}
        kindTabs={toolKindTabs(toolsMeta)}
        toolKind={toolKind}
        editing={editing}
        slug={slug}
        name={name}
        description={description}
        tagIds={tagIds}
        version={version}
        requireConfirmation={requireConfirmation}
        parameters={parameters}
        url={url}
        method={method}
        headersJson={headersJson}
        bodyMode={bodyMode}
        timeoutSec={timeoutSec}
        scriptSource={scriptSource}
        busy={busy}
        saveError={saveError}
        onClose={() => setDialogOpen(false)}
        onDismissError={() => setSaveError("")}
        onSubmit={onSave}
        onToolKindChange={setToolKind}
        onSlugChange={setSlug}
        onNameChange={(v) => {
          setName(v);
          if (dialogMode === "create") setSlug(slugFromName(v));
        }}
        onDescriptionChange={setDescription}
        onTagIdsChange={setTagIds}
        onVersionChange={setVersion}
        onRequireConfirmationChange={setRequireConfirmation}
        onParametersChange={setParameters}
        onUrlChange={setUrl}
        onMethodChange={setMethod}
        onHeadersJsonChange={setHeadersJson}
        onBodyModeChange={setBodyMode}
        onTimeoutSecChange={setTimeoutSec}
        onScriptSourceChange={setScriptSource}
      />
      <ToolDetailDialog
        open={detailOpen}
        item={detailTool}
        toolsMeta={toolsMeta}
        onClose={() => setDetailOpen(false)}
        onTest={
          detailTool
            ? () => {
                setTestTool(detailTool);
                setTestOpen(true);
              }
            : undefined
        }
        onEdit={
          detailTool?.source === "custom"
            ? () => {
                setDetailOpen(false);
                void openEdit(detailTool);
              }
            : undefined
        }
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

  if (pageTab === "logs") {
    return (
      <>
        <ResourceListLayout
          {...layoutCommon}
          searchPlaceholder="搜索工具编号、状态或错误信息"
          search={search}
          onSearchChange={setSearch}
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
          <div className="col-span-full grid gap-3 sm:grid-cols-2">
            <StatChip label="调用记录" value={String(logList.total)} hint="当前租户审计日志总数" />
            <StatChip label="本页展示" value={String(filteredLogs.length)} hint="受搜索筛选影响" />
          </div>
          <div className="col-span-full space-y-3">
            {!logList.loading && filteredLogs.length === 0 && (
              <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">
                暂无调用记录
              </p>
            )}
            {filteredLogs.map((log) => (
              <InvocationLogRow key={log.id} log={log} toolsMeta={toolsMeta} />
            ))}
          </div>
        </ResourceListLayout>
        {dialogs}
      </>
    );
  }

  return (
    <>
      <ResourceListLayout
        {...layoutCommon}
        searchPlaceholder="搜索工具名称、编号或描述"
        search={search}
        onSearchChange={setSearch}
        loading={loading}
        headerAction={
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="btn-ghost shrink-0 text-sm"
              disabled={loading}
              onClick={() => void reloadCatalog()}
            >
              {loading ? "刷新中…" : "刷新"}
            </button>
            <TagFilterSelect value={tagFilterIds} onChange={setTagFilterIds} />
            <button
              type="button"
              className="btn-ghost border border-line text-sm"
              onClick={() => setTagManageOpen(true)}
            >
              管理标签
            </button>
          </div>
        }
      >
        <div className="col-span-full rounded-xl border border-brand/20 bg-brand-light/30 px-4 py-3 text-xs text-brand">
          外部 MCP 工具不在此列表展示，请前往{" "}
          <a href="/workbench/mcp" className="font-medium underline">
            MCP 工作台
          </a>
          。
        </div>

        <div className="col-span-full grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <StatChip label="工具总数" value={String(catalogStats.total)} hint="当前筛选条件下" />
          <StatChip label="内置" value={String(catalogStats.builtin)} />
          <StatChip
            label="自定义"
            value={String(catalogStats.custom)}
            hint={`本页展示 ${filtered.length} 个`}
          />
        </div>

        <div className="col-span-full rounded-xl border border-line bg-surface-muted/40 p-4">
          <p className="mb-2 text-xs font-medium text-ink-muted">来源</p>
          <div className="flex flex-wrap gap-2">
            {catalogSourceTabs(toolsMeta).map((tab) => (
              <FilterChip
                key={tab.key || "all"}
                active={sourceTab === tab.key}
                label={tab.label}
                onClick={() => setSourceTab(tab.key)}
              />
            ))}
          </div>
        </div>

        {sourceTab !== "builtin" && (
          <AddResourceCard
            label="添加新工具"
            hint="创建 HTTP 工具扩展智能体能力"
            onClick={openCreate}
          />
        )}

        {!loading && filtered.length === 0 && (
          <p className="col-span-full py-12 text-center text-sm text-ink-faint">
            暂无匹配的工具，可调整筛选或创建自定义工具
          </p>
        )}

        {filtered.map((t) => (
          <ToolCard
            key={`${t.source}-${t.slug}-${t.tool_id ?? ""}`}
            tool={t}
            toolsMeta={toolsMeta}
            onDetail={() => openDetail(t)}
            onTest={() => {
              setTestTool(t);
              setTestOpen(true);
            }}
            onEdit={t.source === "custom" ? () => void openEdit(t) : undefined}
            onDelete={t.source === "custom" ? () => onDelete(t) : undefined}
          />
        ))}
      </ResourceListLayout>
      {dialogs}
    </>
  );
}
