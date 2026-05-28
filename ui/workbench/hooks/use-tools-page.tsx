"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { DEFAULT_SCRIPT, type ToolDialogMode } from "@/components/tool/ToolCreateDialog";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { usePagedList } from "@/hooks/use-paged-list";
import { useToolsMeta } from "@/hooks/use-tools-meta";
import { api, getApiErrorMessage } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { filterBySearch } from "@/lib/filter-search";
import { TOOLS_MAIN_TABS, TOOLS_PAGE_DESC, defaultToolParams, slugFromName } from "@/lib/tool-page-shared";
import { toolKindTabs, type ToolKindTab, type ToolPageTab, type ToolSourceTab } from "@/lib/tool-labels";
import type { CustomTool, ToolCatalogItem, ToolParameterSpec } from "@/lib/types";

export function useToolsPage() {
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
  const [parameters, setParameters] = useState<ToolParameterSpec[]>(defaultToolParams());
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
      const rows = await api.listToolCatalog(sourceTab || undefined, undefined, tagFilterIds.length ? tagFilterIds : undefined);
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
    () => filterBySearch(catalog, search, (t) => `${t.name} ${t.slug} ${t.description ?? ""} ${t.source}`),
    [catalog, search],
  );

  const filteredLogs = useMemo(
    () =>
      filterBySearch(logList.items, search, (l) => `${l.tool_slug} ${l.status} ${l.source} ${l.invoke_source} ${l.error_message ?? ""}`),
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

  const resetForm = () => {
    setSlug("");
    setName("");
    setDescription("");
    setVersion("1.0.0");
    setRequireConfirmation(false);
    setParameters(defaultToolParams());
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
    const res = await api.invokeTool(testTool.slug, params, testTool.tool_id || undefined, confirmed);
    if (res.status === "confirmation_required" && res.pending) {
      return `__CONFIRM__:工具「${res.pending.name}」需要确认。\n参数：${JSON.stringify(res.pending.params, null, 2)}`;
    }
    return JSON.stringify(res.output, null, 2);
  };

  const openTest = (tool: ToolCatalogItem) => {
    setTestTool(tool);
    setTestOpen(true);
  };

  const layoutCommon = {
    title: "工具",
    description: TOOLS_PAGE_DESC,
    tabs: TOOLS_MAIN_TABS,
    activeTab: pageTab,
    onTabChange: (k: string) => switchPageTab(k as ToolPageTab),
  };

  return {
    layoutCommon,
    toolsMeta,
    pageTab,
    switchPageTab,
    sourceTab,
    setSourceTab,
    search,
    setSearch,
    catalog,
    loading,
    tagFilterIds,
    setTagFilterIds,
    tagManageOpen,
    setTagManageOpen,
    dialogOpen,
    setDialogOpen,
    dialogMode,
    editing,
    busy,
    saveError,
    setSaveError,
    toolKind,
    setToolKind,
    slug,
    setSlug,
    name,
    setName,
    description,
    setDescription,
    tagIds,
    setTagIds,
    version,
    setVersion,
    requireConfirmation,
    setRequireConfirmation,
    parameters,
    setParameters,
    url,
    setUrl,
    method,
    setMethod,
    headersJson,
    setHeadersJson,
    bodyMode,
    setBodyMode,
    timeoutSec,
    setTimeoutSec,
    scriptSource,
    setScriptSource,
    testOpen,
    setTestOpen,
    testTool,
    detailOpen,
    setDetailOpen,
    detailTool,
    confirmDialog,
    logList,
    filtered,
    filteredLogs,
    catalogStats,
    reloadCatalog,
    openCreate,
    openDetail,
    openEdit,
    onSave,
    onDelete,
    runTest,
    openTest,
    kindTabs: toolKindTabs(toolsMeta),
    onNameChange: (v: string) => {
      setName(v);
      if (dialogMode === "create") setSlug(slugFromName(v));
    },
  };
}

export type ToolsPageVm = ReturnType<typeof useToolsPage>;
