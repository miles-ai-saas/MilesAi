"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { fromRow, toPayload, type ModelCatalogFormValues } from "@/components/model-catalog/form-utils";
import { adminApi, type AdminModelCatalog } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export function useModelCatalogDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const ready = useRequireAdmin();
  const [model, setModel] = useState<AdminModelCatalog | null>(null);
  const [form, setForm] = useState<ModelCatalogFormValues | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);

  const reload = useCallback(async () => {
    const m = await adminApi.getModelCatalog(id);
    setModel(m);
    setForm(fromRow(m));
  }, [id]);

  useEffect(() => {
    if (!ready) return;
    reload().catch(() => setErr("加载失败"));
  }, [ready, reload]);

  const patchForm = (patch: Partial<ModelCatalogFormValues>) => {
    setForm((f) => (f ? { ...f, ...patch } : f));
  };

  const onSave = async () => {
    if (!form) return;
    setSaving(true);
    setErr("");
    try {
      const updated = await adminApi.updateModelCatalog(id, toPayload(form, false));
      setModel(updated);
      setForm(fromRow(updated));
      setMsg("已保存");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const onPublish = async () => {
    setActionBusy(true);
    setErr("");
    try {
      const updated = await adminApi.publishModelCatalog(id);
      setModel(updated);
      setForm(fromRow(updated));
      setMsg("已发布，租户可见");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "发布失败");
    } finally {
      setActionBusy(false);
    }
  };

  const onDeprecate = async () => {
    if (!confirm("确定下架该模型？租户将无法再新绑定。")) return;
    setActionBusy(true);
    setErr("");
    try {
      const updated = await adminApi.deprecateModelCatalog(id);
      setModel(updated);
      setForm(fromRow(updated));
      setMsg("已下架");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "下架失败");
    } finally {
      setActionBusy(false);
    }
  };

  const onDelete = async () => {
    if (!model || !confirm(`确定删除「${model.name}」？`)) return;
    setActionBusy(true);
    try {
      await adminApi.deleteModelCatalog(id);
      router.push("/model-catalog");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "删除失败");
      setActionBusy(false);
    }
  };

  return {
    model,
    form,
    msg,
    err,
    saving,
    actionBusy,
    patchForm,
    onSave,
    onPublish,
    onDeprecate,
    onDelete,
  };
}

export type ModelCatalogDetailPageVm = ReturnType<typeof useModelCatalogDetailPage>;
