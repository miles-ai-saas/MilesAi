"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { defaultCategoryForServiceLine } from "@/features/service-template-market/lib/template-pack-meta";
import type { BizEnumItem, BizServiceLineTemplate, BizServiceLineTemplatePack } from "@/lib/types";

export type MarketTab = "plaza" | "mine";

export function useServiceTemplateMarketPage() {
  const { ready } = useRequireAuth();
  const searchParams = useSearchParams();
  const { canWriteProject } = useBizPermissions();
  const [tab, setTab] = useState<MarketTab>("plaza");
  const [allItems, setAllItems] = useState<BizServiceLineTemplatePack[]>([]);
  const [mineItems, setMineItems] = useState<BizServiceLineTemplatePack[]>([]);
  const [templates, setTemplates] = useState<BizServiceLineTemplate[]>([]);
  const [categories, setCategories] = useState<BizEnumItem[]>([]);
  const [industries, setIndustries] = useState<BizEnumItem[]>([]);
  const [serviceLineOptions, setServiceLineOptions] = useState<BizEnumItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [mineLoading, setMineLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [customerType, setCustomerType] = useState("");
  const [serviceLine, setServiceLine] = useState("");
  const [featuredOnly, setFeaturedOnly] = useState(false);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [busyMineId, setBusyMineId] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishServiceLine, setPublishServiceLine] = useState("");
  const [publishCategory, setPublishCategory] = useState("");
  const [publishTags, setPublishTags] = useState<string[]>([]);
  const [publishName, setPublishName] = useState("");
  const [publishDesc, setPublishDesc] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [editPack, setEditPack] = useState<BizServiceLineTemplatePack | null>(null);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editCategory, setEditCategory] = useState("");
  const [editTags, setEditTags] = useState<string[]>([]);
  const [editStageText, setEditStageText] = useState("");
  const [editChatHint, setEditChatHint] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  const reloadPlaza = useCallback(async () => {
    setLoading(true);
    try {
      setAllItems(
        await api.listServiceLineTemplatePacks({
          category: category || undefined,
          serviceLine: serviceLine || undefined,
          customerType: customerType || undefined,
          search: search.trim() || undefined,
          featured: featuredOnly || undefined,
        }),
      );
    } finally {
      setLoading(false);
    }
  }, [category, serviceLine, customerType, search, featuredOnly]);

  const reloadMine = useCallback(async () => {
    setMineLoading(true);
    try {
      setMineItems(await api.listMyServiceLineTemplatePacks());
    } finally {
      setMineLoading(false);
    }
  }, []);

  useEffect(() => {
    if (searchParams.get("tab") === "mine") setTab("mine");
    const sl = searchParams.get("service_line");
    if (sl) setServiceLine(sl);
  }, [searchParams]);

  useEffect(() => {
    if (!ready) return;
    void api.getBizMeta().then((meta) => {
      setCategories(meta.template_pack_categories ?? []);
      setIndustries(meta.industries ?? []);
      setServiceLineOptions(meta.service_lines ?? []);
    });
    void reloadMine();
    void api.listServiceLineTemplates().then(setTemplates);
  }, [ready, reloadMine]);

  useEffect(() => {
    if (!ready || tab !== "plaza") return;
    void reloadPlaza();
  }, [ready, tab, reloadPlaza]);

  const items = allItems;

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
    const sl = first?.service_line ?? templates[0]?.service_line ?? "";
    setPublishServiceLine(sl);
    setPublishCategory(defaultCategoryForServiceLine(sl));
    setPublishTags([]);
    setPublishName("");
    setPublishDesc("");
    setPublishOpen(true);
  };

  const onPublishServiceLineChange = (sl: string) => {
    setPublishServiceLine(sl);
    setPublishCategory(defaultCategoryForServiceLine(sl));
  };

  const togglePublishTag = (key: string) => {
    setPublishTags((prev) => (prev.includes(key) ? prev.filter((t) => t !== key) : [...prev, key]));
  };

  const toggleEditTag = (key: string) => {
    setEditTags((prev) => (prev.includes(key) ? prev.filter((t) => t !== key) : [...prev, key]));
  };

  const createPublish = async () => {
    if (!publishServiceLine || !publishName.trim() || !publishCategory) return;
    setPublishing(true);
    setMsg("");
    try {
      await api.createMyServiceLineTemplatePack({
        service_line: publishServiceLine,
        category: publishCategory,
        name: publishName.trim(),
        description: publishDesc.trim() || undefined,
        tags: publishTags,
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
    setEditCategory(pack.category);
    setEditTags([...pack.tags]);
    setEditStageText(pack.stages.join("\n"));
    setEditChatHint(pack.ai_config?.chat_hint ?? "");
  };

  const saveEdit = async () => {
    if (!editPack) return;
    const stages = editStageText.split("\n").map((s) => s.trim()).filter(Boolean);
    if (!editName.trim() || stages.length === 0 || !editCategory) return;
    setEditSaving(true);
    try {
      const ai = { ...(editPack.ai_config ?? {}), chat_hint: editChatHint.trim() || undefined };
      await api.updateMyServiceLineTemplatePack(editPack.id, {
        name: editName.trim(),
        description: editDesc.trim() || undefined,
        category: editCategory,
        tags: editTags,
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

  const categoryTabs = useMemo(
    () => [{ key: "", label: "全部" }, ...categories.map((c) => ({ key: c.key, label: c.label }))],
    [categories],
  );

  return {
    ready,
    tab,
    setTab,
    items,
    mineItems,
    templates,
    categories,
    industries,
    categoryTabs,
    loading,
    mineLoading,
    search,
    setSearch,
    category,
    setCategory,
    customerType,
    setCustomerType,
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
    editCategory,
    setEditCategory,
    editTags,
    toggleEditTag,
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
    onPublishServiceLineChange,
    publishCategory,
    setPublishCategory,
    publishTags,
    togglePublishTag,
    publishName,
    setPublishName,
    publishDesc,
    setPublishDesc,
    publishing,
    createPublish,
  };
}

export type ServiceTemplateMarketPageVm = ReturnType<typeof useServiceTemplateMarketPage>;
