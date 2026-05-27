"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi, type AdminMarketplaceApp, type AdminMarketplaceAppDetail } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function MarketplaceReviewPage() {
  const ready = useRequireAdmin();
  const [reviewMode, setReviewMode] = useState<string | null>(null);
  const [apps, setApps] = useState<AdminMarketplaceApp[]>([]);
  const [detail, setDetail] = useState<AdminMarketplaceAppDetail | null>(null);
  const [rejectTarget, setRejectTarget] = useState<AdminMarketplaceApp | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rejectLoading, setRejectLoading] = useState(false);
  const [rejectNote, setRejectNote] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const reload = async () => {
    const [modeRes, pending] = await Promise.all([
      adminApi.getMarketplaceReviewMode(),
      adminApi.listPendingMarketplaceApps(),
    ]);
    setReviewMode(modeRes.review_mode);
    setApps(pending.items);
  };

  useEffect(() => {
    if (!ready) return;
    reload().catch((e) => setErr(e instanceof Error ? e.message : "加载失败"));
  }, [ready]);

  const onApprove = async (id: string) => {
    setBusyId(id);
    setErr("");
    try {
      await adminApi.approveMarketplaceApp(id);
      setMsg("已通过并上架");
      setDetail(null);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  };

  const onConfirmReject = async () => {
    if (!rejectTarget) return;
    setRejectLoading(true);
    setErr("");
    try {
      await adminApi.rejectMarketplaceApp(rejectTarget.id, rejectNote || undefined);
      setMsg("已驳回");
      setRejectTarget(null);
      setRejectNote("");
      setDetail(null);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "驳回失败");
    } finally {
      setRejectLoading(false);
    }
  };

  const onView = async (id: string) => {
    setErr("");
    try {
      setDetail(await adminApi.getMarketplaceAppForReview(id));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载详情失败");
    }
  };

  if (ready && reviewMode && reviewMode !== "platform") {
    return (
      <div>
        <PageHeader title="应用审核" description="仅 platform 审核模式下可用" />
        <p className="text-sm text-ink-muted">当前 review_mode={reviewMode}，请在工作台由租户侧审核。</p>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="应用审核" description="审核租户提交的应用上架申请（SaaS 平台 gate）" />

      {msg && <p className="mb-4 text-sm text-emerald-600">{msg}</p>}
      {err && <p className="mb-4 text-sm text-red-600">{err}</p>}

      <section className="card p-4">
        <p className="text-sm text-ink-muted">待审核 {apps.length} 个</p>
        <ul className="mt-4 space-y-3">
          {apps.length === 0 && <li className="text-sm text-ink-faint">暂无待审核应用</li>}
          {apps.map((app) => (
            <li
              key={app.id}
              className="flex flex-col gap-3 rounded-lg border border-line-soft bg-surface-muted p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <h3 className="font-semibold text-ink">
                  {app.icon || "📦"} {app.name}
                </h3>
                <p className="mt-1 text-sm text-ink-muted line-clamp-2">
                  {app.description || "无描述"}
                </p>
                <p className="mt-1 text-xs text-ink-faint">
                  {app.category_name ? `${app.category_name} · ` : ""}
                  提交于{" "}
                  {app.submitted_at
                    ? new Date(app.submitted_at).toLocaleString("zh-CN")
                    : "—"}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <button type="button" className="btn-secondary text-xs" onClick={() => onView(app.id)}>
                  详情
                </button>
                <button
                  type="button"
                  className="btn-primary text-xs"
                  disabled={busyId === app.id}
                  onClick={() => onApprove(app.id)}
                >
                  {busyId === app.id ? "处理中…" : "通过"}
                </button>
                <button
                  type="button"
                  className="btn-ghost text-xs text-red-600"
                  disabled={busyId === app.id}
                  onClick={() => setRejectTarget(app)}
                >
                  驳回
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      {detail && (
        <section className="card mt-6 p-4">
          <div className="flex items-start justify-between gap-3">
            <h2 className="text-sm font-semibold text-ink">Manifest 摘要</h2>
            <button type="button" className="text-xs text-ink-muted" onClick={() => setDetail(null)}>
              关闭
            </button>
          </div>
          <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-surface-muted p-3 text-xs text-ink-muted">
            {JSON.stringify(detail.manifest, null, 2)}
          </pre>
        </section>
      )}

      {rejectTarget && (
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
              <button
                type="button"
                className="btn-secondary"
                disabled={rejectLoading}
                onClick={() => setRejectTarget(null)}
              >
                取消
              </button>
              <button
                type="button"
                className="btn-primary bg-red-600 hover:bg-red-700"
                disabled={rejectLoading}
                onClick={() => void onConfirmReject()}
              >
                {rejectLoading ? "提交中…" : "确认驳回"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
