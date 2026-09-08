"use client";

import { ListFooter } from "@/components/list/ListFooter";
import type { MarketplaceReviewPageVm } from "@/features/marketplace/hooks/use-marketplace-review-page";

export function MarketplaceReviewListSection({ vm }: { vm: MarketplaceReviewPageVm }) {
  const { list, busyId, onView, onApprove, setRejectTarget } = vm;

  return (
    <section className="card p-4">
      <p className="text-sm text-ink-muted">待审核 {list.total} 个</p>
      {list.loading ? (
        <p className="mt-4 text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <ul className="mt-4 space-y-3">
            {list.items.length === 0 && <li className="text-sm text-ink-faint">暂无待审核应用</li>}
            {list.items.map((app) => (
              <li
                key={app.id}
                className="flex flex-col gap-3 rounded-lg border border-line-soft bg-surface-muted p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <h3 className="font-semibold text-ink">
                    {app.icon || "📦"} {app.name}
                  </h3>
                  <p className="mt-1 text-sm text-ink-muted line-clamp-2">{app.description || "无描述"}</p>
                  <p className="mt-1 admin-data-meta">
                    {app.category_name ? `${app.category_name} · ` : ""}
                    提交于 {app.submitted_at ? new Date(app.submitted_at).toLocaleString("zh-CN") : "—"}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <button type="button" className="btn-secondary text-xs" onClick={() => void onView(app.id)}>
                    详情
                  </button>
                  <button type="button" className="btn-primary text-xs" disabled={busyId === app.id} onClick={() => void onApprove(app.id)}>
                    {busyId === app.id ? "处理中…" : "通过"}
                  </button>
                  <button
                    type="button"
                    className="btn-ghost text-xs text-red-600"
                    disabled={busyId === app.id}
                    onClick={() => setRejectTarget({ id: app.id, name: app.name })}
                  >
                    驳回
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <ListFooter className="mt-3" page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
        </>
      )}
    </section>
  );
}

export function MarketplaceReviewDetailSection({ vm }: { vm: MarketplaceReviewPageVm }) {
  const { detail, setDetail } = vm;
  if (!detail) return null;

  return (
    <section className="card mt-6 p-4">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-sm font-semibold text-ink">Manifest 摘要</h2>
        <button type="button" className="text-xs text-ink-muted" onClick={() => setDetail(null)}>
          关闭
        </button>
      </div>
      <pre className="admin-code-block mt-3 max-h-80 rounded-lg bg-surface-muted p-3">{JSON.stringify(detail.manifest, null, 2)}</pre>
    </section>
  );
}

export function MarketplaceReviewRejectDialog({ vm }: { vm: MarketplaceReviewPageVm }) {
  const { rejectTarget, setRejectTarget, rejectNote, setRejectNote, rejectLoading, onConfirmReject } = vm;
  if (!rejectTarget) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="card w-full max-w-sm p-4">
        <h3 className="font-semibold text-ink">驳回应用</h3>
        <p className="mt-1 text-xs text-ink-muted">驳回原因将展示给发布方。</p>
        <textarea
          className="input-field mt-3 min-h-[80px] w-full resize-y"
          placeholder="驳回原因（可选）"
          value={rejectNote}
          onChange={(e) => setRejectNote(e.target.value)}
        />
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className="btn-secondary" disabled={rejectLoading} onClick={() => setRejectTarget(null)}>
            取消
          </button>
          <button type="button" className="btn-primary bg-red-600 hover:bg-red-700" disabled={rejectLoading} onClick={() => void onConfirmReject()}>
            {rejectLoading ? "提交中…" : "确认驳回"}
          </button>
        </div>
      </div>
    </div>
  );
}
