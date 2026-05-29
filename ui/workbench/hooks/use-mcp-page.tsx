"use client";

import { useCallback, useMemo, useState } from "react";
import { MCP_ENDPOINT_PLACEHOLDER } from "@/components/mcp/mcp-dialog-shared";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { usePagedList } from "@/hooks/use-paged-list";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { filterBySearch } from "@/lib/filter-search";
import { mcpTransportFilterOptions, mcpTransportLabel, normalizeMcpTransport, type McpTransportTab } from "@/lib/mcp-labels";
import { useMcpMeta } from "@/hooks/use-mcp-meta";
import { parseStdioArgs } from "@/lib/mcp-page-shared";
import type { McpService } from "@/lib/types";

export function useMcpPage() {
  const { ready } = useRequireAuth();
  const mcpMeta = useMcpMeta(ready);
  const transportTabs = mcpTransportFilterOptions(mcpMeta);
  const [activeTab, setActiveTab] = useState<McpTransportTab>("");
  const [search, setSearch] = useState("");
  const [msg, setMsg] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [dialogTransport, setDialogTransport] = useState<Exclude<McpTransportTab, "">>("http");
  const [editing, setEditing] = useState<McpService | null>(null);
  const [viewing, setViewing] = useState<McpService | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [endpointUrl, setEndpointUrl] = useState("https://");
  const [stdioCommand, setStdioCommand] = useState("npx");
  const [stdioArgs, setStdioArgs] = useState("");
  const [busy, setBusy] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [saveError, setSaveError] = useState("");

  const list = usePagedList(useCallback((p, s) => api.listMcpServices(p, s, activeTab || undefined), [activeTab]), {
    enabled: ready,
    resetKey: activeTab,
  });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (s) => `${s.name} ${s.description ?? ""} ${s.endpoint_url} ${mcpTransportLabel(s.transport, mcpMeta)}`),
    [list.items, search, mcpMeta],
  );

  const viewingLive = useMemo(() => {
    if (!viewing) return null;
    return list.items.find((s) => s.id === viewing.id) ?? viewing;
  }, [viewing, list.items]);

  const pageStats = useMemo(() => {
    let synced = 0;
    let warn = 0;
    let tools = 0;
    for (const s of list.items) {
      if (s.sync_error) warn += 1;
      else if (s.last_sync_at && (s.tools_cache?.length ?? 0) > 0) synced += 1;
      tools += s.tools_cache?.length ?? 0;
    }
    return { synced, warn, tools };
  }, [list.items]);

  const onTabChange = (key: string) => {
    setActiveTab(key as McpTransportTab);
    setSearch("");
  };

  const resetForm = (transport: Exclude<McpTransportTab, "">) => {
    setName("");
    setDescription("");
    setDialogTransport(transport);
    setEndpointUrl(MCP_ENDPOINT_PLACEHOLDER[transport] || "https://");
    setStdioCommand("npx");
    setStdioArgs("");
    setSaveError("");
  };

  const openCreate = (transport: Exclude<McpTransportTab, "">) => {
    setDialogMode("create");
    setEditing(null);
    resetForm(transport);
    setDialogOpen(true);
  };

  const openEdit = (s: McpService) => {
    const t = normalizeMcpTransport(s.transport);
    setDialogMode("edit");
    setEditing(s);
    setDialogTransport(t);
    setName(s.name);
    setDescription(s.description ?? "");
    setEndpointUrl(s.endpoint_url.startsWith("stdio://") ? "" : s.endpoint_url);
    setStdioCommand(String(s.connection_config?.command ?? ""));
    const args = s.connection_config?.args;
    setStdioArgs(Array.isArray(args) ? args.map(String).join("\n") : "");
    setSaveError("");
    setDetailOpen(false);
    setDialogOpen(true);
  };

  const openDetail = (s: McpService) => {
    setViewing(s);
    setDetailOpen(true);
  };

  const onDialogTransportChange = (t: Exclude<McpTransportTab, "">) => {
    if (dialogMode !== "create") return;
    setDialogTransport(t);
    if (!endpointUrl.trim() || endpointUrl === MCP_ENDPOINT_PLACEHOLDER[dialogTransport]) {
      setEndpointUrl(MCP_ENDPOINT_PLACEHOLDER[t] || "");
    }
  };

  const buildPayload = () => {
    const t = editing ? normalizeMcpTransport(editing.transport) : dialogTransport;
    const trimmedName = name.trim() || "MCP";
    if (t === "stdio") {
      return {
        name: trimmedName,
        transport: "stdio",
        description: description.trim() || undefined,
        connection_config: {
          command: stdioCommand.trim(),
          args: parseStdioArgs(stdioArgs),
        },
      };
    }
    return {
      name: trimmedName,
      transport: t,
      endpoint_url: endpointUrl.trim(),
      description: description.trim() || undefined,
      connection_config: { endpoint_url: endpointUrl.trim() },
    };
  };

  const onSubmit = async () => {
    setBusy(true);
    setSaveError("");
    try {
      const payload = buildPayload();
      if (dialogMode === "create") {
        await api.createMcpService(payload);
        setMsg("已创建，请在详情中点击「同步工具」拉取 tools/list");
      } else if (editing) {
        await api.updateMcpService(editing.id, payload);
        setMsg("已保存");
      }
      setDialogOpen(false);
      await list.reload();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  const onSync = async (id: string) => {
    setMsg("");
    setSyncingId(id);
    try {
      const res = await api.syncMcpService(id);
      setMsg(`已同步 ${res.tools.length} 个工具`);
      await list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "同步失败");
      await list.reload();
    } finally {
      setSyncingId(null);
    }
  };

  const onDelete = (s: McpService) => {
    requestConfirm({
      title: "删除 MCP 服务",
      message: (
        <>
          确定删除 MCP 服务 <span className="font-medium">{s.name}</span>？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteMcpService(s.id);
        if (viewing?.id === s.id) {
          setDetailOpen(false);
          setViewing(null);
        }
        await list.reload();
      },
    });
  };

  const activeTabLabel = transportTabs.find((t) => t.value === activeTab)?.label ?? "全部";
  const layoutTabs = useMemo(() => transportTabs.map((t) => ({ key: t.value, label: t.label })), [transportTabs]);

  return {
    mcpMeta,
    activeTab,
    onTabChange,
    search,
    setSearch,
    msg,
    setMsg,
    list,
    filtered,
    pageStats,
    activeTabLabel,
    layoutTabs,
    dialogOpen,
    setDialogOpen,
    dialogMode,
    dialogTransport,
    editing,
    viewingLive,
    detailOpen,
    setDetailOpen,
    name,
    setName,
    description,
    setDescription,
    endpointUrl,
    setEndpointUrl,
    stdioCommand,
    setStdioCommand,
    stdioArgs,
    setStdioArgs,
    busy,
    syncingId,
    saveError,
    setSaveError,
    confirmDialog,
    openCreate,
    openEdit,
    openDetail,
    onDialogTransportChange,
    onSubmit,
    onSync,
    onDelete,
  };
}

export type McpPageVm = ReturnType<typeof useMcpPage>;
