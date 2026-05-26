"use client";

/**
 * MCP 服务管理页（链路 §11，见 lib/chains.ts）：传输类型筛选、卡片列表、同步/编辑/删除。
 * SSE 类型 endpoint 应填 GET 长连接地址（如 /sse），由后端 legacy_sse 客户端处理。
 */

import { useCallback, useMemo, useState } from "react";
import { McpCreateCard } from "@/components/mcp/McpCreateCard";
import { McpServiceCard } from "@/components/mcp/McpServiceCard";
import { McpServiceDialog } from "@/components/mcp/McpServiceDialog";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { usePagedList } from "@/hooks/use-paged-list";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { filterBySearch } from "@/lib/filter-search";
import {
  mcpTransportFilterOptions,
  mcpTransportLabel,
  normalizeMcpTransport,
  type McpTransportTab,
} from "@/lib/mcp-labels";
import { useMcpMeta } from "@/hooks/use-mcp-meta";
import type { McpService } from "@/lib/types";

function parseStdioArgs(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

const PAGE_DESC =
  "注册 Model Context Protocol 端点（HTTP / SSE / STDIO），同步远程工具列表；绑定到智能体后注入系统提示。SSE 请填写 GET 长连接地址。";

function StatChip({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3 shadow-card">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-0.5 text-2xl font-bold tabular-nums text-brand">{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink-faint line-clamp-2">{hint}</p> : null}
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

export default function McpPage() {
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
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [endpointUrl, setEndpointUrl] = useState("http://127.0.0.1:3001/mcp");
  const [stdioCommand, setStdioCommand] = useState("npx");
  const [stdioArgs, setStdioArgs] = useState("");
  const [busy, setBusy] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const list = usePagedList(
    useCallback(
      (p, s) => api.listMcpServices(p, s, activeTab || undefined),
      [activeTab],
    ),
    { enabled: ready, resetKey: activeTab },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const filtered = useMemo(
    () =>
      filterBySearch(
        list.items,
        search,
        (s) =>
          `${s.name} ${s.description ?? ""} ${s.endpoint_url} ${mcpTransportLabel(s.transport, mcpMeta)}`,
      ),
    [list.items, search, mcpMeta],
  );

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
    setEndpointUrl(transport === "http" ? "https://" : "http://127.0.0.1:3001/mcp");
    setStdioCommand("npx");
    setStdioArgs("");
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
    setDialogOpen(true);
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
    setMsg("");
    try {
      const payload = buildPayload();
      if (dialogMode === "create") {
        await api.createMcpService(payload);
        setMsg("已创建，请点击「同步工具」拉取 tools/list");
      } else if (editing) {
        await api.updateMcpService(editing.id, payload);
        setMsg("已保存");
      }
      setDialogOpen(false);
      await list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  const onSync = async (id: string) => {
    setMsg("");
    try {
      const res = await api.syncMcpService(id);
      setMsg(`已同步 ${res.tools.length} 个工具`);
      await list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "同步失败");
      await list.reload();
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
        if (expandedId === s.id) setExpandedId(null);
        await list.reload();
      },
    });
  };

  const activeTabLabel =
    transportTabs.find((t) => t.value === activeTab)?.label ?? "全部";
  const layoutTabs = useMemo(
    () => transportTabs.map((t) => ({ key: t.value, label: t.label })),
    [transportTabs],
  );

  return (
    <>
      <ResourceListLayout
        title="MCP 服务"
        description={PAGE_DESC}
        searchPlaceholder="搜索服务名称、描述或端点"
        search={search}
        onSearchChange={setSearch}
        tabs={layoutTabs}
        activeTab={activeTab}
        onTabChange={onTabChange}
        loading={list.loading}
        headerAction={
          <button
            type="button"
            className="btn-ghost shrink-0 text-sm"
            disabled={list.loading}
            onClick={() => void list.reload()}
          >
            {list.loading ? "刷新中…" : "刷新"}
          </button>
        }
        footer={
          !list.loading ? (
            <ResourceListFooter
              page={list.page}
              size={list.size}
              total={list.total}
              onPageChange={list.setPage}
            />
          ) : null
        }
      >
        {msg && <PageMessage message={msg} onDismiss={() => setMsg("")} />}

        <div className="col-span-full grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatChip label="服务总数" value={String(list.total)} hint={`当前筛选：${activeTabLabel}`} />
          <StatChip
            label="本页已同步"
            value={String(pageStats.synced)}
            hint={`同步失败 ${pageStats.warn}（当前页）`}
          />
          <StatChip label="本页工具数" value={String(pageStats.tools)} hint="已缓存 tools/list" />
          <StatChip label="本页展示" value={String(filtered.length)} hint="受搜索筛选影响" />
        </div>

        <McpCreateCard onAdd={openCreate} />

        {!list.loading && filtered.length === 0 && (
          <p className="col-span-full py-12 text-center text-sm text-ink-faint">
            暂无匹配的 MCP 服务，可通过左侧卡片添加 HTTP / SSE / STDIO
          </p>
        )}

        {filtered.map((s) => (
          <McpServiceCard
            key={s.id}
            service={s}
            mcpMeta={mcpMeta}
            toolsExpanded={expandedId === s.id}
            onSync={() => onSync(s.id)}
            onEdit={() => openEdit(s)}
            onDelete={() => onDelete(s)}
            onToggleTools={() => setExpandedId(expandedId === s.id ? null : s.id)}
          />
        ))}
      </ResourceListLayout>

      <McpServiceDialog
        open={dialogOpen}
        mode={dialogMode}
        transport={dialogTransport}
        editing={editing}
        name={name}
        description={description}
        endpointUrl={endpointUrl}
        stdioCommand={stdioCommand}
        stdioArgs={stdioArgs}
        busy={busy}
        onClose={() => setDialogOpen(false)}
        onSubmit={onSubmit}
        onNameChange={setName}
        onDescriptionChange={setDescription}
        onEndpointUrlChange={setEndpointUrl}
        onStdioCommandChange={setStdioCommand}
        onStdioArgsChange={setStdioArgs}
      />
      {confirmDialog}
    </>
  );
}
