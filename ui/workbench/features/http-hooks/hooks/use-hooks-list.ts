"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useHookMeta } from "@/features/http-hooks/hooks/use-hook-meta";
import { filterBySearch } from "@/lib/filter-search";
import type { HookDefinition } from "@/lib/types";

export function useHooksList() {
  const { ready } = useRequireAuth();
  const meta = useHookMeta(ready);
  const [search, setSearch] = useState("");

  const list = usePagedList(useCallback((p, s) => api.listHooks(p, s), []), { enabled: ready });

  const filtered = useMemo(() => filterBySearch(list.items, search, (h) => `${h.name} ${h.hook_type}`), [list.items, search]);

  const triggers = meta?.triggers ?? [];
  const scopes = meta?.scopes ?? [];
  const onFailureOptions = meta?.on_failure_options ?? [];

  return {
    meta,
    triggers,
    scopes,
    onFailureOptions,
    search,
    setSearch,
    list,
    filtered,
  };
}

export type HooksListSlice = ReturnType<typeof useHooksList>;

export function useHooksForm(listSlice: HooksListSlice) {
  const { list, triggers, scopes, onFailureOptions } = listSlice;
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<HookDefinition | null>(null);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [onFailure, setOnFailure] = useState("ignore");
  const [trigger, setTrigger] = useState("before_call");
  const [scope, setScope] = useState("global");

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

  const toggleActive = async (h: HookDefinition) => {
    await api.updateHook(h.id, { is_active: !h.is_active });
    await list.reload();
  };

  return {
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
    openCreate,
    openEdit,
    onSaveHook,
    toggleActive,
  };
}
