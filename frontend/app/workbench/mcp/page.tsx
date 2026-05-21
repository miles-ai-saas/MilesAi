"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";

export default function McpPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [endpoint, setEndpoint] = useState("http://127.0.0.1:3001/mcp");

  const list = usePagedList(useCallback((p, s) => api.listMcpServices(p, s), []), { enabled: ready });

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (s) => `${s.name} ${s.endpoint_url}`),
    [list.items, search],
  );

  const onCreate = async () => {
    await api.createMcpService(name || "MCP", endpoint);
    setName("");
    setDialogOpen(false);
    await list.reload();
  };

  return (
    <>
      <ResourceListLayout
        title="MCP"
        description="注册 Model Context Protocol 服务，同步远程工具供智能体与流程使用。"
        searchPlaceholder="搜索 MCP 服务名称"
        search={search}
        onSearchChange={setSearch}
        loading={list.loading}
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
          hint="填写服务端点 URL"
          onClick={() => setDialogOpen(true)}
        />
        {filtered.map((s) => (
          <ResourceItemCard
            key={s.id}
            title={s.name}
            description={s.endpoint_url}
            badge={s.status}
            meta={
              <span>
                工具 {s.tools_cache?.length ?? 0} 个
                {s.last_sync_at ? ` · 已同步` : ""}
              </span>
            }
            actions={
              <button
                type="button"
                className="text-xs text-brand hover:underline"
                onClick={async (e) => {
                  e.stopPropagation();
                  await api.syncMcpService(s.id);
                  await list.reload();
                }}
              >
                同步工具
              </button>
            }
          />
        ))}
      </ResourceListLayout>

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
      </ResourceDialog>
    </>
  );
}
