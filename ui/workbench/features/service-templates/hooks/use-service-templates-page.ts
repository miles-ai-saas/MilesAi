"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { useFlowTemplates } from "@/features/flows/hooks/use-flow-templates";
import type { BizServiceLineAiConfig, BizServiceLineTemplate } from "@/lib/types";

const emptyAiConfig = (): BizServiceLineAiConfig => ({
  agent_tag: "",
  flow_template_id: "",
  chat_hint: "",
  quick_prompts: [],
});

function aiConfigFromRow(row: BizServiceLineTemplate): BizServiceLineAiConfig {
  const c = row.ai_config ?? {};
  return {
    agent_tag: c.agent_tag ?? "",
    flow_template_id: c.flow_template_id ?? "",
    chat_hint: c.chat_hint ?? "",
    quick_prompts: c.quick_prompts ?? [],
  };
}

export function useServiceTemplatesPage() {
  const { ready } = useRequireAuth();
  const { canWriteProject } = useBizPermissions();
  const { templates: flowTemplates, loading: flowTemplatesLoading } = useFlowTemplates(ready);
  const [items, setItems] = useState<BizServiceLineTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingLine, setEditingLine] = useState<string | null>(null);
  const [stageText, setStageText] = useState("");
  const [aiConfig, setAiConfig] = useState<BizServiceLineAiConfig>(emptyAiConfig);
  const [quickPromptText, setQuickPromptText] = useState("");
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
    const ai = aiConfigFromRow(row);
    setEditingLine(row.service_line);
    setStageText(row.stages.join("\n"));
    setAiConfig(ai);
    setQuickPromptText((ai.quick_prompts ?? []).join("\n"));
  };

  const cancelEdit = () => {
    setEditingLine(null);
    setStageText("");
    setAiConfig(emptyAiConfig());
    setQuickPromptText("");
  };

  const saveEdit = async () => {
    if (!editingLine) return;
    const stages = stageText.split("\n").map((s) => s.trim()).filter(Boolean);
    if (stages.length === 0) return;
    const quick_prompts = quickPromptText.split("\n").map((s) => s.trim()).filter(Boolean);
    const payloadAi: BizServiceLineAiConfig = {
      agent_tag: aiConfig.agent_tag?.trim() || undefined,
      flow_template_id: aiConfig.flow_template_id?.trim() || undefined,
      chat_hint: aiConfig.chat_hint?.trim() || undefined,
      quick_prompts: quick_prompts.length > 0 ? quick_prompts : undefined,
    };
    setSaving(true);
    try {
      const updated = await api.upsertServiceLineTemplate(editingLine, {
        stages,
        ai_config: payloadAi,
      });
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
    aiConfig,
    setAiConfig,
    quickPromptText,
    setQuickPromptText,
    flowTemplates,
    flowTemplatesLoading,
    saving,
    startEdit,
    cancelEdit,
    saveEdit,
    resetTemplate,
  };
}

export type ServiceTemplatesPageVm = ReturnType<typeof useServiceTemplatesPage>;
