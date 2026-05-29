"use client";

import { useState } from "react";
import { MCP_ENDPOINT_PLACEHOLDER } from "@/features/mcp/components/mcp-dialog-shared";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { api } from "@/lib/api";
import { normalizeMcpTransport, type McpTransportTab } from "@/features/mcp/lib/mcp-labels";
import { parseStdioArgs } from "@/features/mcp/lib/mcp-page-shared";
import type { McpService } from "@/lib/types";
import type { McpListSlice } from "@/features/mcp/hooks/use-mcp-list";

type ViewingSlice = {
  viewing: McpService | null;
  setViewing: (s: McpService | null) => void;
  setDetailOpen: (open: boolean) => void;
};

export function useMcpForm(listSlice: McpListSlice, viewingSlice: ViewingSlice) {
  const { list, setMsg } = listSlice;
  const { viewing, setViewing, setDetailOpen } = viewingSlice;
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [dialogTransport, setDialogTransport] = useState<Exclude<McpTransportTab, "">>("http");
  const [editing, setEditing] = useState<McpService | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [endpointUrl, setEndpointUrl] = useState("https://");
  const [stdioCommand, setStdioCommand] = useState("npx");
  const [stdioArgs, setStdioArgs] = useState("");
  const [busy, setBusy] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [saveError, setSaveError] = useState("");

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

  return {
    dialogOpen,
    setDialogOpen,
    dialogMode,
    dialogTransport,
    editing,
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
    onDialogTransportChange,
    onSubmit,
    onSync,
    onDelete,
  };
}
