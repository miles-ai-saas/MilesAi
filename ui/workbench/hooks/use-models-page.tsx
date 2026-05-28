"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { VENDOR_ORDER, type SourceFilter } from "@/lib/model-page-shared";
import type { ModelCatalogMeta, ModelConfig } from "@/lib/types";

export function useModelsPage() {
  const { ready } = useRequireAuth();
  const [meta, setMeta] = useState<ModelCatalogMeta | null>(null);
  const [items, setItems] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [vendor, setVendor] = useState("");
  const [modelType, setModelType] = useState("");
  const [source, setSource] = useState<SourceFilter>("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [credDialogOpen, setCredDialogOpen] = useState(false);
  const [editing, setEditing] = useState<ModelConfig | null>(null);
  const [credTarget, setCredTarget] = useState<ModelConfig | null>(null);

  const [name, setName] = useState("");
  const [vendorField, setVendorField] = useState("deepseek");
  const [modelName, setModelName] = useState("");
  const [modelCode, setModelCode] = useState("");
  const [modelTypeField, setModelTypeField] = useState("llm");
  const [description, setDescription] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [saveError, setSaveError] = useState("");

  const { requestConfirm, confirmDialog } = useConfirmAction();

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [m, list] = await Promise.all([
        api.getModelCatalogMeta(),
        api.listModelConfigs({
          vendor: vendor || undefined,
          model_type: modelType || undefined,
          source: source || undefined,
          q: search.trim() || undefined,
        }),
      ]);
      setMeta(m);
      setItems(list);
    } finally {
      setLoading(false);
    }
  }, [vendor, modelType, source, search]);

  useEffect(() => {
    if (!ready) return;
    void reload();
  }, [ready, reload]);

  const vendors = useMemo(() => {
    const fromMeta = meta?.vendors ?? [];
    return [...fromMeta].sort((a, b) => VENDOR_ORDER.indexOf(a.value as (typeof VENDOR_ORDER)[number]) - VENDOR_ORDER.indexOf(b.value as (typeof VENDOR_ORDER)[number]));
  }, [meta]);

  const openCreate = () => {
    setEditing(null);
    setName("");
    setVendorField("deepseek");
    setModelName("");
    setModelCode("");
    setModelTypeField("llm");
    setDescription("");
    setApiBase("");
    setApiKey("");
    setSaveError("");
    setDialogOpen(true);
  };

  const openEdit = (m: ModelConfig) => {
    if (m.source === "builtin") return;
    setEditing(m);
    setName(m.name);
    setVendorField(m.vendor);
    setModelName(m.model_name);
    setModelCode(m.model_code ?? "");
    setModelTypeField(m.model_type);
    setDescription(m.description ?? "");
    setApiBase(m.api_base ?? "");
    setApiKey("");
    setSaveError("");
    setDialogOpen(true);
  };

  const openCred = (m: ModelConfig) => {
    setCredTarget(m);
    setApiBase(m.api_base ?? "");
    setApiKey("");
    setCredDialogOpen(true);
  };

  const onSave = async () => {
    if (!name.trim() || !modelName.trim()) return;
    if (!editing && !apiKey.trim()) {
      setSaveError("自定义模型必须填写 API Key");
      return;
    }
    setSaveError("");
    const payload = {
      name: name.trim(),
      vendor: vendorField,
      model_name: modelName.trim(),
      model_code: modelCode.trim() || undefined,
      model_type: modelTypeField,
      description: description.trim() || undefined,
      api_base: apiBase || undefined,
      api_key: apiKey || undefined,
    };
    if (editing) {
      await api.updateModelConfig(editing.id, payload);
    } else {
      await api.createModelConfig(payload);
    }
    setDialogOpen(false);
    await reload();
  };

  const onSaveCred = async () => {
    if (!credTarget || !apiKey.trim()) return;
    await api.upsertBuiltinModelCredentials(credTarget.id, {
      api_key: apiKey.trim(),
      api_base: apiBase || undefined,
    });
    setCredDialogOpen(false);
    await reload();
  };

  const onClearBuiltinByok = (m: ModelConfig) => {
    requestConfirm({
      title: "恢复使用平台密钥",
      message: (
        <>
          将清除 <span className="font-medium">{m.name}</span> 的租户自有 Key，恢复为平台托管密钥（若平台已配置）。
        </>
      ),
      confirmLabel: "确认清除",
      onConfirm: async () => {
        await api.deleteBuiltinModelCredentials(m.id);
        await reload();
      },
    });
  };

  const onDelete = (m: ModelConfig) => {
    if (m.source === "builtin") return;
    requestConfirm({
      title: "删除自定义模型",
      message: (
        <>
          确定删除自定义模型 <span className="font-medium">{m.name}</span>？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteModelConfig(m.id);
        await reload();
      },
    });
  };

  return {
    meta,
    items,
    loading,
    search,
    setSearch,
    vendor,
    setVendor,
    modelType,
    setModelType,
    source,
    setSource,
    vendors,
    dialogOpen,
    setDialogOpen,
    credDialogOpen,
    setCredDialogOpen,
    editing,
    credTarget,
    name,
    setName,
    vendorField,
    setVendorField,
    modelName,
    setModelName,
    modelCode,
    setModelCode,
    modelTypeField,
    setModelTypeField,
    description,
    setDescription,
    apiBase,
    setApiBase,
    apiKey,
    setApiKey,
    saveError,
    setSaveError,
    confirmDialog,
    openCreate,
    openEdit,
    openCred,
    onSave,
    onSaveCred,
    onClearBuiltinByok,
    onDelete,
  };
}

export type ModelsPageVm = ReturnType<typeof useModelsPage>;
