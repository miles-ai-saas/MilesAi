"use client";

/** 钩子列表（链路 §3 + §4）：CRUD、绑定规则、执行记录 + `useHookMeta`。 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import { optionLabel } from "@/lib/enum-meta";
import { useHookMeta } from "@/hooks/use-hook-meta";
import type { EnumOption, HookBinding, HookDefinition, HookExecutionLog } from "@/lib/types";

export default function HooksPage() {
  const { ready } = useRequireAuth();
  const meta = useHookMeta(ready);
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<HookDefinition | null>(null);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [onFailure, setOnFailure] = useState("ignore");
  const [trigger, setTrigger] = useState("before_call");
  const [scope, setScope] = useState("global");

  const [bindingHook, setBindingHook] = useState<HookDefinition | null>(null);
  const [bindings, setBindings] = useState<HookBinding[]>([]);
  const [executions, setExecutions] = useState<HookExecutionLog[]>([]);
  const [bindingsLoading, setBindingsLoading] = useState(false);
  const [bindTrigger, setBindTrigger] = useState("before_call");
  const [bindScope, setBindScope] = useState("global");
  const [bindTargetId, setBindTargetId] = useState("");

  const triggers = meta?.triggers ?? [];
  const scopes = meta?.scopes ?? [];
  const onFailureOptions = meta?.on_failure_options ?? [];

  const list = usePagedList(useCallback((p, s) => api.listHooks(p, s), []), { enabled: ready });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const filtered = useMemo(
    () => filterBySearch(list.items, search, (h) => `${h.name} ${h.hook_type}`),
    [list.items, search],
  );

  const openCreate = () => {
    setEditing(null);
    setName("");
    setUrl("");
    setOnFailure(onFailureOptions[0]?.value ?? "ignore");
    setTrigger(triggers[0]?.value ?? "before_call");
    setScope(scopes[0]?.value ?? "global");
    setDialogOpen(true);
  };

  const openEdit = (h: HookDefinition) => {
    setEditing(h);
    setName(h.name);
    const cfg = h.config as { url?: string; on_failure?: string };
    setUrl(String(cfg.url ?? ""));
    setOnFailure(cfg.on_failure ?? onFailureOptions[0]?.value ?? "ignore");
    setDialogOpen(true);
  };

  const onSaveHook = async () => {
    if (!name.trim()) return;
    const config = {
      ...(editing?.config as object),
      url: url.trim(),
      method: "POST",
      on_failure: onFailure,
      timeout: 5,
    };
    if (editing) {
      await api.updateHook(editing.id, { name: name.trim(), config });
    } else {
      if (!url.trim()) return;
      await api.createHook({
        name: name.trim(),
        hook_type: "http",
        config,
        trigger,
        scope,
      });
    }
    setDialogOpen(false);
    await list.reload();
  };

  const onDeleteHook = (h: HookDefinition) => {
    requestConfirm({
      title: "删除钩子",
      message: (
        <>
          确定删除钩子 <span className="font-medium">{h.name}</span> 及其全部绑定？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteHook(h.id);
        await list.reload();
      },
    });
  };

  const openBindings = async (h: HookDefinition) => {
    setBindingHook(h);
    setBindingsLoading(true);
    try {
      const [b, ex] = await Promise.all([
        api.listHookBindings(h.id),
        api.listHookExecutions(h.id, 1, 8),
      ]);
      setBindings(b);
      setExecutions(ex.items);
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
    const [b, ex] = await Promise.all([
      api.listHookBindings(bindingHook.id),
      api.listHookExecutions(bindingHook.id, 1, 8),
    ]);
    setBindings(b);
    setExecutions(ex.items);
    setBindTargetId("");
  };

  const removeBinding = async (bindingId: string) => {
    if (!bindingHook) return;
    await api.deleteHookBinding(bindingId);
    setBindings(await api.listHookBindings(bindingHook.id));
  };

  const renderTriggerOption = (t: EnumOption) => (
    <option key={t.value} value={t.value}>
      {t.label}
      {t.hint ? ` — ${t.hint}` : ""}
      {t.implemented === false ? "（未接线）" : ""}
    </option>
  );

  return (
    <>
      <ResourceListLayout
        title="钩子"
        description="在智能体对话、流程运行、工具调用等节点挂载 HTTP 扩展，用于审计、鉴权、限流或对接外部系统。请求体为 Event v1 信封（含 trace_id）；before_* 钩子可返回 block / modify。敏感词拦截请使用合规模块。"
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
          label="新建 HTTP 钩子"
          hint="Webhook · 支持多条绑定规则"
          onClick={openCreate}
        />
        {filtered.map((h) => (
          <ResourceItemCard
            key={h.id}
            title={h.name}
            description={String((h.config as { url?: string }).url ?? "未配置 URL")}
            badge={h.hook_type}
            meta={
              <span className="text-xs text-ink-muted">
                {h.is_active ? "已启用" : "已停用"}
                {(h.config as { on_failure?: string }).on_failure === "fail_request"
                  ? " · 失败时阻断"
                  : ""}
              </span>
            }
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
                  绑定与记录
                </button>
              </div>
            }
          />
        ))}
      </ResourceListLayout>

      <ResourceDialog
        open={dialogOpen}
        title={editing ? "编辑 HTTP 钩子" : "新建 HTTP 钩子"}
        description="接收 JSON 信封；before_* 可响应 action: continue | block | modify"
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
        <div className="space-y-3">
          <input
            className="input-field w-full"
            placeholder="名称，如：访问审计"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            className="input-field w-full font-mono text-sm"
            placeholder="https://your-service/hooks/agent"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-ink-muted">HTTP 失败时（仅 before_*）</span>
            <select
              className="input-field w-full"
              value={onFailure}
              onChange={(e) => setOnFailure(e.target.value)}
              disabled={!onFailureOptions.length}
            >
              {onFailureOptions.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          {!editing && (
            <>
              <label className="block text-sm">
                <span className="mb-1 block text-xs text-ink-muted">默认绑定 · 时机</span>
                <select
                  className="input-field w-full"
                  value={trigger}
                  onChange={(e) => setTrigger(e.target.value)}
                  disabled={!triggers.length}
                >
                  {triggers.map(renderTriggerOption)}
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-xs text-ink-muted">默认绑定 · 作用域</span>
                <select
                  className="input-field w-full"
                  value={scope}
                  onChange={(e) => setScope(e.target.value)}
                  disabled={!scopes.length}
                >
                  {scopes.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                      {s.hint ? ` — ${s.hint}` : ""}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
        </div>
      </ResourceDialog>

      <ResourceDialog
        open={!!bindingHook}
        title={bindingHook ? `${bindingHook.name} · 绑定与执行` : "绑定"}
        size="lg"
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
          <div className="space-y-6">
            <section>
              <h3 className="mb-2 text-sm font-medium text-ink">挂载规则</h3>
              <ul className="divide-y rounded-lg border border-line text-sm">
                {bindings.length === 0 && (
                  <li className="px-3 py-2 text-ink-faint">暂无绑定</li>
                )}
                {bindings.map((b) => (
                  <li key={b.id} className="flex items-center justify-between gap-2 px-3 py-2">
                    <span className="text-xs text-ink-muted">
                      {optionLabel(scopes, b.scope)} · {optionLabel(triggers, b.trigger)}
                      {b.target_id ? ` · ${b.target_id.slice(0, 8)}…` : ""} · 优先级 {b.priority}
                    </span>
                    <button
                      type="button"
                      className="shrink-0 text-xs text-red-600"
                      onClick={() => removeBinding(b.id)}
                    >
                      删除
                    </button>
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <h3 className="mb-2 text-sm font-medium text-ink">最近执行</h3>
              <ul className="divide-y rounded-lg border border-line text-xs">
                {executions.length === 0 && (
                  <li className="px-3 py-2 text-ink-faint">尚无执行记录</li>
                )}
                {executions.map((ex) => (
                  <li key={ex.id} className="space-y-0.5 px-3 py-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={
                          ex.status === "ok"
                            ? "text-green-700"
                            : ex.status === "blocked"
                              ? "text-amber-700"
                              : "text-red-600"
                        }
                      >
                        {ex.status}
                      </span>
                      <span className="text-ink-muted">
                        {optionLabel(triggers, ex.trigger)} · {optionLabel(scopes, ex.scope)}
                      </span>
                      {ex.duration_ms != null && <span>{ex.duration_ms}ms</span>}
                      {ex.http_status != null && <span>HTTP {ex.http_status}</span>}
                    </div>
                    {ex.error_message && (
                      <p className="truncate text-ink-faint">{ex.error_message}</p>
                    )}
                  </li>
                ))}
              </ul>
            </section>

            <section className="border-t border-line-soft pt-4">
              <p className="mb-2 text-xs font-medium text-ink-muted">新增绑定</p>
              <select
                className="input-field mb-2 w-full"
                value={bindTrigger}
                onChange={(e) => setBindTrigger(e.target.value)}
                disabled={!triggers.length}
              >
                {triggers.map(renderTriggerOption)}
              </select>
              <select
                className="input-field mb-2 w-full"
                value={bindScope}
                onChange={(e) => setBindScope(e.target.value)}
                disabled={!scopes.length}
              >
                {scopes.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                    {s.hint ? ` — ${s.hint}` : ""}
                  </option>
                ))}
              </select>
              <input
                className="input-field mb-2 w-full font-mono text-xs"
                placeholder="目标 ID（global 可留空）"
                value={bindTargetId}
                onChange={(e) => setBindTargetId(e.target.value)}
              />
              <button type="button" className="btn-primary w-full" onClick={addBinding}>
                添加绑定
              </button>
            </section>
          </div>
        )}
      </ResourceDialog>
      {confirmDialog}
    </>
  );
}
