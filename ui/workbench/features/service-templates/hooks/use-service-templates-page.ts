"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import type { BizServiceLineTemplate } from "@/lib/types";

export function useServiceTemplatesPage() {
  const { ready } = useRequireAuth();
  const { canWriteProject } = useBizPermissions();
  const [items, setItems] = useState<BizServiceLineTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingLine, setEditingLine] = useState<string | null>(null);
  const [stageText, setStageText] = useState("");
  const [saving, setSaving] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await api.listServiceLineTemplates());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    void reload();
  }, [ready, reload]);

  const startEdit = (row: BizServiceLineTemplate) => {
    setEditingLine(row.service_line);
    setStageText(row.stages.join("\n"));
  };

  const cancelEdit = () => {
    setEditingLine(null);
    setStageText("");
  };

  const saveEdit = async () => {
    if (!editingLine) return;
    const stages = stageText.split("\n").map((s) => s.trim()).filter(Boolean);
    if (stages.length === 0) return;
    setSaving(true);
    try {
      const updated = await api.upsertServiceLineTemplate(editingLine, { stages });
      setItems((prev) => prev.map((r) => (r.service_line === updated.service_line ? updated : r)));
      cancelEdit();
    } finally {
      setSaving(false);
    }
  };

  const resetTemplate = async (serviceLine: string) => {
    if (!window.confirm("恢复为系统默认模板？")) return;
    setSaving(true);
    try {
      const updated = await api.resetServiceLineTemplate(serviceLine);
      setItems((prev) => prev.map((r) => (r.service_line === updated.service_line ? updated : r)));
      if (editingLine === serviceLine) cancelEdit();
    } finally {
      setSaving(false);
    }
  };

  return {
    ready,
    items,
    loading,
    canWriteProject,
    editingLine,
    stageText,
    setStageText,
    saving,
    startEdit,
    cancelEdit,
    saveEdit,
    resetTemplate,
  };
}

export type ServiceTemplatesPageVm = ReturnType<typeof useServiceTemplatesPage>;
