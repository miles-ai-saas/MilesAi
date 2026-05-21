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

const TRIGGERS = [
  "before_call",
  "after_call",
  "before_reasoning",
  "after_reasoning",
  "before_tool",
  "after_tool",
  "on_error",
];

export default function HooksPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [trigger, setTrigger] = useState("before_call");

  const list = usePagedList(useCallback((p, s) => api.listHooks(p, s), []), { enabled: ready });

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (h) => `${h.name} ${h.hook_type}`),
    [list.items, search],
  );

  const onCreate = async () => {
    if (!name.trim() || !url.trim()) return;
    await api.createHook({
      name: name.trim(),
      hook_type: "http",
      config: { url: url.trim(), method: "POST" },
      trigger,
      scope: "global",
    });
    setName("");
    setUrl("");
    setDialogOpen(false);
    await list.reload();
  };

  return (
    <>
      <ResourceListLayout
        title="钩子"
        description="在智能体执行关键节点挂载 HTTP 扩展，用于日志、鉴权、审计等横切能力。"
        searchPlaceholder="搜索钩子名称"
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
          label="添加新钩子"
          hint="注册 Webhook 扩展点"
          onClick={() => setDialogOpen(true)}
        />
        {filtered.map((h) => (
          <ResourceItemCard
            key={h.id}
            title={h.name}
            description={String((h.config as { url?: string }).url ?? JSON.stringify(h.config))}
            badge={h.hook_type}
            meta={<span>{h.is_active ? "已启用" : "已停用"}</span>}
          />
        ))}
      </ResourceListLayout>

      <ResourceDialog
        open={dialogOpen}
        title="创建 HTTP 钩子"
        onClose={() => setDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onCreate}>
              创建
            </button>
          </>
        }
      >
        <input
          className="input-field w-full"
          placeholder="钩子名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="Webhook URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <select
          className="input-field w-full"
          value={trigger}
          onChange={(e) => setTrigger(e.target.value)}
        >
          {TRIGGERS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </ResourceDialog>
    </>
  );
}
