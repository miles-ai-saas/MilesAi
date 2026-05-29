"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import type { HookBinding, HookDefinition, HookExecutionLog } from "@/lib/types";
import type { HooksListSlice } from "@/features/http-hooks/hooks/use-hooks-list";

export function useHooksBindings(listSlice: HooksListSlice) {
  const { list } = listSlice;
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const [bindingHook, setBindingHook] = useState<HookDefinition | null>(null);
  const [bindings, setBindings] = useState<HookBinding[]>([]);
  const [executions, setExecutions] = useState<HookExecutionLog[]>([]);
  const [bindingsLoading, setBindingsLoading] = useState(false);
  const [bindTrigger, setBindTrigger] = useState("before_call");
  const [bindScope, setBindScope] = useState("global");
  const [bindTargetId, setBindTargetId] = useState("");

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
    onDeleteHook,
    openBindings,
    addBinding,
    removeBinding,
  };
}
