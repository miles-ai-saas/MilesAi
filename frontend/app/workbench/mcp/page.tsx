"use client";

/**
 * MCP 服务管理页：Tab 筛选传输类型、卡片列表、同步/编辑/删除。
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
import { MCP_TRANSPORT_TABS, normalizeMcpTransport, type McpTransportTab } from "@/lib/mcp-labels";
import type { McpService } from "@/lib/types";

function parseStdioArgs(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function McpPage() {
  const { ready } = useRequireAuth();
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
    () => filterBySearch(list.items, search, (s) => `${s.name} ${s.description ?? ""} ${s.endpoint_url}`),
    [list.items, search],
  );

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

  /** 按传输类型组装 create/update 请求体。 */
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

  return (
    <>
      <ResourceListLayout
        title="MCP 服务"
        description="注册 Model Context Protocol 端点（HTTP / SSE / STDIO），同步远程工具列表；绑定到智能体后注入系统提示。"
        searchPlaceholder="搜索 MCP 服务名称或描述"
        search={search}
        onSearchChange={setSearch}
        tabs={MCP_TRANSPORT_TABS}
        activeTab={activeTab}
        onTabChange={(key) => setActiveTab(key as McpTransportTab)}
        loading={list.loading}
        headerAction={msg ? <span className="text-xs text-ink-muted">{msg}</span> : undefined}
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
        <McpCreateCard onAdd={openCreate} />
        {filtered.map((s) => (
          <McpServiceCard
            key={s.id}
            service={s}
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
