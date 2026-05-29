"use client";

import type { ModelCatalogDetailPageVm } from "@/hooks/use-model-catalog-detail-page";

export function ModelCatalogDetailAside({ vm }: { vm: ModelCatalogDetailPageVm }) {
  const { model, actionBusy, onPublish, onDeprecate, onDelete } = vm;
  if (!model) return null;

  return (
    <aside className="space-y-4">
      <section className="card p-5">
        <h2 className="text-sm font-semibold text-ink">发布</h2>
        <p className="mt-1 text-xs cell-muted">草稿仅运营可见；发布后租户可在模型目录绑定使用。</p>
        <div className="mt-4 flex flex-col gap-2">
          {model.publish_status === "draft" && (
            <button type="button" className="btn-primary w-full" disabled={actionBusy} onClick={() => void onPublish()}>
              发布上架
            </button>
          )}
          {model.publish_status === "published" && (
            <button type="button" className="btn-ghost w-full text-amber-700" disabled={actionBusy} onClick={() => void onDeprecate()}>
              下架模型
            </button>
          )}
          {model.publish_status === "deprecated" && <p className="text-xs cell-muted">已下架，可编辑后重新发布。</p>}
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
          <button type="button" className="mt-3 text-sm text-red-600 hover:underline" disabled={actionBusy} onClick={() => void onDelete()}>
            删除模型
          </button>
        </section>
      )}
    </aside>
  );
}
