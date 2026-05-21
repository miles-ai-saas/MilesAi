"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import type { HookBinding, HookDefinition } from "@/lib/types";

const TRIGGERS = [
  "before_call",
  "after_call",
  "before_reasoning",
  "after_reasoning",
  "before_tool",
  "after_tool",
  "on_error",
];

const SCOPES = ["global", "agent", "flow", "tool", "app"];

export default function HooksPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<HookDefinition | null>(null);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [trigger, setTrigger] = useState("before_call");
  const [scope, setScope] = useState("global");

  const [bindingHook, setBindingHook] = useState<HookDefinition | null>(null);
  const [bindings, setBindings] = useState<HookBinding[]>([]);
  const [bindingsLoading, setBindingsLoading] = useState(false);
  const [bindTrigger, setBindTrigger] = useState("before_call");
  const [bindScope, setBindScope] = useState("global");
  const [bindTargetId, setBindTargetId] = useState("");

  const list = usePagedList(useCallback((p, s) => api.listHooks(p, s), []), { enabled: ready });

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (h) => `${h.name} ${h.hook_type}`),
    [list.items, search],
  );

  const openCreate = () => {
    setEditing(null);
    setName("");
    setUrl("");
    setTrigger("before_call");
    setScope("global");
    setDialogOpen(true);
  };

  const openEdit = (h: HookDefinition) => {
    setEditing(h);
    setName(h.name);
    setUrl(String((h.config as { url?: string }).url ?? ""));
    setDialogOpen(true);
  };

  const onSaveHook = async () => {
    if (!name.trim()) return;
    if (editing) {
      await api.updateHook(editing.id, {
        name: name.trim(),
        config: { ...(editing.config as object), url: url.trim(), method: "POST" },
      });
    } else {
      if (!url.trim()) return;
      await api.createHook({
        name: name.trim(),
        hook_type: "http",
        config: { url: url.trim(), method: "POST" },
        trigger,
        scope,
      });
    }
    setDialogOpen(false);
    await list.reload();
  };

  const onDeleteHook = async (h: HookDefinition) => {
    if (!confirm(`确定删除钩子「${h.name}」及其全部绑定？`)) return;
    await api.deleteHook(h.id);
    await list.reload();
  };

  const openBindings = async (h: HookDefinition) => {
    setBindingHook(h);
    setBindingsLoading(true);
    try {
      setBindings(await api.listHookBindings(h.id));
    } finally {
      setBindingsLoading(false);
    }
  };

  const addBinding = async () => {
    if (!bindingHook) return;
    await api.createHookBinding(bindingHook.id, {
      trigger: bindTrigger,
      scope: bindScope,
      target_id: bindTargetId.trim() || undefined,
    });
    setBindings(await api.listHookBindings(bindingHook.id));
    setBindTargetId("");
  };

  const removeBinding = async (bindingId: string) => {
    if (!bindingHook) return;
    await api.deleteHookBinding(bindingId);
    setBindings(await api.listHookBindings(bindingHook.id));
  };

  return (
    <>
      <ResourceListLayout
        title="钩子"
        description="在智能体执行关键节点挂载 HTTP 扩展；可为同一钩子配置多条绑定规则。"
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
        <AddResourceCard label="添加新钩子" hint="注册 Webhook 扩展点" onClick={openCreate} />
        {filtered.map((h) => (
          <ResourceItemCard
            key={h.id}
            title={h.name}
            description={String((h.config as { url?: string }).url ?? JSON.stringify(h.config))}
            badge={h.hook_type}
            meta={<span>{h.is_active ? "已启用" : "已停用"}</span>}
            actions={
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  className="text-xs text-ink-muted hover:underline"
                  onClick={async (e) => {
                    e.stopPropagation();
                    await api.updateHook(h.id, { is_active: !h.is_active });
                    await list.reload();
                  }}
                >
                  {h.is_active ? "停用" : "启用"}
                </button>
                <CardActions onEdit={() => openEdit(h)} onDelete={() => onDeleteHook(h)} />
                <button
                  type="button"
                  className="text-xs text-brand hover:underline"
                  onClick={() => openBindings(h)}
                >
                  绑定
                </button>
              </div>
            }
          />
        ))}
      </ResourceListLayout>

      <ResourceDialog
        open={dialogOpen}
        title={editing ? "编辑 HTTP 钩子" : "创建 HTTP 钩子"}
        onClose={() => setDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onSaveHook}>
              保存
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
        {!editing && (
          <>
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
            <select
              className="input-field w-full"
              value={scope}
              onChange={(e) => setScope(e.target.value)}
            >
              {SCOPES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </>
        )}
      </ResourceDialog>

      <ResourceDialog
        open={!!bindingHook}
        title={bindingHook ? `绑定规则 · ${bindingHook.name}` : "绑定规则"}
        onClose={() => setBindingHook(null)}
        footer={
          <button type="button" className="btn-ghost" onClick={() => setBindingHook(null)}>
            关闭
          </button>
        }
      >
        {bindingsLoading ? (
          <p className="text-sm text-ink-muted">加载中…</p>
        ) : (
          <ul className="mb-4 divide-y text-sm">
            {bindings.length === 0 && (
              <li className="py-2 text-ink-faint">暂无绑定，创建钩子时已添加默认绑定</li>
            )}
            {bindings.map((b) => (
              <li key={b.id} className="flex items-center justify-between py-2">
                <span className="text-xs text-ink-muted">
                  {b.scope} · {b.trigger}
                  {b.target_id ? ` · ${b.target_id.slice(0, 8)}` : ""} · 优先级 {b.priority}
                </span>
                <button
                  type="button"
                  className="text-xs text-red-600"
                  onClick={() => removeBinding(b.id)}
                >
                  删除
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="mb-2 text-xs font-medium text-ink-muted">新增绑定</p>
        <select
          className="input-field mb-2 w-full"
          value={bindTrigger}
          onChange={(e) => setBindTrigger(e.target.value)}
        >
          {TRIGGERS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          className="input-field mb-2 w-full"
          value={bindScope}
          onChange={(e) => setBindScope(e.target.value)}
        >
          {SCOPES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <input
          className="input-field mb-2 w-full"
          placeholder="目标 ID（global 可留空）"
          value={bindTargetId}
          onChange={(e) => setBindTargetId(e.target.value)}
        />
        <button type="button" className="btn-primary w-full" onClick={addBinding}>
          添加绑定
        </button>
      </ResourceDialog>
    </>
  );
}
