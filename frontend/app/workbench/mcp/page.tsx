"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import type { McpService } from "@/lib/types";

export default function McpPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [endpoint, setEndpoint] = useState("http://127.0.0.1:3001/mcp");
  const [transport, setTransport] = useState("sse");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  const list = usePagedList(useCallback((p, s) => api.listMcpServices(p, s), []), { enabled: ready });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (s) => `${s.name} ${s.endpoint_url}`),
    [list.items, search],
  );

  const onCreate = async () => {
    await api.createMcpService(name || "MCP", endpoint, transport);
    setName("");
    setDialogOpen(false);
    setMsg("已注册，请点击「同步工具」拉取 tools/list");
    await list.reload();
  };

  const onSync = async (id: string) => {
    setMsg("");
    try {
      const res = await api.syncMcpService(id);
      setMsg(`已同步 ${res.tools.length} 个工具`);
      await list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "同步失败");
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
        await list.reload();
      },
    });
  };

  return (
    <>
      <ResourceListLayout
        title="MCP 服务"
        description="注册 Model Context Protocol 端点，同步远程工具列表；绑定到智能体后注入系统提示。"
        searchPlaceholder="搜索 MCP 服务名称"
        search={search}
        onSearchChange={setSearch}
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
        <AddResourceCard
          label="注册 MCP 服务"
          hint="填写服务端点 URL（支持 JSON-RPC tools/list）"
          onClick={() => setDialogOpen(true)}
        />
        {filtered.map((s: McpService) => (
          <ResourceItemCard
            key={s.id}
            title={s.name}
            description={s.endpoint_url}
            badge={s.status}
            meta={
              <span>
                {s.transport} · 工具 {s.tools_cache?.length ?? 0} 个
                {s.last_sync_at ? ` · 已同步` : ""}
              </span>
            }
            actions={
              <span className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="text-xs text-brand hover:underline"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSync(s.id);
                  }}
                >
                  同步工具
                </button>
                <button
                  type="button"
                  className="text-xs text-ink-muted hover:underline"
                  onClick={(e) => {
                    e.stopPropagation();
                    setExpandedId(expandedId === s.id ? null : s.id);
                  }}
                >
                  {expandedId === s.id ? "收起" : "工具列表"}
                </button>
                <button
                  type="button"
                  className="text-xs text-red-600 hover:underline"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(s);
                  }}
                >
                  删除
                </button>
              </span>
            }
          />
        ))}
      </ResourceListLayout>

      {expandedId && (
        <section className="card p-4 text-sm">
          <h3 className="font-medium text-ink">工具缓存</h3>
          <ul className="mt-2 space-y-1 text-xs text-ink-muted">
            {(filtered.find((x) => x.id === expandedId)?.tools_cache ?? []).map(
              (t: Record<string, unknown>, i) => (
                <li key={i}>
                  <span className="font-medium text-ink">{String(t.name)}</span>
                  {t.description ? ` — ${String(t.description)}` : ""}
                </li>
              ),
            )}
          </ul>
        </section>
      )}

      <ResourceDialog
        open={dialogOpen}
        title="注册 MCP 服务"
        onClose={() => setDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onCreate}>
              注册
            </button>
          </>
        }
      >
        <input
          className="input-field w-full"
          placeholder="名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="端点 URL"
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
        />
        <select
          className="input-field w-full"
          value={transport}
          onChange={(e) => setTransport(e.target.value)}
        >
          <option value="sse">sse</option>
          <option value="http">http</option>
          <option value="streamable-http">streamable-http</option>
        </select>
      </ResourceDialog>
      {confirmDialog}
    </>
  );
}
