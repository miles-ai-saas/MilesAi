"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  ModelCatalogEditDialog,
  type ModelCatalogFormValues,
} from "@/components/model-catalog/ModelCatalogEditDialog";
import { adminApi, type AdminModelCatalog } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

const VENDOR_LABEL: Record<string, string> = {
  deepseek: "深度求索",
  doubao: "豆包",
  qwen: "通义千问",
};

const STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  published: "已发布",
  deprecated: "已下架",
};

function toPayload(v: ModelCatalogFormValues, isCreate: boolean) {
  const body: Record<string, unknown> = {
    name: v.name.trim(),
    vendor: v.vendor,
    model_name: v.model_name.trim(),
    model_type: v.model_type,
    description: v.description.trim() || null,
    context_window: v.context_window.trim() || null,
    api_base: v.api_base.trim() || null,
    badge: v.badge.trim() || null,
    sort_order: v.sort_order,
    is_featured: v.is_featured,
    is_active: v.is_active,
  };
  if (isCreate) {
    body.model_code = v.model_code.trim();
    if (v.api_key.trim()) body.api_key = v.api_key.trim();
  } else {
    if (v.api_key.trim()) body.api_key = v.api_key.trim();
    if (v.clear_api_key) body.clear_api_key = true;
  }
  return body;
}

export default function ModelCatalogPage() {
  const ready = useRequireAdmin();
  const [items, setItems] = useState<AdminModelCatalog[]>([]);
  const [vendor, setVendor] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<AdminModelCatalog | null>(null);
  const [isCreate, setIsCreate] = useState(false);

  const reload = async () => {
    const res = await adminApi.listModelCatalog(vendor || undefined);
    setItems(res.items);
  };

  useEffect(() => {
    if (!ready) return;
    reload();
  }, [ready, vendor]);

  const openCreate = () => {
    setEditing(null);
    setIsCreate(true);
    setDialogOpen(true);
  };

  const openEdit = (m: AdminModelCatalog) => {
    setEditing(m);
    setIsCreate(false);
    setDialogOpen(true);
  };

  const onSave = async (values: ModelCatalogFormValues) => {
    const payload = toPayload(values, isCreate);
    if (isCreate) {
      await adminApi.createModelCatalog(payload);
    } else if (editing) {
      await adminApi.updateModelCatalog(editing.id, payload);
    }
    await reload();
  };

  const publish = async (id: string) => {
    await adminApi.publishModelCatalog(id);
    await reload();
  };

  const deprecate = async (id: string) => {
    await adminApi.deprecateModelCatalog(id);
    await reload();
  };

  return (
    <div>
      <PageHeader
        title="内置模型目录"
        description="维护内置模型元数据，配置平台 API Key 供租户直接使用。"
        action={
          <button type="button" className="btn-primary" onClick={openCreate}>
            + 新建内置模型
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {["", "deepseek", "doubao", "qwen"].map((v) => (
          <button
            key={v || "all"}
            type="button"
            onClick={() => setVendor(v)}
            className={`rounded-full px-3 py-1 text-xs ${
              vendor === v ? "bg-brand text-white" : "border bg-white text-ink-muted"
            }`}
          >
            {v ? VENDOR_LABEL[v] ?? v : "全部"}
          </button>
        ))}
      </div>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>名称</th>
              <th>服务商</th>
              <th>model</th>
              <th>状态</th>
              <th>平台 Key</th>
              <th className="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            {items.map((m) => (
              <tr key={m.id}>
                <td className="cell-primary">{m.name}</td>
                <td>{VENDOR_LABEL[m.vendor] ?? m.vendor}</td>
                <td className="cell-mono">{m.model_code ?? m.model_name}</td>
                <td>{STATUS_LABEL[m.publish_status] ?? m.publish_status}</td>
                <td>
                  <span
                    className={
                      m.has_api_key
                        ? "text-emerald-700"
                        : "text-amber-700"
                    }
                  >
                    {m.has_api_key ? "已配置" : "未配置"}
                  </span>
                </td>
                <td className="col-actions">
                  <button
                    type="button"
                    className="text-brand hover:underline"
                    onClick={() => openEdit(m)}
                  >
                    编辑
                  </button>
                  {m.publish_status === "draft" && (
                    <button
                      type="button"
                      className="text-brand hover:underline"
                      onClick={() => publish(m.id)}
                    >
                      发布
                    </button>
                  )}
                  {m.publish_status === "published" && (
                    <button
                      type="button"
                      className="text-amber-700 hover:underline"
                      onClick={() => deprecate(m.id)}
                    >
                      下架
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ModelCatalogEditDialog
        open={dialogOpen}
        title={isCreate ? "新建内置模型" : `编辑 · ${editing?.name ?? ""}`}
        initial={editing}
        isCreate={isCreate}
        onClose={() => setDialogOpen(false)}
        onSave={onSave}
      />
    </div>
  );
}
