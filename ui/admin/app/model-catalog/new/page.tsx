"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AdminDetailHeader } from "@/components/layout/AdminDetailHeader";
import { ModelCatalogEditor } from "@/components/model-catalog/ModelCatalogEditor";
import {
  emptyForm,
  toPayload,
  type ModelCatalogFormValues,
} from "@/components/model-catalog/form-utils";
import { adminApi } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function ModelCatalogNewPage() {
  const router = useRouter();
  const ready = useRequireAdmin();
  const [form, setForm] = useState<ModelCatalogFormValues>(emptyForm());
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  if (!ready) return null;

  const onCreate = async () => {
    if (!form.name.trim() || !form.model_code.trim() || !form.model_name.trim()) {
      setErr("请填写展示名称、模型编码与 API 模型名");
      return;
    }
    setSaving(true);
    setErr("");
    try {
      const created = await adminApi.createModelCatalog(toPayload(form, true));
      router.push(`/model-catalog/${created.id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "创建失败");
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <AdminDetailHeader
        backHref="/model-catalog"
        backLabel="返回模型列表"
        title="新建内置模型"
        description="创建后为草稿状态，可在详情页继续编辑并发布上架。"
        action={
          <button
            type="button"
            className="btn-primary"
            disabled={saving}
            onClick={() => void onCreate()}
          >
            {saving ? "创建中…" : "创建并继续编辑"}
          </button>
        }
      />

      {err && <p className="text-sm text-red-600">{err}</p>}

      <div className="max-w-3xl">
        <ModelCatalogEditor
          form={form}
          onChange={(patch) => setForm((f) => ({ ...f, ...patch }))}
          isCreate
        />
      </div>
    </div>
  );
}
