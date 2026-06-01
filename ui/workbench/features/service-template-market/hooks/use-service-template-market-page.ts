"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import type { BizServiceLineTemplate, BizServiceLineTemplatePack } from "@/lib/types";

export type MarketTab = "plaza" | "mine";

export function useServiceTemplateMarketPage() {
  const { ready } = useRequireAuth();
  const { canWriteProject } = useBizPermissions();
  const [tab, setTab] = useState<MarketTab>("plaza");
  const [allItems, setAllItems] = useState<BizServiceLineTemplatePack[]>([]);
  const [mineItems, setMineItems] = useState<BizServiceLineTemplatePack[]>([]);
  const [templates, setTemplates] = useState<BizServiceLineTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [mineLoading, setMineLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [serviceLine, setServiceLine] = useState("");
  const [featuredOnly, setFeaturedOnly] = useState(false);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [busyMineId, setBusyMineId] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishServiceLine, setPublishServiceLine] = useState("");
  const [publishName, setPublishName] = useState("");
  const [publishDesc, setPublishDesc] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [editPack, setEditPack] = useState<BizServiceLineTemplatePack | null>(null);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editStageText, setEditStageText] = useState("");
  const [editChatHint, setEditChatHint] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  const reloadPlaza = useCallback(async () => {
    setLoading(true);
    try {
      setAllItems(await api.listServiceLineTemplatePacks());
    } finally {
      setLoading(false);
    }
  }, []);

  const reloadMine = useCallback(async () => {
    setMineLoading(true);
    try {
      setMineItems(await api.listMyServiceLineTemplatePacks());
    } finally {
      setMineLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    void reloadPlaza();
    void reloadMine();
    void api.listServiceLineTemplates().then(setTemplates);
  }, [ready, reloadPlaza, reloadMine]);

  const serviceLineOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of allItems) {
      map.set(item.service_line, item.service_line_label);
    }
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1], "zh-CN"));
  }, [allItems]);

  const items = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allItems.filter((pack) => {
      if (serviceLine && pack.service_line !== serviceLine) return false;
      if (featuredOnly && !pack.is_featured) return false;
      if (!q) return true;
      const hay = `${pack.name} ${pack.description ?? ""} ${pack.tags.join(" ")}`.toLowerCase();
      return hay.includes(q);
    });
  }, [allItems, serviceLine, featuredOnly, search]);

  const detailPack = detailId
    ? [...allItems, ...mineItems].find((p) => p.id === detailId) ?? null
    : null;

  const applyPack = async (pack: BizServiceLineTemplatePack) => {
    if (!canWriteProject) return;
    if (!window.confirm(`将「${pack.name}」应用到「${pack.service_line_label}」？\n会覆盖当前租户自定义模板。`)) return;
    setApplyingId(pack.id);
    setMsg("");
    try {
      const result = await api.applyServiceLineTemplatePack(pack.id);
      setMsg(`已应用「${result.pack_name}」，可在服务线模板页查看与微调。`);
      setDetailId(null);
      await reloadPlaza();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "应用失败");
    } finally {
      setApplyingId(null);
    }
  };

  const openPublish = () => {
    const first = templates.find((t) => t.stages.length > 0);
    setPublishServiceLine(first?.service_line ?? templates[0]?.service_line ?? "");
    setPublishName("");
    setPublishDesc("");
    setPublishOpen(true);
  };

  const createPublish = async () => {
    if (!publishServiceLine || !publishName.trim()) return;
    setPublishing(true);
    setMsg("");
    try {
      await api.createMyServiceLineTemplatePack({
        service_line: publishServiceLine,
        name: publishName.trim(),
        description: publishDesc.trim() || undefined,
      });
      setPublishOpen(false);
      setTab("mine");
      setMsg("已创建草稿，可提交审核上架");
      await reloadMine();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "创建失败");
    } finally {
      setPublishing(false);
    }
  };

  const submitMine = async (pack: BizServiceLineTemplatePack) => {
    setBusyMineId(pack.id);
    try {
      await api.submitMyServiceLineTemplatePack(pack.id);
      setMsg("已提交审核，通过后将在模板广场展示");
      await reloadMine();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "提交失败");
    } finally {
      setBusyMineId(null);
    }
  };

  const withdrawMine = async (pack: BizServiceLineTemplatePack) => {
    if (!window.confirm(`删除草稿「${pack.name}」？`)) return;
    setBusyMineId(pack.id);
    try {
      await api.withdrawMyServiceLineTemplatePack(pack.id);
      await reloadMine();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "删除失败");
    } finally {
      setBusyMineId(null);
    }
  };

  const openEdit = (pack: BizServiceLineTemplatePack) => {
    setEditPack(pack);
    setEditName(pack.name);
    setEditDesc(pack.description ?? "");
    setEditStageText(pack.stages.join("\n"));
    setEditChatHint(pack.ai_config?.chat_hint ?? "");
  };

  const saveEdit = async () => {
    if (!editPack) return;
    const stages = editStageText.split("\n").map((s) => s.trim()).filter(Boolean);
    if (!editName.trim() || stages.length === 0) return;
    setEditSaving(true);
    try {
      const ai = { ...(editPack.ai_config ?? {}), chat_hint: editChatHint.trim() || undefined };
      await api.updateMyServiceLineTemplatePack(editPack.id, {
        name: editName.trim(),
        description: editDesc.trim() || undefined,
        stages,
        ai_config: ai,
      });
      setEditPack(null);
      setMsg("已保存修改");
      await reloadMine();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setEditSaving(false);
    }
  };

  const unpublishMine = async (pack: BizServiceLineTemplatePack) => {
    if (!window.confirm(`下架「${pack.name}」？下架后可编辑并重新提交审核。`)) return;
    setBusyMineId(pack.id);
    try {
      await api.unpublishMyServiceLineTemplatePack(pack.id);
      setMsg("已下架，可在草稿中修改后重新提交");
      await reloadMine();
      await reloadPlaza();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "下架失败");
    } finally {
      setBusyMineId(null);
    }
  };

  return {
    ready,
    tab,
    setTab,
    items,
    mineItems,
    templates,
    loading,
    mineLoading,
    search,
    setSearch,
    serviceLine,
    setServiceLine,
    featuredOnly,
    setFeaturedOnly,
    serviceLineOptions,
    canWriteProject,
    applyingId,
    applyPack,
    busyMineId,
    submitMine,
    withdrawMine,
    openEdit,
    saveEdit,
    unpublishMine,
    editPack,
    setEditPack,
    editName,
    setEditName,
    editDesc,
    setEditDesc,
    editStageText,
    setEditStageText,
    editChatHint,
    setEditChatHint,
    editSaving,
    msg,
    setMsg,
    detailId,
    setDetailId,
    detailPack,
    publishOpen,
    setPublishOpen,
    openPublish,
    publishServiceLine,
    setPublishServiceLine,
    publishName,
    setPublishName,
    publishDesc,
    setPublishDesc,
    publishing,
    createPublish,
  };
}

export type ServiceTemplateMarketPageVm = ReturnType<typeof useServiceTemplateMarketPage>;
