"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useHookMeta } from "@/hooks/use-hook-meta";
import { filterBySearch } from "@/lib/filter-search";
import type { HookBinding, HookDefinition, HookExecutionLog } from "@/lib/types";

export function useHooksPage() {
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

  const filtered = useMemo(() => filterBySearch(list.items, search, (h) => `${h.name} ${h.hook_type}`), [list.items, search]);

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

  const toggleActive = async (h: HookDefinition) => {
    await api.updateHook(h.id, { is_active: !h.is_active });
    await list.reload();
  };

  const openBindings = async (h: HookDefinition) => {
    setBindingHook(h);
    setBindingsLoading(true);
    try {
      const [b, ex] = await Promise.all([api.listHookBindings(h.id), api.listHookExecutions(h.id, 1, 8)]);
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
    const [b, ex] = await Promise.all([api.listHookBindings(bindingHook.id), api.listHookExecutions(bindingHook.id, 1, 8)]);
    setBindings(b);
    setExecutions(ex.items);
    setBindTargetId("");
  };

  const removeBinding = async (bindingId: string) => {
    if (!bindingHook) return;
    await api.deleteHookBinding(bindingId);
    setBindings(await api.listHookBindings(bindingHook.id));
  };

  return {
    meta,
    triggers,
    scopes,
    onFailureOptions,
    search,
    setSearch,
    list,
    filtered,
    dialogOpen,
    setDialogOpen,
    editing,
    name,
    setName,
    url,
    setUrl,
    onFailure,
    setOnFailure,
    trigger,
    setTrigger,
    scope,
    setScope,
    bindingHook,
    setBindingHook,
    bindings,
    executions,
    bindingsLoading,
    bindTrigger,
    setBindTrigger,
    bindScope,
    setBindScope,
    bindTargetId,
    setBindTargetId,
    confirmDialog,
    openCreate,
    openEdit,
    onSaveHook,
    onDeleteHook,
    toggleActive,
    openBindings,
    addBinding,
    removeBinding,
  };
}

export type HooksPageVm = ReturnType<typeof useHooksPage>;
