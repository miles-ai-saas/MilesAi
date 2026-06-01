"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import type { BizServiceLineTemplatePack } from "@/lib/types";

export function useServiceTemplateMarketPage() {
  const { ready } = useRequireAuth();
  const { canWriteProject } = useBizPermissions();
  const [allItems, setAllItems] = useState<BizServiceLineTemplatePack[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [serviceLine, setServiceLine] = useState("");
  const [featuredOnly, setFeaturedOnly] = useState(false);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setAllItems(await api.listServiceLineTemplatePacks());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    void reload();
  }, [ready, reload]);

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

  const detailPack = detailId ? allItems.find((p) => p.id === detailId) ?? null : null;

  const applyPack = async (pack: BizServiceLineTemplatePack) => {
    if (!canWriteProject) return;
    if (!window.confirm(`将「${pack.name}」应用到「${pack.service_line_label}」？\n会覆盖当前租户自定义模板。`)) return;
    setApplyingId(pack.id);
    setMsg("");
    try {
      const result = await api.applyServiceLineTemplatePack(pack.id);
      setMsg(`已应用「${result.pack_name}」，可在服务线模板页查看与微调。`);
      setDetailId(null);
      await reload();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "应用失败");
    } finally {
      setApplyingId(null);
    }
  };

  return {
    ready,
    items,
    loading,
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
    msg,
    setMsg,
    detailId,
    setDetailId,
    detailPack,
  };
}

export type ServiceTemplateMarketPageVm = ReturnType<typeof useServiceTemplateMarketPage>;
