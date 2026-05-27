"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AdminDetailHeader } from "@/components/layout/AdminDetailHeader";
import { ModelCatalogEditor } from "@/components/model-catalog/ModelCatalogEditor";
import {
  fromRow,
  STATUS_LABEL,
  statusBadgeClass,
  toPayload,
  TYPE_LABEL,
  VENDOR_LABEL,
  type ModelCatalogFormValues,
} from "@/components/model-catalog/form-utils";
import { adminApi, type AdminModelCatalog } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function ModelCatalogDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const ready = useRequireAdmin();
  const [model, setModel] = useState<AdminModelCatalog | null>(null);
  const [form, setForm] = useState<ModelCatalogFormValues | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);

  const reload = async () => {
    const m = await adminApi.getModelCatalog(id);
    setModel(m);
    setForm(fromRow(m));
  };

  useEffect(() => {
    if (!ready) return;
    reload().catch(() => setErr("加载失败"));
  }, [ready, id]);

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

  if (!model || !form) {
    return <p className="text-sm cell-muted">加载中…</p>;
  }

  const modelId = model.model_code ?? model.model_name;

  return (
    <div className="space-y-6">
      <AdminDetailHeader
        backHref="/model-catalog"
        backLabel="返回模型列表"
        title={model.name}
        badges={
          <>
            <span className={`status-badge ${statusBadgeClass(model.publish_status)}`}>
              {STATUS_LABEL[model.publish_status] ?? model.publish_status}
            </span>
            <span className={model.has_api_key ? "key-badge-ready" : "key-badge-missing"}>
              {model.has_api_key ? "Key 已配置" : "Key 未配置"}
            </span>
          </>
        }
        description={
          <>
            {VENDOR_LABEL[model.vendor] ?? model.vendor}
            <span className="mx-2 text-ink-faint">·</span>
            {TYPE_LABEL[model.model_type] ?? model.model_type}
            {modelId && (
              <>
                <span className="mx-2 text-ink-faint">·</span>
                <span className="font-mono text-xs">{modelId}</span>
              </>
            )}
          </>
        }
        action={
          <button
            type="button"
            className="btn-primary"
            disabled={saving}
            onClick={() => void onSave()}
          >
            {saving ? "保存中…" : "保存更改"}
          </button>
        }
      />

      {msg && <p className="text-sm text-emerald-600">{msg}</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ModelCatalogEditor
            form={form}
            onChange={patchForm}
            isCreate={false}
            model={model}
          />
        </div>

        <aside className="space-y-4">
          <section className="card p-5">
            <h2 className="text-sm font-semibold text-ink">发布</h2>
            <p className="mt-1 text-xs cell-muted">
              草稿仅运营可见；发布后租户可在模型目录绑定使用。
            </p>
            <div className="mt-4 flex flex-col gap-2">
              {model.publish_status === "draft" && (
                <button
                  type="button"
                  className="btn-primary w-full"
                  disabled={actionBusy}
                  onClick={() => void onPublish()}
                >
                  发布上架
                </button>
              )}
              {model.publish_status === "published" && (
                <button
                  type="button"
                  className="btn-ghost w-full text-amber-700"
                  disabled={actionBusy}
                  onClick={() => void onDeprecate()}
                >
                  下架模型
                </button>
              )}
              {model.publish_status === "deprecated" && (
                <p className="text-xs cell-muted">已下架，可编辑后重新发布。</p>
              )}
            </div>
          </section>

          <section className="card p-5">
            <h2 className="text-sm font-semibold text-ink">元数据</h2>
            <dl className="mt-3 space-y-2 text-xs">
              <div className="flex justify-between gap-2">
                <dt className="cell-muted">创建时间</dt>
                <dd className="cell-numeric text-ink">{model.created_at.slice(0, 10)}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="cell-muted">Provider</dt>
                <dd className="font-mono text-ink">{model.provider}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="cell-muted">内部 ID</dt>
                <dd className="font-mono text-ink-faint">{model.id.slice(0, 8)}…</dd>
              </div>
            </dl>
          </section>

          {model.publish_status !== "published" && (
            <section className="card border-red-200 p-5">
              <h2 className="text-sm font-semibold text-red-700">危险操作</h2>
              <p className="mt-1 text-xs cell-muted">已发布模型需先下架才能删除。</p>
              <button
                type="button"
                className="mt-3 text-sm text-red-600 hover:underline"
                disabled={actionBusy}
                onClick={() => void onDelete()}
              >
                删除模型
              </button>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
