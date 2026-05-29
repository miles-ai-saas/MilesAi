"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { filterBySearch } from "@/lib/filter-search";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useA2aMeta } from "@/hooks/use-a2a-meta";
import type { A2aPeer } from "@/lib/types";

export function useA2aPeersPanel() {
  const { ready } = useRequireAuth();
  const a2aMeta = useA2aMeta(ready);
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const list = usePagedList(useCallback((p, s) => api.listA2aPeers(p, s), []), { enabled: ready });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const filtered = useMemo(() => filterBySearch(list.items, search, (p) => `${p.name} ${p.description ?? ""} ${p.base_url ?? ""}`), [list.items, search]);

  const resetForm = () => {
    setName("");
    setDescription("");
    setBaseUrl("");
  };

  const onCreate = async () => {
    if (!name.trim() || !baseUrl.trim()) return;
    setBusy(true);
    setMsg("");
    try {
      const peer = await api.createA2aPeer({
        name: name.trim(),
        description: description.trim() || undefined,
        base_url: baseUrl.trim(),
      });
      setDialogOpen(false);
      resetForm();
      setMsg(`已登记「${peer.name}」，请点击「同步 Card」拉取 Agent Card`);
      await list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "登记失败");
    } finally {
      setBusy(false);
    }
  };

  const onProbe = async () => {
    if (!baseUrl.trim()) return;
    setBusy(true);
    setMsg("");
    try {
      const res = await api.probeA2aPeer(baseUrl.trim());
      setMsg(res.ok ? `探测成功：${res.message}` : `探测失败：${res.message}`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "探测失败");
    } finally {
      setBusy(false);
    }
  };

  const onSync = async (id: string) => {
    setMsg("");
    try {
      const res = await api.syncA2aPeerCard(id);
      setMsg(res.message);
      await list.reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "同步失败");
    }
  };

  const onDelete = (peer: A2aPeer) => {
    requestConfirm({
      title: "删除外部 Agent",
      message: (
        <>
          确定删除外部 Agent <span className="font-medium">{peer.name}</span>？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteA2aPeer(peer.id);
        await list.reload();
      },
    });
  };

  return {
    a2aMeta,
    search,
    setSearch,
    dialogOpen,
    setDialogOpen,
    name,
    setName,
    description,
    setDescription,
    baseUrl,
    setBaseUrl,
    busy,
    msg,
    list,
    filtered,
    onCreate,
    onProbe,
    onSync,
    onDelete,
    confirmDialog,
  };
}

export type A2aPeersPanelVm = ReturnType<typeof useA2aPeersPanel>;
