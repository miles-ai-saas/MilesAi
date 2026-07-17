"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useKbMeta } from "@/features/kb/hooks/use-kb-meta";
import type { KbDetailAlertState } from "@/features/kb/hooks/use-kb-detail-page";
import type { KnowledgeBase, KbQuota } from "@/lib/types";

export function useKbDetailCore({ id }: { id: string }) {
  const router = useRouter();
  const { ready } = useRequireAuth();
  const kbMeta = useKbMeta(ready && !!id);
  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [quota, setQuota] = useState<KbQuota | null>(null);
  const [quotaLoading, setQuotaLoading] = useState(true);
  const [alert, setAlert] = useState<KbDetailAlertState>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editChunkSize, setEditChunkSize] = useState(500);
  const [editChunkOverlap, setEditChunkOverlap] = useState(50);
  const [editRetrievalMode, setEditRetrievalMode] = useState<"vector" | "hybrid">("vector");
  const [editHybridAlpha, setEditHybridAlpha] = useState(0.5);
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const reloadQuota = useCallback(() => {
    return api
      .getKbQuota()
      .then(setQuota)
      .catch(() => setQuota(null))
      .finally(() => setQuotaLoading(false));
  }, []);

  const reloadKb = useCallback(() => {
    if (!id) return;
    return api.getKb(id).then(setKb);
  }, [id]);

  useEffect(() => {
    if (!ready || !id) return;
    setQuotaLoading(true);
    Promise.all([reloadKb(), reloadQuota()]).catch((e) => setAlert({ tone: "error", message: e instanceof Error ? e.message : "加载失败" }));
  }, [ready, id, reloadKb, reloadQuota]);

  const openSettings = () => {
    if (!kb) return;
    setEditName(kb.name);
    setEditDesc(kb.description ?? "");
    setEditChunkSize(kb.chunk_size ?? 500);
    setEditChunkOverlap(kb.chunk_overlap ?? 50);
    setEditRetrievalMode(kb.retrieval_mode === "hybrid" ? "hybrid" : "vector");
    setEditHybridAlpha(kb.hybrid_alpha ?? 0.5);
    setSettingsOpen(true);
  };

  const onSaveSettings = async () => {
    if (!kb) return;
    const updated = await api.updateKb(kb.id, {
      name: editName.trim() || kb.name,
      description: editDesc || null,
      chunk_size: editChunkSize,
      chunk_overlap: editChunkOverlap,
      retrieval_mode: editRetrievalMode,
      hybrid_alpha: editHybridAlpha,
    });
    setKb(updated);
    setSettingsOpen(false);
    setAlert({
      tone: "info",
      message: "设置已保存；分片参数仅影响之后上传或重试的文档。",
    });
  };

  const onDeleteKb = () => {
    if (!kb) return;
    requestConfirm({
      title: "删除知识库",
      description: "此操作不可撤销。",
      message: (
        <>
          确定删除知识库 <span className="font-medium">{kb.name}</span>
          ？将删除其下全部文档与向量数据。
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteKb(kb.id);
        router.push("/workbench/kb");
      },
    });
  };

  return {
    id,
    router,
    ready,
    kb,
    kbMeta,
    quota,
    quotaLoading,
    alert,
    setAlert,
    settingsOpen,
    setSettingsOpen,
    editName,
    setEditName,
    editDesc,
    setEditDesc,
    editChunkSize,
    setEditChunkSize,
    editChunkOverlap,
    setEditChunkOverlap,
    editRetrievalMode,
    setEditRetrievalMode,
    editHybridAlpha,
    setEditHybridAlpha,
    confirmDialog,
    requestConfirm,
    reloadQuota,
    openSettings,
    onSaveSettings,
    onDeleteKb,
  };
}
