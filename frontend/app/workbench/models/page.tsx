"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { CardActions } from "@/components/resource/CardActions";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { filterBySearch } from "@/lib/filter-search";
import { DEFAULT_PAGE_SIZE } from "@/lib/pagination";
import type { ModelConfig } from "@/lib/types";

export default function ModelsPage() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<ModelConfig | null>(null);
  const [name, setName] = useState("");
  const [provider, setProvider] = useState("openai");
  const [modelName, setModelName] = useState("gpt-4o-mini");
  const [apiBase, setApiBase] = useState("");
  const [apiKey, setApiKey] = useState("");

  const reload = async () => {
    setLoading(true);
    try {
      setItems(await api.listModelConfigs());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!ready) return;
    reload();
  }, [ready]);

  const filtered = useMemo(
    () => filterBySearch(items, search, (m) => `${m.name} ${m.provider} ${m.model_name}`),
    [items, search],
  );

  const openCreate = () => {
    setEditing(null);
    setName("");
    setProvider("openai");
    setModelName("gpt-4o-mini");
    setApiBase("");
    setApiKey("");
    setDialogOpen(true);
  };

  const openEdit = (m: ModelConfig) => {
    setEditing(m);
    setName(m.name);
    setProvider(m.provider);
    setModelName(m.model_name);
    setApiBase(m.api_base ?? "");
    setApiKey("");
    setDialogOpen(true);
  };

  const onSave = async () => {
    if (!name.trim()) return;
    const payload = {
      name: name.trim(),
      provider,
      model_name: modelName,
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

  const onDelete = async (m: ModelConfig) => {
    if (!confirm(`确定删除模型配置「${m.name}」？`)) return;
    await api.deleteModelConfig(m.id);
    await reload();
  };

  const toggleActive = async (m: ModelConfig) => {
    await api.updateModelConfig(m.id, { is_active: !m.is_active });
    await reload();
  };

  return (
    <>
      <ResourceListLayout
        title="模型供应商"
        description="配置大模型接入，供智能体与流程节点调用。"
        searchPlaceholder="搜索模型配置名称"
        search={search}
        onSearchChange={setSearch}
        loading={loading}
        footer={
          !loading ? (
            <ResourceListFooter
              page={1}
              size={DEFAULT_PAGE_SIZE}
              total={items.length}
              onPageChange={() => {}}
            />
          ) : null
        }
      >
        <AddResourceCard label="添加模型配置" hint="接入 OpenAI 兼容或其它供应商" onClick={openCreate} />
        {filtered.map((m) => (
          <ResourceItemCard
            key={m.id}
            title={m.name}
            description={`${m.provider} / ${m.model_name}`}
            badge={m.is_active ? "启用" : "停用"}
            meta={m.api_base ? <span className="truncate">{m.api_base}</span> : undefined}
            actions={
              <div className="flex flex-wrap gap-3">
                <CardActions onEdit={() => openEdit(m)} onDelete={() => onDelete(m)} />
                <button
                  type="button"
                  className="text-xs text-ink-muted hover:underline"
                  onClick={() => toggleActive(m)}
                >
                  {m.is_active ? "停用" : "启用"}
                </button>
              </div>
            }
          />
        ))}
      </ResourceListLayout>

      <ResourceDialog
        open={dialogOpen}
        title={editing ? "编辑模型配置" : "添加模型配置"}
        onClose={() => setDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onSave}>
              保存
            </button>
          </>
        }
      >
        <input
          className="input-field w-full"
          placeholder="配置名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="供应商"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="模型名"
          value={modelName}
          onChange={(e) => setModelName(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="API Base（可选）"
          value={apiBase}
          onChange={(e) => setApiBase(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder={editing ? "API Key（留空不修改）" : "API Key（可选）"}
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
      </ResourceDialog>
    </>
  );
}
