"use client";

/**
 * GET /flows/templates — 内置画布模板（创建流程、编辑页插入模板）。
 */
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FlowTemplate } from "@/lib/types";

export function useFlowTemplates(enabled = true) {
  const [templates, setTemplates] = useState<FlowTemplate[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setLoading(true);
    void api
      .getFlowTemplates()
      .then((res) => {
        if (!cancelled) setTemplates(res.items);
      })
      .catch(() => {
        if (!cancelled) setTemplates([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  const list = templates ?? [];
  const insertable = list.filter((t) => t.insertable);
  const defaultTemplate = list.find((t) => t.id === "rag") ?? list.find((t) => t.id !== "blank") ?? null;

  return { templates: list, insertable, defaultTemplate, loading };
}
